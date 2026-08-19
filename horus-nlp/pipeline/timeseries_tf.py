import logging
from datetime import datetime
from collections import Counter
from typing import List, Dict
import psycopg2
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)

class TimeseriesTFAggregator:
    def __init__(self, db_url: str = "postgresql://horus:horus_secret@localhost:5432/horus"):
        self.db_url = db_url

    def aggregate_and_insert(self, source_id: int, tokenized_docs: List[List[str]], timestamp: datetime = None):
        """
        단어 출현 빈도(TF)를 집계하여 TimescaleDB에 벌크 인서트
        """
        if not tokenized_docs:
            return

        ts = timestamp or datetime.now()
        term_counter = Counter()
        doc_counter = Counter()

        for doc in tokenized_docs:
            for term in doc:
                term_counter[term] += 1
            for unique_term in set(doc):
                doc_counter[unique_term] += 1

        records = [
            (ts, source_id, term, freq, doc_counter[term])
            for term, freq in term_counter.most_common(100) # 상위 100개 단어
        ]

        if not records:
            return

        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            query = """
                INSERT INTO term_frequencies (time, source_id, term, frequency, doc_count)
                VALUES %s
            """
            execute_values(cursor, query, records)
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"Inserted {len(records)} term frequency records into TimescaleDB.")
        except Exception as e:
            logger.error(f"Failed to insert into TimescaleDB: {e}")
