#main.py 
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.routers.advertisements import router as advertisements_router
from app.api.v1.routers.advertisers import router as advertisers_router
from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.channels import router as channels_router
from app.api.v1.routers.detections import router as detections_router
from app.api.v1.routers.reports import router as reports_router
from app.api.v1.routers.users import router as users_router
from app.core.config import get_settings
from app.core.logging import RequestLoggingMiddleware, setup_logging
from app.core.metrics import http_requests_total, router as metrics_router
from app.infrastructure.cache.redis_client import check_redis_health
from app.infrastructure.db import base  # noqa: F401
from app.infrastructure.db.session import SessionLocal

settings = get_settings()
setup_logging()
logger = logging.getLogger("dtv.main")

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(users_router, prefix=settings.api_v1_prefix)
app.include_router(channels_router, prefix=settings.api_v1_prefix)
app.include_router(advertisers_router, prefix=settings.api_v1_prefix)
app.include_router(advertisements_router, prefix=settings.api_v1_prefix)
app.include_router(detections_router, prefix=settings.api_v1_prefix)
app.include_router(reports_router, prefix=settings.api_v1_prefix)
app.include_router(metrics_router)


@app.on_event("startup")
def startup_event():
    Path(settings.local_upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.screenshot_output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.clip_output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.temp_audio_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.local_storage_base_dir).mkdir(parents=True, exist_ok=True)
    logger.info("startup_directories_ready")


@app.middleware("http")
async def metrics_middleware(request, call_next):
    http_requests_total.inc()
    response = await call_next(request)
    return response


@app.get("/")
def root():
    return {
        "message": "DTV-Ad Monitor API is running",
        "environment": settings.app_env,
        "worker_mode": "separate_processes_expected",
    }

@app.get("/health")
def root_health():
    return health()

@app.get(f"{settings.api_v1_prefix}/health")
def health():
    db_ok = False
    db_error = None

    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            db_ok = True
    except Exception as exc:
        db_error = str(exc)

    redis_ok = check_redis_health()

    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "services": {
            "database": {
                "healthy": db_ok,
                "error": db_error,
            },
            "redis": {
                "healthy": redis_ok,
            },
            "storage": {
                "healthy": True,
                "backend": settings.storage_mode,
            },
        },
        "workers": {
            "note": "Workers run separately from the FastAPI API process",
        },
        "metrics": {
            "storage_backend": settings.storage_mode,
        },
    }