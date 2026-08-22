---
id: ADR-002
title: 외부 웹사이트 크롤링 시 TPS < 1.0 저속 레이트 리미터 및 Jitter 정책 도입
status: ACCEPTED
date: 2026-08-16
deciders: Horus Core Team
technical_context: horus-eyes (Web Crawler Engine)
---

# ADR-002: 크롤링 레이트 리미팅 및 IP 차단 방지 정책

## 1. 배경 및 문제 상황 (Context & Problem Statement)

과거 크롤러는 빠른 수집을 위해 다중 스레드/비동기 동시 요청을 과도하게 발생시켜 대상 사이트(네이버 뉴스, 대형 커뮤니티 등)의 방화벽에 의해 **IP 차단(HTTP 429 Too Many Requests, 403 Forbidden, 캡차)**을 겪었습니다.

Horus 2.0의 크롤링 대상은 상용 서비스 제공자 및 포털이므로, **"절대 대상 서버에 부하를 주지 않고 방화벽에 감지되지 않는 저속 안정 수집(Stealth Crawling)"**이 1급 요구사항으로 부여되었습니다.

---

## 2. 결정 (Decision Outcome)

`horus-eyes`에 도메인별 비동기 락과 의도적 지연(Delay + Jitter)을 조합한 **`AsyncRateLimiter`**를 설계하여 모든 HTTP 요청에 강제 적용하기로 결정했습니다.

### 핵심 설계 규칙:
1. **도메인별 격리(Per-Domain Lock)**: 동일 도메인(예: `news.naver.com`)으로의 동시 요청은 세마포어를 통해 엄격히 직렬화(Concurrency = 1).
2. **최소 지연시간(Base Delay)**: 요청 간 최소 `1.5초` 대기.
3. **무작위 지터(Random Jitter)**: 일정한 주기성을 피해 봇 탐지 머신러닝을 회피하기 위해 `0.3초 ~ 0.8초`의 균등 분포 난수 지연 추가.
4. **목표 처리량(Target Throughput)**: **초당 요청 수(TPS) $\le 1.0$ (실측 0.45 ~ 0.50 req/sec)** 유지.

---

## 3. 구현 참조 (Implementation Reference)

```python
# horus-eyes/crawler/rate_limiter.py 의 핵심 로직 요약
class AsyncRateLimiter:
    def __init__(self, min_interval: float = 1.5, max_jitter: float = 0.8):
        self.min_interval = min_interval
        self.max_jitter = max_jitter
        self._locks = defaultdict(asyncio.Lock)
        self._last_request_time = defaultdict(float)

    async def acquire(self, domain: str):
        async with self._locks[domain]:
            elapsed = time.time() - self._last_request_time[domain]
            jitter = random.uniform(0.3, self.max_jitter)
            target_delay = self.min_interval + jitter
            if elapsed < target_delay:
                await asyncio.sleep(target_delay - elapsed)
            self._last_request_time[domain] = time.time()
```

---

## 4. 기대 효과 및 결과 (Consequences)

* **차단율 제로**: 네이버 뉴스 및 주요 커뮤니티 장기 수집 시 429/403 차단 없이 100% 무중단 수집 달성.
* **서버 자원 친화적**: 로컬 머신의 네트워크 및 CPU 부하를 거의 소모하지 않고 백그라운드 상시 수집 가능.
* **트레이드오프**: 대량 백필(과거 수개월 데이터) 시 시간이 오래 소요되므로, 백필은 백그라운드 장기 작업으로 실행하고 일자별 중복 체크를 통해 수집 효율을 극대화함.
