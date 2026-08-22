---
id: SPEC-004
title: horus-server 백엔드 API 게이트웨이 및 크롤링 관제 서브시스템 명세
status: IMPLEMENTED
last_updated: 2026-08-22
version: 2.1.0
module_path: /Users/horus/dev/horus-dev/horus-server
verified_by: uvicorn app.main:app --reload (Port 8000)
---

# SPEC-004: horus-server 백엔드 API 게이트웨이 명세서

## 1. 개요 및 목적

`horus-server`는 FastAPI 기반의 비동기 백엔드 API 서버이자, 프론트엔드와 각 분석 엔진(크롤러, NLP, 퀀트)을 잇는 중앙 컨트롤러입니다.
SQLAlchemy 2.0 Async 기반의 고성능 DB 연동, **지속 크롤러 데몬 제어**, **단일 직렬 GPU 워커(텍스트/비전) 제어**, **다중 레인 Horizon 실시간 스트림 파형 API**, **MAB 실시간 뉴스 추천**, **Hybrid LLM Gateway**를 제공합니다.

---

## 2. API 엔드포인트 명세 (REST API Catalog)

### 2.1. 지속 크롤러 데몬 제어 (`/api/v1/crawl/daemon`)

| Method | Path | 설명 | Request Body / Params | 응답 DTO (Response) |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/crawl/daemon/start` | 지속 크롤러 데몬 시작 / 주기 설정 | `{"interval_seconds": 60}` | `DaemonStatusResponse` |
| `POST` | `/api/v1/crawl/daemon/pause` | 지속 크롤러 데몬 일시중지 | None | `DaemonStatusResponse` |
| `POST` | `/api/v1/crawl/daemon/resume` | 지속 크롤러 데몬 재개 | None | `DaemonStatusResponse` |
| `POST` | `/api/v1/crawl/daemon/stop` | 지속 크롤러 데몬 완전 중단 | None | `DaemonStatusResponse` |
| `GET` | `/api/v1/crawl/daemon/status` | 지속 크롤러 데몬 현재 상태 조회 | None | `DaemonStatusResponse` |

### 2.2. 단일 직렬 GPU 작업 큐 제어 (`/api/v1/crawl/gpu`)

| Method | Path | 설명 | Request Body | 응답 DTO (Response) |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/crawl/gpu/status` | GPU 큐 통합 상태 및 텍스트/비전 대기 수 조회 | None | `GPUUnifiedStatusResponse` |
| `POST` | `/api/v1/crawl/gpu/text/start` | 텍스트 NLP 서브시스템 시작 | `{"model_name": "gemma4:e4b-mlx"}` | `GPUUnifiedStatusResponse` |
| `POST` | `/api/v1/crawl/gpu/text/pause` | 텍스트 NLP 서브시스템 일시중지 | None | `GPUUnifiedStatusResponse` |
| `POST` | `/api/v1/crawl/gpu/text/resume` | 텍스트 NLP 서브시스템 재개 | None | `GPUUnifiedStatusResponse` |
| `POST` | `/api/v1/crawl/gpu/text/stop` | 텍스트 NLP 서브시스템 정지 | None | `GPUUnifiedStatusResponse` |
| `POST` | `/api/v1/crawl/gpu/vision/start` | 비전 Image-to-Text 서브시스템 시작 | `{"model_name": "qwen3.5:2b-mlx"}` | `GPUUnifiedStatusResponse` |
| `POST` | `/api/v1/crawl/gpu/vision/pause` | 비전 Image-to-Text 서브시스템 일시중지 | None | `GPUUnifiedStatusResponse` |
| `POST` | `/api/v1/crawl/gpu/vision/resume`| 비전 Image-to-Text 서브시스템 재개 | None | `GPUUnifiedStatusResponse` |
| `POST` | `/api/v1/crawl/gpu/vision/stop` | 비전 Image-to-Text 서브시스템 정지 | None | `GPUUnifiedStatusResponse` |

### 2.3. 실시간 관제 및 스트림 파형 API (`/api/v1/crawl/metrics & /events`)

