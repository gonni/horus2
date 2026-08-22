---
id: ADR-001
title: Spark/JVM 레거시에서 Python/Timescale/FastAPI 현대적 스택으로의 아키텍처 전환
status: ACCEPTED
date: 2026-08-16
deciders: Horus Core Team
technical_context: Legacy System (Scala 3.3, Spark Streaming, Akka, InfluxDB 2) -> Horus 2.0
---

# ADR-001: Spark/JVM 레거시에서 Python 3.11/Timescale/FastAPI로의 전환

## 1. 배경 및 문제 상황 (Context & Problem Statement)

기존 Horus 1.0 환경(`ml-amd` 서버)은 다음과 같은 기술 스택으로 구성되어 있었습니다:
- **`HorusEyes`**: 구형 웹 크롤러 (수동 Regex/DOM XPath, 포트 8070)
- **`SparkHorusTermCount`**: Apache Spark Streaming + Akka Stream 기반 실시간 단어 빈도(TF) 집계 $\rightarrow$ InfluxDB 2 적재
- **`SparkHorusTermProcessing`**: Apache Spark Batch 기반 LDA 토픽 모델링, TDM 계산, 단어 거리(`term_dist`) 계산
- **`BrainStocking`**: Scala 3.3, ZIO 기반 15:10 종가매매 추출 및 익일 성과 검증

### 레거시 시스템의 핵심 결함:
1. **과도한 메모리 및 리소스 낭비**: 단일 노드(개발 머신 및 서버)에서 복수의 Spark Context와 JVM 프로세스가 상시 상주하여 수십 GB의 메모리를 점유하고 심각한 CPU 오버헤드 유발.
2. **저장소의 파편화와 관리 복잡도**: MySQL 8, InfluxDB 2, Neo4j, Redis가 제각각 분리되어 있어 트랜잭션 정합성 유지가 어렵고 백업/복원 유지보수 비용 급증.
3. **NLP 라이브러리 생태계 단절**: 최신 LLM(Qwen, Gemini) 및 현대적 한국어 형태소 분석기(Kiwi C++)와의 통합이 어려움.

---

## 2. 고려된 대안 (Considered Options)

1. **대안 A: 레거시 JVM/Spark 최적화 및 유지**
   * *장점*: 기존 Scala 코드베이스 재사용 가능.
   * *단점*: 개발 생산성 저하, LLM 및 현대적 데이터 도구와의 연동 비용 과다, 로컬 환경 구동 불가능.
2. **대안 B: Python 3.11 + Polars / Kiwi + TimescaleDB + FastAPI 전면 개편 (선택됨)**
   * *장점*: 단일 언어 생태계 통일(Python 3.11+), C++ 기반 초고속 형태소 분석(Kiwi), TimescaleDB를 통한 시계열 처리로 InfluxDB 제거, 경량화로 개발자 머신(Apple Silicon)에서 완벽 구동.
   * *단점*: 기존 Scala 코드의 Python 포팅 비용 발생.

---

## 3. 결정 (Decision Outcome)

**대안 B를 채택하여 Python 3.11+ 기반 마이크로서비스로 전면 재구축하기로 결정했습니다.**

### 구체적 변경 내역:
* Spark Streaming $\rightarrow$ Python 3.11 + Kiwi (C++ 바인딩) + TimescaleDB Hypertable
* InfluxDB 2 $\rightarrow$ PostgreSQL 16 TimescaleDB 확장의 `term_frequencies` 테이블로 통합
* Scala ZIO BrainStocking $\rightarrow$ `horus-quant` (AsyncPG + Pandas/Polars + Gemini LLM)
* 레거시 웹 UI $\rightarrow$ `horus-web` (Next.js 14 App Router + TailwindCSS + 3d-force-graph)

---

## 4. 기대 효과 및 결과 (Consequences)

### 긍정적 효과:
* **메모리 절감**: Spark JVM 상주 메모리(8~16GB)가 경량 Python 프로세스(수백 MB)로 대폭 축소.
* **통합 DB 관리**: PostgreSQL 16 하나로 관계형 데이터, 23.8M 대용량 기사 파티션, 시계열(TimescaleDB), 벡터(pgvector)를 단일 인스턴스에서 통합 관리.
* **최신 LLM 파이프라인 즉시 결합**: Gemini 2.0 Flash 및 로컬 Ollama 모델과의 원활한 연동.

### 주의사항 및 관리 룰:
* Python의 GIL 한계를 극복하기 위해 CPU 집약적 형태소 연산은 Kiwi의 C++ 멀티스레딩 기능을 적극 활용하고, I/O 작업은 `asyncio`로 처리한다.
