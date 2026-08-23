# Horus 2.0 - Next-Gen AI Data Intelligence Platform

**Horus 2.0**은 대규모 웹 뉴스 데이터의 **AI 기반 스마트 크롤링 $\rightarrow$ PostgreSQL 16(TimescaleDB + pgvector) 저장 $\rightarrow$ Kiwi C++ 초경량 형태소/단어 동시출현 계산 $\rightarrow$ Neo4j 지식 그래프 및 3D 시각화 $\rightarrow$ Multi-Armed Bandit(MAB) 추천 $\rightarrow$ 종가매매 퀀트(BrainStocking 2.0) $\rightarrow$ Next.js 14/15 모던 대시보드**를 아우르는 차세대 통합 데이터 인텔리전스 플랫폼입니다.

---

## 🏗️ 아키텍처 및 서브모듈 구조

```
horus-dev/
├── docs/                # [LLM Wiki] 단일 진실 공급원(SSOT) - 아키텍처, ADR, 모듈별 정밀 스펙
│   ├── SYSTEM_OVERVIEW.md  # 전체 시스템 조감도 및 아키텍처
│   ├── STATE.md            # 현재 구현 완료 현황 및 세션 인수인계 노트
│   ├── adr/                # 아키텍처 결정 기록 (ADR-001 ~ ADR-004)
│   └── specs/              # 모듈별 정밀 기능 명세서 (SPEC-001 ~ SPEC-005)
├── docker/              # [인프라] PostgreSQL 16 (TimescaleDB + pgvector), Neo4j 5, Redis 7
│   ├── docker-compose.yml
│   ├── .env.example
│   └── init-db/init.sql # DB DDL 및 초기 시드 데이터
├── horus-server/        # [백엔드 코어] FastAPI, SQLAlchemy Async, Hybrid LLM Gateway, MAB 추천
├── horus-eyes/          # [AI 크롤러] Playwright, Trafilatura, LLM Pydantic 구조화 파서, Vision LLM
├── horus-nlp/           # [NLP & 그래프] Kiwi 형태소 엔진, TimescaleDB 실시간 TF, Neo4j 적재
├── horus-quant/         # [종가매매 퀀트] BrainStocking 2.0 (15:10 추출 / 09:10 성과 검증)
├── horus-admin/         # [관리자 UI (Port 3001)] 5대 지능형 스마트 수집기 허브 & 시드 크롤러 관리 콘솔
├── horus-web/           # [서비스 UI (Port 3000)] 뉴스 인텔리전스, 3D Graph, 퀀트 모니터링 모던 대시보드
├── scripts/             # [스크립트] 원클릭 셋업(setup.sh) 및 DB 초기화(init_db.sh)
├── SETUP_GUIDE.md       # [가이드] 타 PC 개발 환경 설정 및 트러블슈팅 매뉴얼
└── README.md
```

> [!TIP]
> **LLM Wiki / 개발 명세서(SSOT)**: 새로운 AI 세션이나 다른 AI 에이전트에서 작업할 때는 [**`docs/SYSTEM_OVERVIEW.md`**](./docs/SYSTEM_OVERVIEW.md) 및 [**`docs/STATE.md`**](./docs/STATE.md)를 먼저 확인하세요. 상세 모듈 스펙은 [`docs/specs/`](./docs/specs/)에 정리되어 있습니다.


---

## ⚡ 원클릭 빠른 시작 (Quick Setup)

다른 PC에서 프로젝트를 처음 클론한 경우, 아래 단일 명령어로 인프라 실행, DB 초기화, Python 가상환경 및 프론트엔드 설치를 일괄 완료할 수 있습니다:

```bash
# 실행 권한 부여 및 셋업 스크립트 실행
chmod +x scripts/*.sh
./scripts/setup.sh

# 백엔드 + 어드민 + 서비스 UI 전체 통합 실행
./run_all.sh
```

---

