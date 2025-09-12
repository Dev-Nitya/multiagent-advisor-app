from fastapi import APIRouter, HTTPException, Body
import logging

from services.prompt_registry import prompt_registry

prompt_router = APIRouter()
logger = logging.getLogger(__name__)

@prompt_router.get('/prompts')
async def list_prompts():
    try:
        prompts = prompt_registry.get_all_prompts()
        return prompts
    except Exception as e:
        logger.error(f"Error listing prompts: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")