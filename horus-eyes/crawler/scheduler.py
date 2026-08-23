import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text, bindparam


from crawler.config import config
from crawler.fetcher import ContentFetcher
from crawler.extractor import AIExtractor, ExtractedArticle
from crawler.pipeline import CrawlPipeline
from crawler.smart_collectors import (
    USMarketSignalCollector,
    CommunitySpikeCollector,
    ThreadsCollector,
    SmartAutoSeedCollector,
    TopicGraphCollector
)

logger = logging.getLogger(__name__)

class CrawlSchedulerDaemon:
    """
    모든 활성 Seed(CrawlSource)를 주기적(기본 60초)으로 폴링하여,
    DB에 없는 신규 글만 탐색하여 고속 적재(0% GPU)하는 실시간 연속 크롤링 데몬
    """
    def __init__(self):
        self.engine = create_async_engine(config.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.fetcher = ContentFetcher()
        self.extractor = AIExtractor()
        self.pipeline = CrawlPipeline()

        # 지능형 5대 수집기 엔진 초기화
        self.us_market_collector = USMarketSignalCollector(self.fetcher)
        self.community_spike_collector = CommunitySpikeCollector(self.fetcher)
        self.threads_collector = ThreadsCollector(self.fetcher)
        self.smart_auto_seed_collector = SmartAutoSeedCollector(self.fetcher)
        self.topic_graph_collector = TopicGraphCollector(self.fetcher)


        self.state: str = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED
        self.interval_seconds: int = 60  # 기본 60초 (1분)
        self._task: Optional[asyncio.Task] = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        # 실시간 모니터링 통계
        self.cycle_count: int = 0
        self.total_ingested_articles: int = 0
        self.total_scanned_seeds: int = 0
        self.last_cycle_started_at: Optional[datetime] = None
        self.last_cycle_finished_at: Optional[datetime] = None
        self.next_run_at: Optional[datetime] = None
        self.current_running_seed_name: Optional[str] = None
        self.last_error_message: Optional[str] = None

    async def start(self, interval_seconds: Optional[int] = None):
        if interval_seconds:
            self.interval_seconds = max(10, min(interval_seconds, 3600))

        if self.state == "PAUSED":
            self.resume()
            return

        if self._task and not self._task.done():
            logger.info("Crawl Scheduler Daemon is already running.")
            return

        self.state = "RUNNING"
        self._pause_event.set()
        self._task = asyncio.create_task(self._daemon_loop())
        logger.info(f"Crawl Scheduler Daemon STARTED with interval {self.interval_seconds}s")

    def pause(self):
        if self.state == "RUNNING":
            self.state = "PAUSED"
            self._pause_event.clear()
            logger.info("Crawl Scheduler Daemon PAUSED.")

    def resume(self):
        if self.state == "PAUSED":
            self.state = "RUNNING"
            self._pause_event.set()
            logger.info("Crawl Scheduler Daemon RESUMED.")

    async def stop(self):
        self.state = "STOPPED"
        self._pause_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Crawl Scheduler Daemon STOPPED.")

    def set_interval(self, interval_seconds: int):
        self.interval_seconds = max(10, min(interval_seconds, 3600))
        logger.info(f"Crawl interval updated to {self.interval_seconds}s")

    async def _daemon_loop(self):
        while self.state in ["RUNNING", "PAUSED"]:
            await self._pause_event.wait()
            if self.state == "STOPPED":
                break

            self.last_cycle_started_at = datetime.now()
            self.next_run_at = self.last_cycle_started_at + timedelta(seconds=self.interval_seconds)
            self.cycle_count += 1

            try:
                logger.info(f"=== Starting Crawl Cycle #{self.cycle_count} (Interval: {self.interval_seconds}s) ===")
                await self._run_cycle()
                self.last_cycle_finished_at = datetime.now()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in crawl cycle #{self.cycle_count}: {e}")
                self.last_error_message = str(e)

            # 대기 루프 (일시정지 및 인터벌 반영)
            sleep_remaining = max(1.0, (self.next_run_at - datetime.now()).total_seconds())
            while sleep_remaining > 0 and self.state == "RUNNING":
                await asyncio.sleep(min(1.0, sleep_remaining))
                sleep_remaining = (self.next_run_at - datetime.now()).total_seconds()

    async def _crawl_single_seed_safe(self, src):
        if self.state != "RUNNING":
            return
        await self._pause_event.wait()
        source_id, name, base_url, hints = src
        try:
            await self._crawl_single_seed(source_id, name, base_url, hints or {})
        except Exception as e:
            logger.error(f"Error crawling seed '{name}' ({base_url}): {e}")
            self.last_error_message = f"[{name}] {str(e)}"

    async def _run_cycle(self):
        # 1. 활성 소스 목록 로드
        async with self.session_factory() as session:
            stmt = text("SELECT id, name, base_url, ai_parsing_hints FROM crawl_sources WHERE is_active = true ORDER BY id")
            res = await session.execute(stmt)
            sources = res.fetchall()

        if not sources:
            logger.info("No active crawl sources found.")
            return

        self.total_scanned_seeds += len(sources)

        # 🚀 각 Seed(호스트/도메인)별 독립 비동기 병렬 수집 (각 Seed별로 독립 1.0 TPS 실행)
        tasks = [self._crawl_single_seed_safe(src) for src in sources]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _crawl_single_seed(self, source_id: int, name: str, base_url: str, hints: dict):
        collector_type = hints.get("collector_type")
        if base_url.startswith("smart://") or collector_type in ["us_market_signal", "community_spike", "threads_stream", "smart_auto_seed", "topic_graph"]:
            await self._crawl_smart_collector(source_id, name, collector_type or "us_market_signal", base_url, hints)
            return

        logger.info(f"Scanning Seed #{source_id}: {name} ({base_url})")

        # 1. 목록 페이지 HTML 다운로드
        list_html = await self.fetcher.fetch_html(base_url)
        if not list_html:
            logger.warning(f"Failed to fetch list page for {name}")
            return

        # 2. 링크 추출
        link_selector = hints.get("link_selector")
        items = self.pipeline.extract_links_with_meta(base_url, list_html, link_selector=link_selector)
        candidate_urls = [it["url"] for it in items if it.get("url")]

        if not candidate_urls:
            # Fallback 링크 탐색
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(list_html, "html.parser")
            from urllib.parse import urljoin
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if any(k in href for k in ["article", "view", "board", "post", "read", "id="]):
                    full = urljoin(base_url, href)
                    if full.startswith("http") and full not in candidate_urls:
                        candidate_urls.append(full)

        # 3. DB와 Diffing하여 신규 링크만 필터링
        new_urls = await self._filter_new_urls(candidate_urls)
        logger.info(f"Seed '{name}': Found {len(candidate_urls)} candidate links, {len(new_urls)} NEW links to ingest.")

        # Seed 스캔 이벤트 기록
        await self._record_event(source_id, "seed_scan", name, base_url, {
            "candidate_count": len(candidate_urls),
            "new_count": len(new_urls)
        })


        if not new_urls:
            return

        # 4. 신규 기사 순회 수집 (저속 TPS < 1.0, 0% GPU 고속 CPU 파싱)
        for url in new_urls[:10]:  # 1주기당 최대 10건 수집
            if self.state != "RUNNING":
                break
            await self._pause_event.wait()

            try:
                raw_html = await self.fetcher.fetch_html(url)
                if not raw_html:
                    continue

                # 고속 네이티브 파싱 (use_llm=False)
                article_data: Optional[ExtractedArticle] = await self.extractor.extract_structured(url, raw_html, hints=hints, use_llm=False)
                if not article_data or not article_data.content:
                    continue

                # 본문 이미지 및 부가 메타데이터 추출
                native_meta = self.extractor.extract_native_metadata(raw_html, url, hints=hints)
                images = native_meta.get("images", [])

                # DB 적재 (이미지 URL 목록을 articles.metadata['images']에 저장)
                await self._save_article(source_id, url, article_data, images=images)
                self.total_ingested_articles += 1

                # 본문 기사 수집 이벤트 기록
                await self._record_event(source_id, "article_ingest", article_data.title, url, {
                    "author": article_data.author,
                    "published_at": article_data.published_at.isoformat() if article_data.published_at else None,
                    "char_count": len(article_data.content),
                    "image_count": len(images)
                })

                # 본문 이미지 감지 및 이벤트 기록 (실시간 피드 썸네일용)
                if images:
                    for img in images[:3]:
                        await self._record_event(source_id, "image_ingest", f"이미지: {article_data.title[:40]}", url, {
                            "image_url": img
                        }, image_url=img)

            except Exception as e:
                logger.error(f"Error ingesting article {url}: {e}")

            # Safe Rate Limiting (1.5초 대기)
            await asyncio.sleep(1.5)

    async def _crawl_smart_collector(self, source_id: int, name: str, collector_type: str, base_url: str, hints: dict):
        target = hints.get("target_url_or_query") or base_url.replace(f"smart://{collector_type}/", "").replace("smart://", "")
        cfg = hints.get("config", {})
        logger.info(f"Scanning Smart Collector #{source_id}: '{name}' (Type: {collector_type}, Target: {target})")

        # 1. Seed 스캔 이벤트 기록 (차트 상단 녹색 틱 🟢)
        await self._record_event(source_id, "seed_scan", name, target, {
            "collector_type": collector_type,
            "target": target
        })

        results = []
        try:
            if collector_type == "us_market_signal":
                lang = cfg.get("language", "en")
                results = await self.us_market_collector.fetch_signals(query=target, language=lang, max_results=10)
            elif collector_type == "threads_stream":
                mode = cfg.get("mode", "korean_trending")
                lang = cfg.get("language", "ko")
                results = await self.threads_collector.fetch_threads_posts(target=target, mode=mode, language=lang, max_results=10)
            elif collector_type == "community_spike":
                mode = cfg.get("mode", "hot")
                results = await self.community_spike_collector.fetch_reddit_spikes(subreddit=target, mode=mode, limit=10)
            elif collector_type == "smart_auto_seed":
                res = await self.smart_auto_seed_collector.discover_and_extract(seed_url=target, max_articles=5)
                results = res.get("extracted_articles", [])
            elif collector_type == "topic_graph":
                lang = cfg.get("language", "ko")
                res = await self.topic_graph_collector.collect_topic_stream(center_topic=target, language=lang, max_articles=5)
                results = res.get("articles", [])
        except Exception as e:
            logger.error(f"Error executing smart collector #{source_id} '{name}': {e}")
            await self._record_event(source_id, "error", f"오류: {name}", target, {"error": str(e)})
            return

        if not results:
            logger.info(f"Smart Collector '{name}': No items found in this cycle.")
            return

        # 2. DB 중복 대조 (이미 수집된 URL은 Skip)
        candidate_urls = [it.get("url") for it in results if it.get("url")]
        new_urls = await self._filter_new_urls(candidate_urls)
        logger.info(f"Smart Collector '{name}': Found {len(results)} candidate items, {len(new_urls)} NEW to ingest.")

        if not new_urls:
            return

        # 3. 신규 기사 적재 및 이벤트 기록
        for item in results:
            if self.state != "RUNNING":
                break
            await self._pause_event.wait()

            url = item.get("url")
            if not url or url not in new_urls:
                continue

            title = item.get("title") or "무제"
            content = item.get("summary") or item.get("content_preview") or title
            author = item.get("author") or item.get("publisher") or name
            pub_str = item.get("published_at")
            try:
                pub_dt = datetime.fromisoformat(pub_str) if pub_str else datetime.now()
            except Exception:
                pub_dt = datetime.now()

            images = item.get("images", [])
            meta = {
                "collector_type": collector_type,
                "target": target,
                "source_name": name,
                "signals": item.get("signals", []),
                "impact_score": item.get("impact_score", 50),
                "sentiment": item.get("sentiment", "NEUTRAL"),
                "tickers": item.get("tickers", []),
                "images": images,
                "top_comments": item.get("top_comments", []),
                "comment_count": item.get("num_comments", len(item.get("top_comments", [])))
            }

            async with self.session_factory() as session:
                stmt = text("""
                    INSERT INTO articles (source_id, url, title, content, summary, author, published_at, category, sentiment_score, metadata)
                    VALUES (:source_id, :url, :title, :content, :summary, :author, :published_at, 'smart_collect', :sentiment_score, CAST(:metadata AS jsonb))
                    ON CONFLICT (url, published_at) DO NOTHING
                """)
                await session.execute(stmt, {
                    "source_id": source_id,
                    "url": url,
                    "title": title[:500],
                    "content": content,
                    "summary": item.get("summary") or title,
                    "author": author[:100],
                    "published_at": pub_dt,
                    "sentiment_score": (item.get("impact_score", 50) - 50) / 50.0,
                    "metadata": json.dumps(meta, ensure_ascii=False)
                })
                await session.commit()
                self.total_ingested_articles += 1

            # 본문 기사 수집 이벤트 기록 (차트 상 파란 틱 🔵)
            await self._record_event(source_id, "article_ingest", title, url, {
                "author": author,
                "published_at": pub_dt.isoformat(),
                "char_count": len(content),
                "collector_type": collector_type
            })

            # 이미지 수집 이벤트 기록 (차트 상 보라색 틱 🟣)
            if images:
                for img in images[:2]:
                    await self._record_event(source_id, "image_ingest", f"이미지: {title[:40]}", url, {
                        "image_url": img
                    }, image_url=img)

            # Safe Rate Limiting (1.5초 대기)
            await asyncio.sleep(1.5)

    def _canonicalize_url(self, url: str) -> str:

        if not url:
            return ""
        from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
        try:
            parsed = urlparse(url)
            query_params = parse_qsl(parsed.query)
            clean_params = [
                (k, v) for k, v in query_params 
                if not k.startswith("utm_") and k not in ["ref", "rc", "_gl", "source", "sid", "fbclid"]
            ]
            clean_query = urlencode(clean_params)
            clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, ""))
            return clean_url.rstrip("/")
        except Exception:
            return url.strip()

    async def _filter_new_urls(self, urls: List[str]) -> List[str]:
        if not urls:
            return []
        
        # 1. 원본 URL 및 정규화된 URL 목록 준비
        url_candidates = []
        for u in urls:
            if not u:
                continue
            clean = self._canonicalize_url(u)
            url_candidates.append(u)
            if clean and clean != u:
                url_candidates.append(clean)
        
        if not url_candidates:
            return []

        async with self.session_factory() as session:
            # 2. IN :urls 바인드 파라미터로 DB에 이미 존재하는 URL 일괄 조회 (중복 100% 탐지)
            stmt = text("SELECT url FROM articles WHERE url IN :urls").bindparams(
                bindparam("urls", expanding=True)
            )
            res = await session.execute(stmt, {"urls": tuple(set(url_candidates))})
            existing = set(r[0] for r in res.fetchall())
            # 정규화된 기존 URL도 함께 set에 포함
            existing_canon = set(self._canonicalize_url(r) for r in existing)
            existing.update(existing_canon)

        # 3. DB에 이미 존재하는 기사는 100% 필터링(Skip)
        new_urls = []
        seen = set()
        for u in urls:
            canon = self._canonicalize_url(u)
            if u not in existing and canon not in existing and canon not in seen:
                seen.add(canon)
                new_urls.append(u)

        return new_urls


    async def _save_article(self, source_id: int, url: str, data: ExtractedArticle, images: Optional[List[str]] = None):
        async with self.session_factory() as session:
            metadata_dict = {
                "nlp_processed": False,
                "images": images or [],
                "image_count": len(images or [])
            }
            insert_stmt = text("""
                INSERT INTO articles (source_id, url, title, content, summary, author, published_at, category, sentiment_score, metadata)
                VALUES (:source_id, :url, :title, :content, NULL, :author, :published_at, :category, NULL, CAST(:metadata AS jsonb))
                ON CONFLICT (url, published_at) DO NOTHING
            """)
            await session.execute(insert_stmt, {
                "source_id": source_id,
                "url": url,
                "title": data.title,
                "content": data.content,
                "author": data.author,
                "published_at": data.published_at or datetime.now(),
                "category": data.category,
                "metadata": json.dumps(metadata_dict, ensure_ascii=False)
            })
            await session.commit()

    async def _record_event(self, source_id: Optional[int], event_type: str, title: Optional[str], url: Optional[str], details: dict, image_url: Optional[str] = None):
        try:
            async with self.session_factory() as session:
                event_stmt = text("""
                    INSERT INTO crawl_events (source_id, event_type, title, url, image_url, details)
                    VALUES (:source_id, :event_type, :title, :url, :image_url, CAST(:details AS jsonb))
                """)
                await session.execute(event_stmt, {
                    "source_id": source_id,
                    "event_type": event_type,
                    "title": title[:500] if title else None,
                    "url": url,
                    "image_url": image_url,
                    "details": json.dumps(details, ensure_ascii=False)
                })
                await session.commit()
        except Exception as e:
            logger.debug(f"Event recording skipped: {e}")

    def get_status(self) -> Dict[str, Any]:
        seconds_to_next = 0
        if self.next_run_at and self.state == "RUNNING":
            seconds_to_next = max(0, int((self.next_run_at - datetime.now()).total_seconds()))

        return {
            "state": self.state,
            "interval_seconds": self.interval_seconds,
            "seconds_to_next_cycle": seconds_to_next,
            "cycle_count": self.cycle_count,
            "total_ingested_articles": self.total_ingested_articles,
            "total_scanned_seeds": self.total_scanned_seeds,
            "current_running_seed_name": self.current_running_seed_name,
            "last_cycle_started_at": self.last_cycle_started_at.isoformat() if self.last_cycle_started_at else None,
            "last_cycle_finished_at": self.last_cycle_finished_at.isoformat() if self.last_cycle_finished_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_error_message": self.last_error_message
        }

crawl_scheduler = CrawlSchedulerDaemon()
