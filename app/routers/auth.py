from fastapi import APIRouter

from app.auth import get_public_auth_config


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/config", include_in_schema=False)
def auth_config() -> dict[str, str | bool]:
    return get_public_auth_config()
