from fastapi import Request, HTTPException, APIRouter
from fastapi.responses import StreamingResponse
from utils import event_broker_redis as event_broker
import json
import asyncio

llm_events_router = APIRouter()

@llm_events_router.get("/events/{request_id}")
async def events_stream(request_id: str, request: Request):
    """
    SSE endpoint streaming events published to Redis channel "events:{request_id}".
    Closes stream when a completion sentinel event is published.
    """
    async def event_generator():
        try:
            async for raw in event_broker.subscribe_stream(request_id):
                # stop if client disconnected
                if await request.is_disconnected():
                    break

                # raw is JSON string; parse to inspect 'type'
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = None

                # If publisher sends a completion sentinel, close stream gracefully
                if isinstance(payload, dict) and payload.get("type") in ("__COMPLETE__", "__CLOSE__"):
                    # send a final event (optional) then break to close connection
                    yield f"event: complete\ndata: {json.dumps({'type': 'complete'})}\n\n"
                    break

                # Normal SSE data
                yield f"data: {raw}\n\n"
        except RuntimeError as e:
            # Redis client not initialized
            raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(event_generator(), media_type="text/event-stream")