import redis
from app.core.config import get_settings

def get_redis_client():
    settings = get_settings()
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
    )

def check_redis_health() -> bool:
    try:
        client = get_redis_client()
        return bool(client.ping())
    except Exception:
        return False