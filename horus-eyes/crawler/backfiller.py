import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from crawler.config import config
from crawler.fetcher import ContentFetcher
from crawler.extractor import AIExtractor, ExtractedArticle
from crawler.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

# 네이버 뉴스 주요 섹션 ID
NAVER_SECTIONS = {
    "economy": "101",      # 경제
    "tech": "105",         # IT/과학
    "society": "102",      # 사회
    "politics": "100",     # 정치
    "world": "104"         # 세계
}

class BackfillManager:
    """
    네이버 뉴스 및 주요 언론사 과거 누락 일자 복구(Backfill) 전용 엔진
    - 시작일(start_date) ~ 종료일(end_date) 날짜별 아카이브 순회
    - TPS < 1.0 저속 안전 크롤링
    - 기수집 기사 자동 스킵 (중복 방지)
    """
    def __init__(self):
        self.fetcher = ContentFetcher()
        self.extractor = AIExtractor()
        self.engine = create_async_engine(config.SQLALCHEMY_DATABASE_URI)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.is_running = False
        self.progress: Dict[str, Any] = {
            "status": "idle",
            "current_date": None,
            "total_days": 0,
            "processed_days": 0,
            "saved_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "current_tps": 0.0,
            "last_message": "대기 중"
        }

    async def run_backfill(
        self,
        start_date: str,
        end_date: str,
        section: str = "economy",
        max_pages_per_day: int = 5,
        max_articles_per_day: int = 30
    ):
        """
        예: start_date="2026-08-01", end_date="2026-08-15", section="economy"
        """
        self.is_running = True
        sec_id = NAVER_SECTIONS.get(section, "101")
        
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            self.progress["status"] = "error"
            self.progress["last_message"] = f"날짜 형식 오류: {e}"
            return

        total_days = (end_dt - start_dt).days + 1
        self.progress.update({
            "status": "running",
            "total_days": total_days,
            "processed_days": 0,
            "saved_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "last_message": f"{start_date} ~ {end_date} 백필 시작"
        })

        logger.info(f"Starting Backfill for Naver News ({section} / sid1={sec_id}) from {start_date} to {end_date} ({total_days} days)")

        curr_dt = start_dt
        while curr_dt <= end_dt and self.is_running:
            date_str = curr_dt.strftime("%Y%m%d")
            display_date = curr_dt.strftime("%Y-%m-%d")
            self.progress["current_date"] = display_date
            self.progress["last_message"] = f"[{display_date}] 기사 목록 탐색 중..."

            day_saved = 0
            for page in range(1, max_pages_per_day + 1):
                if not self.is_running or day_saved >= max_articles_per_day:
                    break

                list_url = f"https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1={sec_id}&date={date_str}&page={page}"
                logger.info(f"Fetching Naver Archive: {list_url}")
                
                html = await self.fetcher.fetch_html(list_url)
                if not html:
                    continue

                links = self._extract_naver_archive_links(html)
                if not links:
                    logger.info(f"No more links on date {date_str} page {page}. Moving to next day.")
                    break

                for article_url in links:
                    if not self.is_running or day_saved >= max_articles_per_day:
                        break

                    saved = await self._process_article(article_url, category=section)
                    if saved:
                        day_saved += 1
                        self.progress["saved_count"] += 1
                    self.progress["current_tps"] = rate_limiter.current_tps

            self.progress["processed_days"] += 1
            curr_dt += timedelta(days=1)
            logger.info(f"Completed backfill for {display_date}. (Day saved: {day_saved}, Total saved: {self.progress['saved_count']})")

        self.progress["status"] = "completed" if self.is_running else "stopped"
        self.progress["last_message"] = f"백필 작업 완료: 총 {self.progress['saved_count']}건 수집, {self.progress['skipped_count']}건 기등록 스킵."
        self.is_running = False
        logger.info("Backfill task ended.")

    def stop(self):
        self.is_running = False
        self.progress["status"] = "stopped"
        self.progress["last_message"] = "사용자에 의해 백필 작업이 중지되었습니다."

    def _extract_naver_archive_links(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links = []
        
        # 1. 네이버 뉴스 아카이브 메인 목록 영역 (.list_body, ul.type06_headline, ul.type06)
        list_containers = soup.select(".list_body ul li dt a, .list_body ul li dl dt:not(.photo) a")
        for a in list_containers:
            href = a.get("href")
            if href and "article" in href:
                full = urljoin("https://news.naver.com", href)
                if full not in links:
                    links.append(full)

        # 2. 일반 링크 폴백
        if not links:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/article/" in href or "article.naver" in href:
                    full = urljoin("https://news.naver.com", href)
                    if full not in links:
                        links.append(full)

        return links

    async def _process_article(self, url: str, category: str) -> bool:
        # 1. 기수집 URL 체크
        try:
            async with self.session_factory() as session:
                check_stmt = text("SELECT id FROM articles WHERE url = :url LIMIT 1")
                res = await session.execute(check_stmt, {"url": url})
                if res.scalar_one_or_none():
                    self.progress["skipped_count"] += 1
                    return False
        except Exception as e:
            logger.error(f"DB check failed: {e}")

        # 2. 본문 다운로드 (RateLimiter 자동 적용)
        html = await self.fetcher.fetch_html(url)
        if not html:
            self.progress["error_count"] += 1
            return False

        # 3. 데이터 구조화 추출
        article_data: Optional[ExtractedArticle] = await self.extractor.extract_structured(
            url, html, hints={"category": category}
        )
        if not article_data or len(article_data.content) < 30:
            self.progress["error_count"] += 1
            return False

        # 4. PostgreSQL 적재
        try:
            async with self.session_factory() as session:
                insert_stmt = text("""
                    INSERT INTO articles (source_id, url, title, content, summary, author, published_at, category, sentiment_score, metadata)
                    VALUES (:source_id, :url, :title, :content, :summary, :author, :published_at, :category, :sentiment_score, CAST(:metadata AS jsonb))
                    ON CONFLICT (url, published_at) DO NOTHING
                """)
                await session.execute(insert_stmt, {
                    "source_id": 1,
                    "url": url,
                    "title": article_data.title,
                    "content": article_data.content,
                    "summary": article_data.summary,
                    "author": article_data.author,
                    "published_at": article_data.published_at,
                    "category": category,
                    "sentiment_score": article_data.sentiment_score,
                    "metadata": '{"backfilled": true, "entities": ' + str(article_data.key_entities).replace("'", '"') + '}'
                })
                await session.commit()
                logger.info(f"[Backfill Saved] {article_data.title[:35]}... ({article_data.published_at.strftime('%Y-%m-%d')})")
                return True
        except Exception as e:
            logger.error(f"Failed to insert backfilled article: {e}")
            self.progress["error_count"] += 1
            return False

    async def close(self):
        await self.fetcher.close()
        await self.engine.dispose()

backfill_manager = BackfillManager()
