# Horus 2.0 개발 환경 설정 및 초기화 가이드 (Setup Guide)

새로운 PC(macOS, Linux, Windows WSL2)에서 **Horus 2.0** 프로젝트를 클론한 뒤, 로컬 개발 환경을 구성하고 데이터베이스 및 인프라를 초기화하는 종합 가이드입니다.

---

## 📋 1. 사전 요구사항 (Prerequisites)

개발 환경을 구성하기 전에 아래 도구들이 설치되어 있어야 합니다.

| 도구 | 권장 버전 | 용도 | 설치 확인 명령어 |
| :--- | :--- | :--- | :--- |
| **Docker & Docker Compose** | 24.0+ / Compose v2 | PostgreSQL, Redis, Neo4j 인프라 컨테이너 실행 | `docker compose version` |
| **Python** | 3.11 또는 3.12 | 백엔드 API, AI 크롤러, NLP 형태소 분석, 퀀트 엔진 | `python3 --version` |
| **Node.js & npm** | Node 18+ (LTS) / npm 9+ | Next.js 14+ 프론트엔드 웹 대시보드 | `node -v`, `npm -v` |
| **Git** | 2.30+ | 소스코드 형상 관리 | `git --version` |
| **Ollama** *(선택사항)* | 0.3+ | 로컬 LLM 추론 (Qwen2.5, Gemma 등) | `ollama --version` |

---

## ⚡ 2. 원클릭 자동 셋업 (Quick Setup)

가장 빠르고 간편한 방법은 프로젝트 루트에서 제공되는 자동화 스크립트를 실행하는 것입니다.

```bash
# 1. 저장소 클론
git clone https://github.com/<your-username>/horus-dev.git
cd horus-dev

# 2. 실행 권한 부여 및 셋업 스크립트 실행
chmod +x scripts/*.sh
./scripts/setup.sh
```

### `scripts/setup.sh`가 자동으로 수행하는 작업:
1. 필수 도구(Docker, Python, Node.js) 설치 여부 검사
2. 템플릿(`.env.example`)을 기반으로 각 모듈별 `.env` 파일 자동 생성
3. `docker compose up -d`로 인프라 서비스(Postgres, Redis, Neo4j) 기동
4. PostgreSQL 헬스체크 대기 및 DDL/초기 시드 데이터(`init.sql`) 자동 적재 (`scripts/init_db.sh`)
5. 통합 Python 가상환경(`.venv`) 생성 및 전 서브모듈 의존성 일괄 설치
6. Playwright Chromium 브라우저 바이너리 자동 다운로드
7. Next.js 프론트엔드(`horus-web`) 의존성(`npm install`) 설치

---

## 🛠️ 3. 수동 단계별 설정 가이드 (Manual Setup)

원클릭 스크립트 대신 직접 단계별로 환경을 구성하려면 아래 절차를 따릅니다.

### 1단계: 환경변수 설정 파일 복사
```bash
# 프로젝트 루트 및 각 서브모듈의 .env 파일 생성
cp .env.example .env
cp docker/.env.example docker/.env
cp horus-server/.env.example horus-server/.env
cp horus-eyes/.env.example horus-eyes/.env
```
> [!TIP]
> Google Gemini API를 사용하려면 `horus-server/.env` 및 `horus-eyes/.env` 파일의 `GEMINI_API_KEY` 항목에 발급받은 API 키를 입력하세요.

---

### 2단계: 인프라 컨테이너 실행 및 DB 초기화
```bash
# Docker 인프라 기동 (PostgreSQL, Redis, Neo4j)
cd docker
docker compose up -d
cd ..

# DB 스키마 DDL 및 초기 시드 데이터 적재
./scripts/init_db.sh
```

#### 초기화되는 주요 DB 테이블 및 시계열 하이퍼테이블:
* `crawl_sources`: 크롤링 대상 사이트 시드 (네이버 속보, 뽐뿌, 클리앙, 코인판 등 초기 시드 4건 자동 등록)
* `articles`: 기사 원천 데이터 (날짜별 Range 파티셔닝: `articles_2025`, `articles_2026`, `articles_2027`)
* `term_frequencies`: TimescaleDB 시계열 하이퍼테이블 (실시간 단어 출현 빈도)
* `article_images`: 기사 본문 내 이미지 비전 LLM OCR/캡셔닝 큐
* `stock_daily` & `stock_closing_targets`: KOSPI 일별 시세 및 15:10 종가매매 퀀트 타겟
* `reco_feedbacks`: MAB 추천 피드백 (노출/클릭 로그)

