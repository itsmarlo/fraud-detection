from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.config import get_settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "OK",
        "service": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(UTC).isoformat(),
    }
