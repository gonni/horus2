---
id: SPEC-005
title: horus-web 프론트엔드 대시보드 및 실시간 스트림 시각화 서브시스템 명세
status: IMPLEMENTED
last_updated: 2026-08-22
version: 2.1.0
module_path: /Users/horus/dev/horus-dev/horus-web
verified_by: npm run build / npm run dev (Port 3000)
---

# SPEC-005: horus-web 프론트엔드 대시보드 명세서

## 1. 개요 및 목적

`horus-web`은 Next.js 14 (App Router), TypeScript, TailwindCSS 기반의 모던 웹 프론트엔드 관제 대시보드입니다.
**MultiLane Horizon 실시간 스트림 파형 시각화(초당 1.0 TPS 엄격 검증)**, **실시간 수집 활동 스트림(Live Activity Ticker)**, **GPU 텍스트/비전 듀얼 제어 패널**, **지속 크롤러 데몬 컨트롤러**, **3D 단어 동시출현 지식그래프 뷰어**, **15:10 종가매매 퀀트 대시보드**를 제공합니다.

---

## 2. 컴포넌트 및 페이지 구조

```text
horus-web/src/
├── app/
│   ├── layout.tsx                     # 글로벌 레이아웃, 헤더 네비게이션(Navbar), 다크모드
│   ├── page.tsx                       # 메인 랜딩 페이지
│   ├── crawl-admin/page.tsx           # [Crawl Admin] 크롤링 관제 종합 대시보드
│   ├── graph3d/page.tsx               # [Graph] 3D Force Graph 키워드 네트워크
│   ├── news/page.tsx                  # [News] MAB 맞춤 스마트 뉴스 피드
│   └── quant/page.tsx                 # [Quant] 종가매매 타겟 및 성과 분석
├── components/
│   ├── Navbar.tsx                     # 상단 글로벌 네비게이션 바
│   └── MultiLaneStreamChart.tsx       # [신규] 다중 레인 Horizon 실시간 파형 차트
└── lib/
    └── api.ts                         # FastAPI 백엔드 연동 비동기 클라이언트
```

---

## 3. 핵심 UI 컴포넌트 상세 명세

### 3.1. Crawl Admin 대시보드 ([`src/app/crawl-admin/page.tsx`](file:///Users/horus/dev/horus-dev/horus-web/src/app/crawl-admin/page.tsx))

1. **상시 지속 크롤러 데몬 컨트롤 바**:
   - 상태 배지(`RUNNING` 초록 / `PAUSED` 주황 / `STOPPED` 회색).
   - 시작 / 일시중지 / 재개 / 정지 버튼.
   - 수집 주기 슬라이더 (10초 ~ 300초 조정) 및 다음 실행 카운트다운 타이머.
2. **GPU 듀얼 제어 패널 (Unified GPU Serial Worker Controller)**:
   - **텍스트 NLP 카드**: 모델 선택 셀렉터(`gemma4:e4b-mlx` 등), 대기 큐(Pending) 뱃지, 처리/실패 카운터, 시작/일시중지/정지 버튼.
   - **비전 Image-to-Text 카드**: 모델 선택 셀렉터(`qwen3.5:2b-mlx` 등), 대기 큐(Pending) 뱃지, 처리/실패 카운터, 시작/일시중지/정지 버튼.
   - 안전 안내 뱃지: *"이미지는 메모리에서 텍스트 변환 후 즉시 삭제(용량 0MB 부담), 원본 URL은 보존"* 명시.
3. **다중 레인 Horizon 실시간 스트림 파형 ([`MultiLaneStreamChart.tsx`](file:///Users/horus/dev/horus-dev/horus-web/src/components/MultiLaneStreamChart.tsx))**:
   - 상단 우측(LIVE)에서 생성되어 좌측(과거)으로 흘러가는 Horizon 스타일 파형.
   - **Lane 0**: 전체 통합 수집 파형 및 Total TPS.
   - **Lane 1~N**: 각 활성 Seed별 처리량 및 실시간 TPS (초당 요청 수).
   - **Lane N+1**: LLM AI 정제 처리량 파형.
   - **정밀 TPS 검증**: 각 Seed 레인별 최근 15건의 개별 호출 틱(Call Tick) 및 순간 TPS 표시, TPS 1.05 초과 시 경고 배지 표시.
   - 시간 범위 선택: `10분(10초 틱)`, `1시간(1분 틱)`, `1일(30분 틱)`, `7일(3시간 틱)`.
4. **실시간 수집 활동 스트림 피드 (Live Activity Ticker)**:
   - 3초 주기로 `GET /api/v1/crawl/events/recent`를 폴링하여 최신 이벤트를 피드 형태로 출력.
   - 이벤트 타입별 컬러 태그: `SEED`(보라), `기사`(초록), `이미지`(주황), `LLM 정제`(하늘색).
   - 기사 이미지 썸네일 미리보기 및 LLM 3줄 요약 미리보기 박스 지원.
5. **Seed 파싱 테스트 모달 (Dry-run)**:
   - URL, 링크 셀렉터, 본문 셀렉터를 입력하여 실시간 링크 탐색 및 본문 파싱 결과를 확인하는 모달.

### 3.2. 3D 단어 동시출현 지식그래프 (`/graph3d`)
* `react-force-graph-3d` (Three.js WebGL) 기반 노드/링크 3차원 회전 시각화.
* 노드 클릭 시 연관어 하이라이팅 및 최신 기사 사이드바 연동.

### 3.3. 종가매매 퀀트 대시보드 (`/quant`)
* 15:10 추천 종목 테이블, Gemini AI 종목 리포트 팝업, 09:10 익일 성과 검증 뱃지.

---

## 4. 인수 및 검증 기준 (Acceptance Criteria)

* [ ] `npm run build` 실행 시 에러 없이 클린 빌드되는가?
* [ ] `/crawl-admin` 접속 시 지속 크롤러 데몬 바, GPU 듀얼 제어 패널, MultiLaneStreamChart, Live Ticker가 정상 렌더링되는가?
* [ ] 지속 크롤러 데몬 및 GPU 텍스트/비전 워커의 시작/일시중지 버튼 클릭 시 백엔드로 API 요청이 올바르게 전달되고 UI 상태가 갱신되는가?
* [ ] MultiLane 차트에서 10m/1h/1d/7d 범위 변경 시 해당 시간축 버킷으로 파형이 부드럽게 전환되는가?
