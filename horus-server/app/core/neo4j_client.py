from neo4j import AsyncGraphDatabase
from app.core.config import settings

_neo4j_driver = None

def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
            max_connection_pool_size=50
        )
    return _neo4j_driver

async def close_neo4j():
    global _neo4j_driver
    if _neo4j_driver:
        await _neo4j_driver.close()
