---
id: STATE-SNAPSHOT
title: Horus 2.0 구현 현황 및 인수인계 상태 (Current State & Backlog)
status: IMPLEMENTED
last_updated: 2026-08-22
maintainer: Horus Core Team
---

# Horus 2.0 현재 구현 상태 및 백로그 (State Snapshot)

## 1. 컴포넌트별 구현 완료 현황 (Implementation Matrix)

| 서브시스템 | 핵심 모듈 | 구현 상태 | 검증 완료 항목 | 비고 / 주의사항 |
| :--- | :--- | :---: | :--- | :--- |
| **인프라 & DB** | PostgreSQL 16 (Timescale + pgvector) | `DONE` | 23.8M 파티셔닝, `crawl_events` 테이블(7일 롤링 보존) | 볼륨: `/Volumes/VData/docker-runtime/horus/` |
| | Neo4j 5.20 Community | `DONE` | 지식그래프 노드/관계 DDL, 볼륨 마운트 | 포트: 7474 (HTTP), 7687 (Bolt) |
| | Redis 7.0 | `DONE` | 컨테이너 구동, Celery & MAB 카운터 지원 | 포트: 6379 |
| **`horus-eyes`** | **`CrawlSchedulerDaemon`** | `DONE` | 60초 주기 상시 지속 수집, 신규 URL Diffing | 0% GPU 고속 CPU 파싱 적재 |
| | **`UnifiedGPUWorker`** | `DONE` | 단일 직렬 FIFO GPU 큐 (텍스트/비전 듀얼 서브시스템) | 비전 메모리 Base64 처리(디스크 0MB 부담) |
| | AsyncRateLimiter | `DONE` | 도메인별 세마포어, 1.5s + 0.3~0.8s Jitter | **실측 TPS 0.45 ~ 0.50 보장** |
| | BackfillManager | `DONE` | 날짜 범위 네이버 속보 아카이브 순회 및 중복 제거 | 백필 모드 CLI 지원 |
| **`horus-nlp`** | Kiwi 형태소 분석기 | `DONE` | 고성능 C++ 기반 한국어 명사 추출 | Spark Akka Stream 대체 |
| | 시계열 TF 집계 | `DONE` | TimescaleDB `term_frequencies` 적재 | 분/시/일 단위 집계 |
| | Neo4j 동시출현 파이프라인 | `DONE` | 19,838+ 키워드 동시출현 엣지 생성 검증 | `CO_OCCURS_WITH` 가중치 반영 |
| **`horus-quant`** | 종가매매 스캐너 | `DONE` | 15:10 당일 수급 + 텍스트 결합 종목 발굴 | `stock_closing_targets` 저장 |
| | 익일 성과 백테스터 | `DONE` | 09:10 익일 시가/고가 대비 수익률 자동 계산 | `is_success` 및 수익률 기록 |
| | LLM 종목 분석가 | `DONE` | Gemini 2.0 Flash 기반 분석 코멘트 자동 생성 | 리포트 텍스트 컬럼 적재 |
| **`horus-server`** | **지속 데몬 제어 API** | `DONE` | `POST /api/v1/crawl/daemon/*` | 시작/일시중지/재개/정지/상태 |
| | **GPU 듀얼 워커 API** | `DONE` | `POST /api/v1/crawl/gpu/*` (텍스트 & 비전 분리 제어) | 모델 변경, 실시간 대기 큐 통계 |
| | **다중 레인 Stream API** | `DONE` | `GET /api/v1/crawl/metrics/stream` | Horizon 스트림 파형, TPS 1.0 검증 |
| | **실시간 이벤트 피드 API** | `DONE` | `GET /api/v1/crawl/events/recent` | 최근 실시간 수집 활동 티커 |
| | MAB 뉴스 추천 엔진 | `DONE` | Thompson Sampling 기반 클릭/노출 가중치 | 탐색(Exploration)과 활용(Exploitation) |
| **`horus-web`** | **MultiLane Horizon Stream** | `DONE` | 다중 레인 실시간 수집 파형 차트 (ECharts) | 전체 파형 + Seed별 레인 + TPS 검증 |
| | **Live Activity Ticker** | `DONE` | 실시간 수집 활동 스트림 피드 (3초 자동 갱신) | 이미지 썸네일 & LLM 요약 프리뷰 |
| | **GPU 듀얼 제어 패널** | `DONE` | 텍스트 NLP & 비전 Image-to-Text 독립 컨트롤러 | 모델 선택 드롭다운, Pending 뱃지 |
| | 3D Force Graph UI | `DONE` | 3D 단어 동시출현망 인터랙티브 뷰어 | `/graph3d` 경로 |
| | Stock Quant Dashboard | `DONE` | 종가매매 타겟 테이블 및 백테스트 성과 요약 | `/quant` 경로 |
| **실행 스크립트** | `run_all.sh` 등 런처 | `DONE` | Ctrl+C 안전 트랩 일괄 종료 스크립트 | `run_server.sh`, `run_web.sh` 등 |

---

## 2. 세션 인수인계 핵심 노트 (Session Handover Notes)

1. **실행 편의성**:
   * `./run_all.sh` 명령어로 FastAPI 백엔드 서버와 Next.js 웹 UI를 동시 실행할 수 있으며, `Ctrl + C`를 누르면 모든 백그라운드 프로세스가 즉시 안전하게 종료됩니다.
2. **GPU 작업 큐 안전 수칙**:
   * 로컬 인퍼런스(Ollama) 사용 시 텍스트 모델(Gemma)과 비전 모델(Qwen)이 동시에 VRAM을 점유하지 않도록 `UnifiedGPUWorker`가 1건씩 순차 처리합니다.
   * 비전 이미지 처리는 디스크 파일로 저장되지 않으므로 로컬 저장 공간이 고갈되지 않습니다.
3. **수집 데이터 롤링 정리**:
   * `crawl_events` 테이블의 실시간 이벤트는 7일 이상 경과 시 `/metrics/stream` 호출 시점에 자동으로 삭제(Rolling 7-day retention)됩니다.

---

## 3. 향후 우선순위 백로그 (Next Action Items)

### [P1] 크롤러 대상 사이트 파서 세분화
* 뽐뿌, 클리앙, 코인판 등 커뮤니티 게시판의 로그인/쿠키 필요 여부 및 안티 스크래핑 대응.
* 본문 내 태그(`table`, `iframe`) 정리 필터 세분화.

### [P1] Celery Beat 기반 백그라운드 자동 주기 실행
* `CrawlSchedulerDaemon`을 Celery Beat와 결합하여 무중단 클러스터 환경에서의 분산 스케줄링 지원.

### [P2] 3D 지식그래프 시계열 필터링 고도화
* 날짜 및 시간 범위 슬라이더를 연동하여 특정 시점의 단어 동시출현망 상태를 3D로 재생(Time-lapse)하는 기능 추가.
