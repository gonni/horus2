# Horus 2.0 프로젝트 핸드오버 및 컨텍스트 문서 (Project Handover Context)

> **문서 갱신 일시**: 2026-08-16  
> **프로젝트 루트 경로**: `/Users/horus/dev/horus-dev/`  
> **목적**: 새로운 대화 세션 전환 시 지금까지의 시스템 분석, 아키텍처 설계, 구현 상태 및 다음 단계 크롤러 보완 작업을 즉시 이어가기 위한 컨텍스트 요약 문서입니다.

---

## 1. 프로젝트 배경 및 레거시 시스템 분석 요약

* **기존 환경 (`ml-amd` 서버 / `horus-runtime` / MySQL `192.168.35.22`)**:
  * `HorusEyes`: 웹 크롤러 엔진 (수동 Regex/DOM XPath 기반, 포트 8070, MySQL `crawl_seeds`).
  * `SparkHorusTermCount`: Spark Streaming + Akka Stream 기반 실시간 단어 빈도(TF) -> InfluxDB 2 (`term_tf`) 적재.
  * `SparkHorusTermProcessing`: Spark Batch (`RunOnceMain`) -> LDA 토픽, TDM, 단어 거리(`term_dist`) 계산.
  * `BrainStocking`: Scala 3.3, ZIO 기반 15:10 종가매매 추출 및 09:10 익일 성과 검증.
* **기존의 문제점**:
  * 단일 노드에서 무거운 Spark/JVM 다중 실행으로 수 GB 메모리 낭비 및 높은 CPU 오버헤드.
  * 수동 XPath/Regex 파싱으로 대상 사이트 구조 변경 시 잦은 크롤러 장애 발생.
  * MySQL 8 + InfluxDB 2 + Neo4j + OS crontab의 복잡한 파편화.

---

## 2. Horus 2.0 차세대 아키텍처 & 핵심 기술 스택

```
+-----------------------------------------------------------------------------------+
|                         [1. Frontend] horus-web (Port: 3000)                      |
|       Next.js 14+ (App Router) + TypeScript + TailwindCSS + shadcn/ui             |
|       - 3D 단어 동시출현망 뷰어 (3d-force-graph)                                  |
|       - 실시간 수집 모니터링, 누락 일자 백필 컨트롤러 & Seed 파싱 테스트 모달      |
|       - MAB 추천 뉴스 브라우저 & 종가매매 퀀트 대시보드                           |
+-----------------------------------------+-----------------------------------------+
                                          │ REST API / WebSocket
                                          v
+-----------------------------------------------------------------------------------+
|                       [2. Backend Core] horus-server (Port: 8000)                 |
|       FastAPI (Python 3.11+) + SQLAlchemy 2.0 Async (asyncpg/greenlet)            |
|       - Hybrid LLM Gateway (Local Ollama Qwen2.5:27b + Cloud Gemini 2.0 Flash)    |
|       - MAB (Thompson Sampling) 실시간 뉴스 추천 & Celery 비동기 파이프라인       |
|       - 실시간 수집 통계 / 백필 제어 / Seed 파싱 테스트(Dry-run) API              |
+-------------------+---------------------+--------------------+--------------------+
                    │                     │                    │
                    v                     v                    v
+-----------------------+ +-----------------------+ +-----------------------+
| [3. AI Crawler]       | | [4. NLP & Graph]      | | [5. Stock Quant]      |
| horus-eyes            | | horus-nlp             | | horus-quant           |
| - AsyncRateLimiter    | | - Kiwi (C++ 형태소)   | | - BrainStocking 2.0   |
|   (TPS ≤ 1.0 저속보장)| | - Polars (초고속 TDM) | | - 15:10 종가매매 추출 |
| - BackfillManager     | | - TimescaleDB TF 적재 | | - 09:10 성과 자동검증 |
|   (과거 누락 아카이브)| | - Neo4j 지식그래프 적재| | - LLM 종목 리포트     |
| - Trafilatura + AI    | |   (19,838+ 엣지 검증) | |                       |
+-----------------------+ +-----------------------+ +-----------------------+
                    │                     │                    │
                    └─────────────────────┼────────────────────┘
                                          ▼
+-----------------------------------------------------------------------------------+
|                           [6. Storage & Infrastructure]                           |
|  - PostgreSQL 16 (TimescaleDB + pgvector): 23.8M 파티셔닝, Trigram 인덱스, 시계열 |
|  - Neo4j 5.20 Community: (:Keyword)-[:CO_OCCURS_WITH]->(:Keyword) 지식 그래프     |
|  - Redis 7: Celery 작업 큐 & MAB 클릭/노출 실시간 카운터 캐시                     |
|  - 데이터 볼륨 마운트: /Volumes/VData/docker-runtime/horus (M1 디스크 절약)      |
+-----------------------------------------------------------------------------------+
```