---

### 3단계: Python 가상환경 및 의존성 설치
```bash
# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 의존성 패키지 일괄 설치
pip install --upgrade pip
pip install -r horus-server/requirements.txt
pip install -r horus-eyes/requirements.txt
pip install -r horus-nlp/requirements.txt
pip install -r horus-quant/requirements.txt

# Playwright 브라우저 바이너리 설치
playwright install chromium
```

---

### 4단계: 프론트엔드(`horus-web`) 의존성 설치
```bash
cd horus-web
npm install
cd ..
```

---

## 🚀 4. 서비스 실행 방법

각 서비스는 독립된 터미널에서 실행합니다.

### 1) 백엔드 코어 API (`horus-server`)
```bash
source .venv/bin/activate
cd horus-server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
* **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### 2) 프론트엔드 웹 대시보드 (`horus-web`)
```bash
cd horus-web
npm run dev
```
* **웹 대시보드**: [http://localhost:3000](http://localhost:3000)
* **수집 모니터링 및 어드민**: [http://localhost:3000/crawl-admin](http://localhost:3000/crawl-admin)
* **3D 지식그래프 시각화**: [http://localhost:3000/graph3d](http://localhost:3000/graph3d)
* **종가매매 퀀트 대시보드**: [http://localhost:3000/quant](http://localhost:3000/quant)

---

### 3) AI 크롤러 데몬 (`horus-eyes`)
```bash
source .venv/bin/activate
cd horus-eyes

# 실시간 크롤링 실행
python main.py --mode live

# 특정 날짜 과거 누락 데이터 백필 실행
python main.py --mode backfill --start 2026-08-01 --end 2026-08-15
```

---

### 4) 초경량 NLP 형태소 및 지식그래프 파이프라인 (`horus-nlp`)
```bash
source .venv/bin/activate
cd horus-nlp
python main.py
```

---

### 5) 15:10 종가매매 퀀트 스케줄러 (`horus-quant`)
```bash
source .venv/bin/activate
cd horus-quant
python main.py
```

---

## 🔍 5. 인프라 접속 정보 요약

| 서비스 | 호스트 / 포트 | 계정 (User / Password) | 비고 |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | `localhost:5432` / DB: `horus` | `horus` / `horus_secret` | TimescaleDB, pgvector, pg_trgm 포함 |
| **Redis** | `localhost:6379` | `default` / `horus_redis` | Celery Broker & 캐시 |
| **Neo4j Browser** | [http://localhost:7474](http://localhost:7474) | `neo4j` / `horus_graph` | 지식그래프 브라우저 UI |
| **Neo4j Bolt** | `bolt://localhost:7687` | `neo4j` / `horus_graph` | Cypher 드라이버 엔드포인트 |

---

## ❓ 6. 자주 발생하는 문제 및 해결 방법 (Troubleshooting)

### Q1. PostgreSQL 컨테이너 기동 시 포트 충돌이 발생합니다 (`bind: address already in use: 5432`).
- **원인**: 로컬 머신에 이미 별도의 PostgreSQL이 실행 중일 수 있습니다.
- **해결**:
  - 기존 로컬 PostgreSQL을 중지하거나,
  - `docker/.env` 및 `horus-server/.env`에서 `POSTGRES_PORT=5433`과 같이 다른 포트로 변경합니다.

### Q2. `psycopg2` 또는 `kiwipiepy` 설치 시 컴파일 에러가 발생합니다.
- **해결 (macOS)**: `brew install cmake libpq` 실행 후 `pip install` 재시도.
- **해결 (Ubuntu/Debian)**: `sudo apt-get install -y build-essential libpq-dev python3-dev` 실행.
- **해결 (Windows WSL2)**: `sudo apt update && sudo apt install -y build-essential python3-dev libpq-dev`.

### Q3. Docker 데이터 볼륨을 특정 외부 디스크로 변경하고 싶습니다.
- **해결**: `docker/.env` 파일 내 `DOCKER_DATA_ROOT=/원하는/절대경로`로 수정 후 `docker compose up -d`를 실행합니다.