| Method | Path | 설명 | Query Params | 응답 DTO (Response) |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/crawl/metrics/stream` | **다중 레인 Horizon 실시간 스트림 파형 데이터** (7일 롤링 보존 자동 정리, TPS 1.0 검증) | `range=10m\|1h\|1d\|7d` | `MultiLaneStreamResponse` |
| `GET` | `/api/v1/crawl/metrics/timeseries`| 시계열 수집 통계 집계 (UTC/KST 보정) | `range=10m\|1h\|1d\|7d&source_id=all` | `TimeSeriesMetricsResponse` |
| `GET` | `/api/v1/crawl/events/recent` | 최근 실시간 크롤링 활동 이벤트 목록 (Live Ticker용) | `limit=50` | `List[CrawlEventItem]` |
| `GET` | `/api/v1/crawl/dashboard/stats`| 대시보드 KPI 요약 지표 조회 | None | `CrawlDashboardStats` |
| `POST` | `/api/v1/crawl/test-preview` | **Seed 실시간 파싱(Dry-run) 테스트** | `CrawlTestRequest` | `CrawlTestResponse` |
| `POST` | `/api/v1/crawl/backfill` | 과거 날짜 아카이브 백필 비동기 실행 | `BackfillRequest` | `BackfillStatus` |

### 2.4. 지식 그래프, 퀀트 및 MAB 추천 API

| Method | Path | 설명 | 응답 (Response) |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/graph/cooccurrence` | 3D 시각화용 단어 동시출현 지식그래프 노드/링크 | `{"nodes": [...], "links": [...]}` |
| `GET` | `/api/v1/reco/feed` | Thompson Sampling 기반 스마트 맞춤 기사 피드 | `List[ArticleSummarySchema]` |
| `POST` | `/api/v1/reco/feedback` | 유저 클릭/노출 피드백 수신 | `{"status": "OK"}` |
| `GET` | `/api/v1/quant/closing-targets`| 날짜별 종가매매 추천 및 익일 백테스트 검증 결과 | `List[StockClosingTargetSchema]` |

---

## 3. 핵심 DTO 스키마 명세 (`app/schemas/crawl.py`)

### 3.1. `MultiLaneStreamResponse`
```python
class MultiLaneStreamResponse(BaseModel):
    range: str                       # 10m, 1h, 1d, 7d
    timestamps: List[str]            # 시간축 레이블 리스트
    time_window_seconds: int         # 윈도우 초 (예: 600)
    lanes: List[LaneSeries]          # Lane 0: Total, Lane 1..N: Sources, Lane N+1: LLM
    total_events: int
    active_lanes_count: int
    global_max_tps: float
    is_tps_compliant: bool           # 모든 Source 레인이 TPS <= 1.0을 준수하는지 여부
    duplicate_count: int             # DB 내 중복 URL 수
    latest_event_time: Optional[str]
```

### 3.2. `GPUUnifiedStatusResponse`
```python
class GPUUnifiedStatusResponse(BaseModel):
    text_state: str                  # IDLE, RUNNING, PAUSED, STOPPED
    text_model_name: str
    text_pending_count: int
    text_processed_count: int
    text_failed_count: int

    vision_state: str                # IDLE, RUNNING, PAUSED, STOPPED
    vision_model_name: str
    vision_pending_count: int
    vision_processed_count: int
    vision_failed_count: int

    total_articles: int
    current_task: Optional[Dict[str, Any]]
    last_processed_at: Optional[str]
    last_error_message: Optional[str]
```

---

## 4. 인수 및 검증 기준 (Acceptance Criteria)

* [ ] `GET /api/v1/crawl/metrics/stream?range=10m` 호출 시 60개 버킷의 타임스탬프와 각 레인별 TPS 수치가 정상 반환되는가?
* [ ] `POST /api/v1/crawl/daemon/start` 호출 시 `CrawlSchedulerDaemon`이 가동되고 상태가 `RUNNING`으로 변경되는가?
* [ ] `POST /api/v1/crawl/gpu/text/start` 및 `vision/start` 호출 시 각각 독립적으로 상태가 변경되고 대기 큐 통계가 실시간 집계되는가?
* [ ] `GET /api/v1/crawl/events/recent` 호출 시 최근 발생한 수집 이벤트가 최신순으로 50건 반환되는가?