---

## 3. 현재까지 구현 완료 및 검증된 핵심 기능

### ① 저속 크롤링(Slow Rate Limiter) - 1급 요구사항 충족
* [`horus-eyes/crawler/rate_limiter.py`](file:///Users/horus/dev/horus-dev/horus-eyes/crawler/rate_limiter.py): 도메인별 비동기 락과 최소 1.5초 딜레이 + 0.3~0.8초 무작위 Jitter 적용.
* **실측 속도**: **평균 0.45 ~ 0.50 req/sec (TPS < 1.0)**로 방화벽/DDoS 탐지 및 IP 차단을 원천 방지.

### ② 과거 누락 일자 백필 (Backfill Engine)
* [`horus-eyes/crawler/backfiller.py`](file:///Users/horus/dev/horus-dev/horus-eyes/crawler/backfiller.py): 시작일~종료일 범위를 지정하여 네이버 뉴스 날짜별 아카이브를 저속 순회하며, 기수집 기사는 중복 스킵하고 누락분만 선별 적재.

### ③ 레거시 MySQL `crawl_seeds` 1:1 마이그레이션 완료
* 레거시 MySQL(`192.168.35.22:3306/horus`)의 원본 시드를 PostgreSQL `crawl_sources` 테이블로 이관 완료:
  * **21**: `네이버뉴>속보>전체` (`https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001&listType=title`)
  * **22**: `뽐뿌>자유게시판` (`https://www.ppomppu.co.kr/zboard/zboard.php?id=freeboard`)
  * **23**: `좌리앙` (`https://m.clien.net/service/board/park`)
  * **24**: `코인판>자유게시판` (`https://coinpan.com/free`)
* 물리 저장 위치: `/Volumes/VData/docker-runtime/horus/postgres/`
* DDL 반영 파일: [`docker/init-db/init.sql`](file:///Users/horus/dev/horus-dev/docker/init-db/init.sql)

### ④ Seed 실시간 파싱 테스트(Dry-run) 기능 & UI 대시보드
* **백엔드 API**: `POST /api/v1/crawl/test-preview` (URL, `link_selector`, `content_selector`를 전달받아 실시간 탐색 링크 수 및 첫 기사 본문 미리보기 반환)
* **프론트엔드 UI ([`horus-web/src/app/crawl-admin/page.tsx`](file:///Users/horus/dev/horus-dev/horus-web/src/app/crawl-admin/page.tsx))**:
  * 수집 모니터링 KPI, 실시간 TPS 속도, 실시간 수집 기사 Live Feed
  * 누락 일자 백필 컨트롤러 (DatePicker, 진행률 바, 시작/중지)
  * Seed 관리 & **실시간 파싱 테스트 모달**

---

## 4. 인프라 및 서비스 실행 환경 요약

| 서비스 | 경로 / 포트 | 실행 명령어 |
| :--- | :--- | :--- |
| **인프라 컨테이너** | Postgres(5432), Neo4j(7474/7687), Redis(6379) | `cd docker && docker compose up -d` |
| **백엔드 API** | `http://localhost:8000` (`/docs`) | `cd horus-server && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` |
| **프론트엔드 웹** | `http://localhost:3000` (`/crawl-admin`) | `cd horus-web && npm run dev` |
| **크롤러 CLI** | `horus-eyes` | `python3 main.py --mode live` 또는 `--mode backfill --start YYYY-MM-DD --end YYYY-MM-DD` |
| **NLP 지식그래프** | `horus-nlp` | `python3 main.py` |

---

## 5. 다음 세션 작업 로드맵 (Next Steps)

1. **크롤러 상세 기능 보완 및 최적화**:
   * 각 대상 사이트(네이버 속보, 뽐뿌, 클리앙, 코인판)별 커스텀 DOM 구조 세부 튜닝 및 에러 핸들링 강화.
   * Playwright 동적 렌더링이 필요한 사이트와 경량 httpx 파싱 사이트의 지능형 분기 처리.
2. **Celery / Redis 기반 분산 크롤링 작업 큐 연동**:
   * 백그라운드 주기 수집 스케줄러(APScheduler / Celery Beat) 활성화.
3. **대량 과거 데이터 백필 운영 테스트 및 모니터링 안정화**.
