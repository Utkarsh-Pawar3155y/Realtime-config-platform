import logging
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import FRONTEND_URL, ENVIRONMENT
from app.database import engine
from app.redis_client import redis_client

from app.service_routes import router as service_router
from app.config_routes import router as config_router
from app.config_change_routes import router as config_change_router
from app.rollback_routes import router as rollback_router
from app.approval_routes import router as approval_router
from app.dashboard_routes import router as dashboard_router
from app.agent_routes import router as agent_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ccms")

app = FastAPI(
    title="Real-Time Configuration Management Platform (CCMS)",
    version="2.0.0",
    description="Centralized configuration management with real-time push distribution and agent synchronization."
)

# Configure CORS for both production frontend and local development
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

if FRONTEND_URL and FRONTEND_URL not in allowed_origins:
    allowed_origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allow Vercel preview/production deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(service_router)
app.include_router(config_router)
app.include_router(config_change_router)
app.include_router(rollback_router)
app.include_router(approval_router)
app.include_router(dashboard_router)
app.include_router(agent_router)


@app.get("/")
def root():
    return {
        "service": "Real-Time Configuration Management Platform (CCMS)",
        "version": "2.0.0",
        "status": "running",
        "environment": ENVIRONMENT
    }


@app.get("/health")
def health(response: Response):
    postgres_status = "ok"
    redis_status = "ok"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {e}")
        postgres_status = "failed"

    try:
        redis_client.ping()
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = "failed"

    is_healthy = (postgres_status == "ok" and redis_status == "ok")

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "postgres": postgres_status,
        "redis": redis_status,
        "environment": ENVIRONMENT
    }