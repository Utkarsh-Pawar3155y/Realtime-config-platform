import logging
import ssl
import redis
from app.config import REDIS_URL

logger = logging.getLogger(__name__)

# Configure redis connection with robust SSL parameters for Upstash / cloud Redis
connection_kwargs = {
    "decode_responses": True,
    "socket_timeout": 5,
    "socket_connect_timeout": 5,
    "retry_on_timeout": True
}

if REDIS_URL.startswith("rediss://"):
    connection_kwargs["ssl_cert_reqs"] = None

try:
    redis_client = redis.Redis.from_url(
        REDIS_URL,
        **connection_kwargs
    )
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {e}")
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def get_redis_client():
    return redis_client
