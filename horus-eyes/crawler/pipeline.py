import asyncio
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text

from crawler.config import config
from crawler.fetcher import ContentFetcher
from crawler.extractor import AIExtractor, ExtractedArticle

logger = logging.getLogger(__name__)

class CrawlPipeline:
    def __init__(self):
        self.fetcher = ContentFetcher()
        self.extractor = AIExtractor()
        self.engine = create_async_engine(config.SQLALCHEMY_DATABASE_URI)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def run_source_crawl(self, source_id: int, base_url: str, hints: Optional[dict] = None, max_articles: int = 5):
        logger.info(f"Starting crawl for source #{source_id}: {base_url}")
        
        # 1. 목록 페이지 가져오기
        list_html = await self.fetcher.fetch_html(base_url)
        if not list_html:
            logger.error(f"Failed to fetch list page: {base_url}")
            return

        # 2. 링크 추출 (Seed에 설정된 link_selector 힌트 전달)
        link_selector = hints.get("link_selector") if hints else None
        article_urls = self._extract_links(base_url, list_html, link_selector=link_selector)
        logger.info(f"Found {len(article_urls)} candidate links. Processing top {max_articles}...")

        # 3. 각 기사 수집 & AI 구조화 추출
        for url in article_urls[:max_articles]:
            try:
                await self._process_single_article(source_id, url, hints)
            except Exception as e:
                logger.error(f"Error processing article {url}: {e}")

    def extract_links_with_meta(self, base_url: str, html: str, link_selector: Optional[str] = None) -> List[dict]:
        """
        목록 페이지 HTML에서 기사 링크 및 앵커 텍스트, 리드문(스니펫), 언론사/작성자, 시간, 썸네일 등 메타정보를 함께 추출합니다.
        """
        soup = BeautifulSoup(html, "html.parser")
        items = []
        seen_urls = set()

        def _clean_text(elem) -> Optional[str]:
            if not elem:
                return None
            t = elem.get_text(separator=" ", strip=True)
            return t if t else None

        # 1. 커스텀 CSS Selector가 지정된 경우
        if link_selector and isinstance(link_selector, str) and link_selector.strip():
            clean_sel = link_selector.strip()
            try:
                selected_elems = soup.select(clean_sel)
                for elem in selected_elems:
                    a_tag = elem if elem.name == "a" else elem.find("a")
                    if not a_tag or not a_tag.get("href"):
                        continue
                    href = a_tag["href"]
                    full_url = urljoin(base_url, href)
                    if not full_url.startswith("http") or full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    # 메타데이터 탐색 (부모 컨테이너 탐색)
                    container = elem.find_parent(["li", "tr", "div", "article"]) or elem
                    title = _clean_text(a_tag)
                    
                    # 썸네일 이미지 탐색
                    img = container.find("img")
                    thumbnail = urljoin(base_url, img.get("src") or img.get("data-src")) if (img and (img.get("src") or img.get("data-src"))) else None

                    # 스니펫 탐색
                    snippet_elem = container.find(class_=lambda c: c and any(k in c.lower() for k in ["lede", "desc", "snippet", "summary", "content"]))
                    snippet = _clean_text(snippet_elem)

                    # 출처/언론사/작성자 탐색
                    press_elem = container.find(class_=lambda c: c and any(k in c.lower() for k in ["press", "source", "author", "writer", "nick", "media"]))
                    press = _clean_text(press_elem)

                    # 시간/날짜 탐색
                    time_elem = container.find(class_=lambda c: c and any(k in c.lower() for k in ["date", "time", "stamp", "when"])) or container.find("time")
                    time_text = _clean_text(time_elem)

                    items.append({
                        "url": full_url,
                        "title": title,
                        "anchor_text": title,
                        "snippet": snippet,
                        "press": press,
                        "time_text": time_text,
                        "thumbnail": thumbnail
                    })

                if items:
                    logger.info(f"Extracted {len(items)} rich link items using custom selector '{clean_sel}'")
                    return items
            except Exception as e:
                logger.warning(f"Invalid custom selector '{clean_sel}': {e}")

        # 2. 네이버 뉴스 표준 구조 자동 감지 (.sa_item / .sa_text)
        naver_cards = soup.select(".sa_item, .sa_text, .sh_item, ul.type06_headline li, ul.type06 li")
        if naver_cards:
            for card in naver_cards:
                a_tag = card.select_one(".sa_text_title, .sh_text_headline, a[href*='article'], a[href*='news']")
                if not a_tag or not a_tag.get("href"):
                    continue
                href = a_tag["href"]
                full_url = urljoin(base_url, href)
                if not full_url.startswith("http") or full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                title = _clean_text(a_tag)
                snippet = _clean_text(card.select_one(".sa_text_lede, .lede, .sh_text_lede"))
                press = _clean_text(card.select_one(".sa_text_press, .writing, .sh_text_press"))
                time_text = _clean_text(card.select_one(".sa_text_datetime, .date, .time"))
                
                img_tag = card.select_one("img.sa_thumb_inner, img")
                thumbnail = None
                if img_tag:
                    raw_src = img_tag.get("src") or img_tag.get("data-src")
                    if raw_src:
                        thumbnail = urljoin(base_url, raw_src)

                items.append({
                    "url": full_url,
                    "title": title,
                    "anchor_text": title,
                    "snippet": snippet,
                    "press": press,
                    "time_text": time_text,
                    "thumbnail": thumbnail
                })

            if items:
                return items

        # 3. 클리앙 커뮤니티 구조 (.list_item)
        clien_rows = soup.select(".list_item, .list_content")
        if clien_rows:
            for row in clien_rows:
                a_tag = row.select_one("a.list_subject, a.subject_fixed, a[href*='/service/board/']")
                if not a_tag or not a_tag.get("href"):
                    continue
                href = a_tag["href"]
                full_url = urljoin(base_url, href)
                if not full_url.startswith("http") or full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                title = _clean_text(a_tag)
                press = _clean_text(row.select_one(".nickname, .author"))
                time_text = _clean_text(row.select_one(".timestamp, .time"))
                
                items.append({
                    "url": full_url,
                    "title": title,
                    "anchor_text": title,
                    "snippet": None,
                    "press": press,
                    "time_text": time_text,
                    "thumbnail": None
                })
            if items:
                return items

        # 4. 뽐뿌 / 일반 테이블 게시판 구조 (tr, td)
        table_rows = soup.select("tr.list0, tr.list1, tr[align='center'], tr")
        for row in table_rows:
            a_tag = row.select_one("a[href*='view'], a[href*='zboard'], a[href*='article'], a[href*='board']")
            if not a_tag or not a_tag.get("href"):
                continue
            href = a_tag["href"]
            full_url = urljoin(base_url, href)
            if not full_url.startswith("http") or full_url in seen_urls:
                continue
            if any(k in full_url for k in ["comment", "login", "auth", "member", "javascript"]):
                continue

            seen_urls.add(full_url)
            title = _clean_text(a_tag)
            if not title or len(title) < 2:
                continue

            author = _clean_text(row.select_one(".list_name, .author, span.user"))
            date_col = _clean_text(row.select_one("td.eng, .date, .time"))

            items.append({
                "url": full_url,
                "title": title,
                "anchor_text": title,
                "snippet": None,
                "press": author,
                "time_text": date_col,
                "thumbnail": None
            })

        if items:
            return items

        # 5. 범용 스마트 링크 탐색 Fallback
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(base_url, href)
            if not full_url.startswith("http") or full_url in seen_urls:
                continue
            if any(k in full_url for k in ["article", "news", "view", "read", "board", "post", "id="]):
                if not any(k in full_url for k in ["comment", "login", "auth", "share", "tag", "category"]):
                    seen_urls.add(full_url)
                    title = _clean_text(a_tag)
                    items.append({
                        "url": full_url,
                        "title": title,
                        "anchor_text": title,
                        "snippet": None,
                        "press": None,
                        "time_text": None,
                        "thumbnail": None
                    })
        return items

    def _extract_links(self, base_url: str, html: str, link_selector: Optional[str] = None) -> List[str]:
        items = self.extract_links_with_meta(base_url, html, link_selector=link_selector)
        return [item["url"] for item in items]

    async def _process_single_article(self, source_id: int, url: str, hints: Optional[dict]):
        # 이미 수집된 URL인지 확인
        async with self.session_factory() as session:
            check_stmt = text("SELECT id FROM articles WHERE url = :url LIMIT 1")
            res = await session.execute(check_stmt, {"url": url})
            if res.scalar_one_or_none():
                logger.info(f"Article already exists in DB: {url}")
                return

        # 본문 HTML 다운로드
        raw_html = await self.fetcher.fetch_html(url)
        if not raw_html:
            return

        # AI 구조화 추출
        article_data: Optional[ExtractedArticle] = await self.extractor.extract_structured(url, raw_html, hints)
        if not article_data:
            logger.warning(f"AI Extraction yielded no result for: {url}")
            return

        # PostgreSQL 적재
        async with self.session_factory() as session:
            insert_stmt = text("""
                INSERT INTO articles (source_id, url, title, content, summary, author, published_at, category, sentiment_score, metadata)
                VALUES (:source_id, :url, :title, :content, :summary, :author, :published_at, :category, :sentiment_score, CAST(:metadata AS jsonb))
                ON CONFLICT (url, published_at) DO NOTHING
            """)
            await session.execute(insert_stmt, {
                "source_id": source_id,
                "url": url,
                "title": article_data.title,
                "content": article_data.content,
                "summary": article_data.summary,
                "author": article_data.author,
                "published_at": article_data.published_at,
                "category": article_data.category,
                "sentiment_score": article_data.sentiment_score,
                "metadata": '{"entities": ' + str(article_data.key_entities).replace("'", '"') + '}'
            })
            await session.commit()
            logger.info(f"Successfully saved article: {article_data.title}")

    async def close(self):
        await self.fetcher.close()
        await self.engine.dispose()
