import redis.asyncio as aioredis
from app.core.config import settings

redis_pool = None

async def get_redis_client() -> aioredis.Redis:
    global redis_pool
    if redis_pool is None:
        redis_pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20
        )
    return aioredis.Redis(connection_pool=redis_pool)

async def close_redis():
    global redis_pool
    if redis_pool:
        await redis_pool.disconnect()
