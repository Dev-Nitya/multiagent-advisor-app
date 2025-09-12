from fastapi import APIRouter, HTTPException, Body
from typing import Dict

from config.prompt_config import is_prompt_sanitization_enabled, set_prompt_sanitization_enabled
from services.user_prefs_service import get_prompt_sanitization_for_user, set_prompt_sanitization_for_user

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/prompt_sanitization", summary="Get app-level prompt sanitization flag")
async def get_prompt_sanitization() -> Dict:
    return {"prompt_sanitization_enabled": is_prompt_sanitization_enabled()}


@admin_router.post("/prompt_sanitization", summary="Set app-level prompt sanitization flag")
async def post_prompt_sanitization(payload: Dict = Body(...)):
    if "enabled" not in payload:
        raise HTTPException(status_code=400, detail="Missing 'enabled' boolean field")
    set_prompt_sanitization_enabled(bool(payload["enabled"]))
    return {"prompt_sanitization_enabled": is_prompt_sanitization_enabled()}


@admin_router.get("/users/{user_id}/prompt_sanitization", summary="Get user-level prompt sanitization setting")
async def get_user_prompt_sanitization(user_id: str):
    pref = get_prompt_sanitization_for_user(user_id)
    # explicit null when not set
    return {"user_id": user_id, "prompt_sanitization": pref}


@admin_router.post("/users/{user_id}/prompt_sanitization", summary="Set user-level prompt sanitization setting")
async def set_user_prompt_sanitization(user_id: str, payload: Dict = Body(...)):
    if "enabled" not in payload:
        raise HTTPException(status_code=400, detail="Missing 'enabled' boolean field")
    set_prompt_sanitization_for_user(user_id, bool(payload["enabled"]))
    return {"user_id": user_id, "prompt_sanitization": get_prompt_sanitization_for_user(user_id)}