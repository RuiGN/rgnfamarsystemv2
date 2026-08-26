from functools import lru_cache

import redis
from django.conf import settings


@lru_cache(maxsize=1)
def get_knowledge_redis():
    return redis.Redis.from_url(
        settings.KNOWLEDGE_REDIS_URL,
        decode_responses=False,
        health_check_interval=30,
        max_connections=settings.KNOWLEDGE_REDIS_MAX_CONNECTIONS,
        socket_connect_timeout=3,
        socket_timeout=5,
    )


def knowledge_redis_health():
    client = get_knowledge_redis()
    return {
        'available': bool(client.ping()),
        'prefix': settings.KNOWLEDGE_REDIS_PREFIX,
    }
