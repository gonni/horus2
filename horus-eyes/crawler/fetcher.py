import httpx
import logging
from typing import Optional
from crawler.config import config
from crawler.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

class ContentFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=config.REQUEST_TIMEOUT,
            follow_redirects=True
        )

    async def fetch_html(self, url: str) -> Optional[str]:
        # 저속 크롤링 레이트 리미터 적용 (TPS <= 1.0 보장)
        await rate_limiter.acquire(url)

        # 1. curl_cffi TLS 브라우저 지문 위장 (Chrome 124) 우선 사용 (Akamai, Cloudflare 403 차단 우회)
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124", timeout=config.REQUEST_TIMEOUT) as session:
                res = await session.get(url)
                if res.status_code == 200 and len(res.text) > 50:
                    # 인코딩 자동 처리 (euc-kr / cp949 / utf-8)
                    return res.text
        except Exception as ce:
            logger.debug(f"curl_cffi fetch error, trying httpx fallback: {ce}")

        # 2. httpx 폴백
        try:
            res = await self.client.get(url)
            if res.status_code == 200:
                return res.text
            logger.warning(f"HTTP {res.status_code} for URL: {url}")
            return None
        except Exception as e:
            logger.error(f"Fetch failed for {url}: {e}")
            return None

    async def fetch_dynamic_html(self, url: str, wait_selector: Optional[str] = None) -> Optional[str]:
        """
        Playwright를 이용한 SPA / 무한스크롤 동적 페이지 렌더링 (저속 리미터 적용)
        """
        await rate_limiter.acquire(url)
        from playwright.async_api import async_playwright
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=config.USER_AGENT)
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=int(config.REQUEST_TIMEOUT * 1000))
                if wait_selector:
                    await page.wait_for_selector(wait_selector, timeout=5000)
                content = await page.content()
                await browser.close()
                return content
        except Exception as e:
            logger.error(f"Dynamic fetch failed for {url}: {e}")
            return None

    async def close(self):
        await self.client.aclose()

