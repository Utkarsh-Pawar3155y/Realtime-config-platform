import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ccms"
)

# SQLAlchemy expects postgresql:// instead of postgres:// if copied from some platforms
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379"
)

# If the redis connection string has redis-cli command format (pasted by mistake), clean it up
if "redis://" in REDIS_URL and not REDIS_URL.startswith("redis://") and not REDIS_URL.startswith("rediss://"):
    # extract the url part
    import re
    match = re.search(r'(redis[s]?://[^\s]+)', REDIS_URL)
    if match:
        REDIS_URL = match.group(1)

# If upstash domain is detected and it uses redis://, upgrade to rediss:// for TLS
if "upstash.io" in REDIS_URL and REDIS_URL.startswith("redis://"):
    REDIS_URL = REDIS_URL.replace("redis://", "rediss://", 1)

CCMS_URL = os.getenv(
    "CCMS_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173"
).rstrip("/")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
