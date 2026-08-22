import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from crawler.config import config
from crawler.pipeline import CrawlPipeline
from crawler.backfiller import backfill_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def run_live_crawl(max_articles: int = 5):
    logger.info("Starting HorusEyes AI Crawler Live Cycle (Slow-rate TPS < 1.0)...")
    pipeline = CrawlPipeline()
    engine = create_async_engine(config.SQLALCHEMY_DATABASE_URI)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            stmt = text("SELECT id, name, base_url, ai_parsing_hints FROM crawl_sources WHERE is_active = true")
            result = await session.execute(stmt)
            sources = result.fetchall()

        logger.info(f"Loaded {len(sources)} active crawl sources.")
        for src in sources:
            source_id, name, base_url, hints = src
            logger.info(f"Triggering slow crawl for: {name} ({base_url})")
            await pipeline.run_source_crawl(source_id, base_url, hints=hints, max_articles=max_articles)

    except Exception as e:
        logger.error(f"Crawler live execution failed: {e}")
    finally:
        await pipeline.close()
        await engine.dispose()
        logger.info("HorusEyes Live Crawler cycle finished.")

def main():
    parser = argparse.ArgumentParser(description="HorusEyes AI Crawler & Backfill Engine")
    parser.add_argument("--mode", type=str, choices=["live", "backfill"], default="live", help="Execution mode")
    parser.add_argument("--start", type=str, default=None, help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="Backfill end date (YYYY-MM-DD)")
    parser.add_argument("--section", type=str, default="economy", help="Backfill Naver section (economy, tech, society, etc.)")
    parser.add_argument("--max-articles", type=int, default=5, help="Max articles per source/day")
    args = parser.parse_args()

    if args.mode == "backfill":
        start = args.start or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        end = args.end or datetime.now().strftime("%Y-%m-%d")
        logger.info(f"Running Backfill Mode: {start} ~ {end} (Section: {args.section})")
        asyncio.run(backfill_manager.run_backfill(
            start_date=start,
            end_date=end,
            section=args.section,
            max_articles_per_day=args.max_articles
        ))
    else:
        asyncio.run(run_live_crawl(max_articles=args.max_articles))

if __name__ == "__main__":
    import sys
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n[HorusEyes] Crawler stopped by user (Ctrl+C). Exiting cleanly.")
        sys.exit(0)
