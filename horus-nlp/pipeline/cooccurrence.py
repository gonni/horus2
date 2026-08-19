import logging
from itertools import combinations
from collections import Counter
from typing import List, Dict, Tuple
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class GraphBuilder:
    def __init__(self, neo4j_uri: str = "bolt://localhost:7687", auth: Tuple[str, str] = ("neo4j", "horus_graph")):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=auth)

    def calculate_cooccurrences(self, tokenized_docs: List[List[str]], min_count: int = 2) -> Dict[Tuple[str, str], int]:
        """
        문서 집합 내에서 단어 동시출현(Co-occurrence) 빈도 고속 집계
        """
        pair_counter = Counter()
        for doc_tokens in tokenized_docs:
            unique_tokens = list(set(doc_tokens))
            if len(unique_tokens) < 2:
                continue
            for w1, w2 in combinations(sorted(unique_tokens), 2):
                pair_counter[(w1, w2)] += 1

        return {pair: count for pair, count in pair_counter.items() if count >= min_count}

    def sync_to_neo4j(self, cooccurrences: Dict[Tuple[str, str], int]):
        """
        Neo4j에 지식 그래프 엣지 벌크 적재 (Cypher MERGE)
        """
        if not cooccurrences:
            logger.info("No co-occurrences to sync.")
            return

        cypher_query = """
        UNWIND $batch AS item
        MERGE (k1:Keyword {name: item.source})
        MERGE (k2:Keyword {name: item.target})
        MERGE (k1)-[r:CO_OCCURS_WITH]->(k2)
        SET r.weight = item.weight, r.updated_at = datetime()
        """

        batch_data = [
            {"source": pair[0], "target": pair[1], "weight": count}
            for pair, count in cooccurrences.items()
        ]

        try:
            with self.driver.session() as session:
                session.run(cypher_query, batch=batch_data)
            logger.info(f"Successfully synced {len(batch_data)} word pairs to Neo4j graph.")
        except Exception as e:
            logger.error(f"Neo4j sync failed: {e}")

    def close(self):
        self.driver.close()
