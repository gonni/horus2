import logging
import psycopg2
from datetime import datetime, timedelta
from pipeline.tokenizer import tokenizer
from pipeline.cooccurrence import GraphBuilder
from pipeline.timeseries_tf import TimeseriesTFAggregator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_URL = "postgresql://horus:horus_secret@localhost:5432/horus"
NEO4J_URI = "bolt://localhost:7687"

def process_nlp_cycle():
    logger.info("Starting HorusNLP processing cycle (Lightweight Spark replacement)...")
    
    # 1. 최근 기사 가져오기
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, source_id, title, content, published_at 
            FROM articles 
            WHERE crawled_at >= NOW() - INTERVAL '2 hours'
            ORDER BY published_at DESC LIMIT 500;
        """)
        articles = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to fetch articles from DB: {e}")
        return

    if not articles:
        logger.info("No recent articles to process.")
        return

    logger.info(f"Loaded {len(articles)} recent articles for NLP analysis.")

    # 2. Kiwi 형태소 토큰화 (C++ 고속 실행)
    tokenized_docs = []
    for art in articles:
        art_id, source_id, title, content, pub_at = art
        full_text = f"{title} {content}"
        nouns = tokenizer.extract_nouns(full_text)
        tokenized_docs.append(nouns)

    # 3. 실시간 단어 빈도 -> TimescaleDB 적재
    tf_aggregator = TimeseriesTFAggregator(DB_URL)
    tf_aggregator.aggregate_and_insert(source_id=1, tokenized_docs=tokenized_docs)

    # 4. 단어 동시출현망 -> Neo4j 적재
    graph_builder = GraphBuilder(NEO4J_URI)
    cooccurrences = graph_builder.calculate_cooccurrences(tokenized_docs, min_count=2)
    graph_builder.sync_to_neo4j(cooccurrences)
    graph_builder.close()

    logger.info("HorusNLP processing cycle completed successfully.")

if __name__ == "__main__":
    process_nlp_cycle()
