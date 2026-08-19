import asyncio
import random
import time
import logging
from typing import Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class AsyncRateLimiter:
    """
    저속 크롤링(Slow-rate Crawling) 전용 비동기 레이트 리미터
    - TPS <= 1.0 엄격 보장 (기본 최소 간격 1.5초 + Random Jitter 0.3~0.8초)
    - 도메인별 독립적인 요청 큐 및 락 관리
    - 비정상 트래픽/DDoS 방화벽 감지 방지
    """
    def __init__(self, min_interval: float = 1.5, max_jitter: float = 0.8):
        self.min_interval = min_interval
        self.max_jitter = max_jitter
        self._last_request_time: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        
        # 실시간 통계 메트릭
        self.request_count = 0
        self.start_time = time.time()

    def _get_domain(self, url: str) -> str:
        try:
            domain = urlparse(url).netloc
            return domain.lower() if domain else "default"
        except Exception:
            return "default"

    async def _get_domain_lock(self, domain: str) -> asyncio.Lock:
        async with self._global_lock:
            if domain not in self._locks:
                self._locks[domain] = asyncio.Lock()
            return self._locks[domain]

    async def acquire(self, url: str):
        """
        요청 전 대기 시간을 계산하여 강제 지연 (TPS < 1.0 유지)
        """
        domain = self._get_domain(url)
        domain_lock = await self._get_domain_lock(domain)

        async with domain_lock:
            now = time.time()
            last_time = self._last_request_time.get(domain, 0.0)
            elapsed = now - last_time

            # 기본 딜레이 + 무작위 지터
            jitter = random.uniform(0.3, self.max_jitter)
            required_wait = (self.min_interval + jitter) - elapsed

            if required_wait > 0:
                logger.debug(f"[RateLimiter] Waiting {required_wait:.2f}s for domain '{domain}' (Safe slow-crawl)...")
                await asyncio.sleep(required_wait)

            self._last_request_time[domain] = time.time()
            self.request_count += 1

    @property
    def current_tps(self) -> float:
        duration = max(time.time() - self.start_time, 1.0)
        return round(self.request_count / duration, 3)

# 전역 레이트 리미터 인스턴스 (최소 1.5초 간격 준수)
rate_limiter = AsyncRateLimiter(min_interval=1.5, max_jitter=0.8)