## 🚀 개별 서비스 실행 가이드

가상환경 활성화 후 각 서브모듈을 실행합니다.

### 1. 백엔드 코어 서버 실행 (`horus-server`)
```bash
./run_server.sh
# 또는: cd horus-server && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
* **Swagger API 문서**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc API 문서**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### 2. 관리자 콘솔 대시보드 실행 (`horus-admin`)
```bash
./run_admin.sh
# 또는: cd horus-admin && npm run dev (Port 3001)
```
* **관리자 콘솔 메인**: [http://localhost:3001](http://localhost:3001)
* **5대 지능형 스마트 수집 허브**: [http://localhost:3001/smart-crawl](http://localhost:3001/smart-crawl)
* **시드 크롤러 & 작업 관리**: [http://localhost:3001/crawl-admin](http://localhost:3001/crawl-admin)

---

### 3. 최종 사용자 서비스 웹 대시보드 실행 (`horus-web`)
```bash
./run_web.sh
# 또는: cd horus-web && npm run dev (Port 3000)
```
* **서비스 대시보드 메인**: [http://localhost:3000](http://localhost:3000)
* **뉴스 인텔리전스 & 추천**: [http://localhost:3000/news](http://localhost:3000/news)
* **3D 지식그래프 시각화**: [http://localhost:3000/graph3d](http://localhost:3000/graph3d)
* **종가매매 퀀트 대시보드**: [http://localhost:3000/quant](http://localhost:3000/quant)


---

### 3. AI 크롤러 1회성/데몬 실행 (`horus-eyes`)
```bash
source .venv/bin/activate
cd horus-eyes

# 실시간 크롤링
python main.py --mode live

# 과거 누락 일자 백필
python main.py --mode backfill --start 2026-08-01 --end 2026-08-15
```

---

### 4. 초경량 NLP 파이프라인 실행 (`horus-nlp`)
```bash
source .venv/bin/activate
cd horus-nlp

# Kiwi 형태소 분석 및 Neo4j 동시출현망 생성 (Spark Batch 대체)
python main.py
```

---

### 5. 종가매매 퀀트 스케줄러 실행 (`horus-quant`)
```bash
source .venv/bin/activate
cd horus-quant

# 15:10 종가매매 추출 및 09:10 익일 성과 자동 검증 데몬
python main.py
```

---

## 🌟 주요 혁신 포인트 요약

| 영역 | 기존 레거시 (Old) | Horus 2.0 (New) | 개선 효과 |
| :--- | :--- | :--- | :--- |
| **인프라** | MySQL 8 + InfluxDB 2 | **PostgreSQL 16 (TimescaleDB + pgvector)** | 단일 RDBMS로 통합, 23.8M Trigram 초고속 검색, 서버 리소스 1/3 절감 |
| **지식 그래프** | RDBMS `term_dist` SQL 셀프 조인 | **Neo4j 5.x Cypher 그래프** | 단어 동시출현망 밀리초(ms) 탐색 및 차세대 GraphRAG 확장 |
| **웹 크롤러** | 수동 Regex/DOM XPath 등록 | **Trafilatura + LLM 구조화 추출** | 사이트 구조 변경에 강건한 AI 파싱 및 메타데이터 자동 정제 |
| **AI LLM** | 없음 / 단일 클라우드 | **Local Ollama (Qwen) + Cloud Gemini Hybrid** | 대량 배치는 비용 0원 로컬 처리, 실시간 고난도 분석은 Gemini 처리 |
| **배치/스트리밍**| 무거운 JVM Spark Cluster | **Kiwi C++ + Polars** | Spark의 수 GB 메모리 낭비 제거, 수 초 내 초경량 고속 연산 |
| **웹 대시보드** | Scalatra + Twirl (서버 렌더링) | **Next.js 14+ + Tailwind + 3D Force Graph** | 인터랙티브 반응형 UI, 3D 실시간 네트워크 시각화 |
