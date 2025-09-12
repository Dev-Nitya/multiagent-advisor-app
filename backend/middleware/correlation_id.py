"""
FastAPI middleware that ensures a correlation/request id is present for each request
and stores request-scoped metadata in utils.request_context.request_context.

Adds header X-Request-Id to responses and reads it from incoming header if present.
"""
from typing import Callable, Optional
import uuid
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response

from utils.request_context import set_request_context, get_request_context


def _gen_request_id() -> str:
    return uuid.uuid4().hex


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = "x-request-id"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Read incoming header (case-insensitive)
        req_id = None
        try:
            req_id = request.headers.get(self.header_name) or request.headers.get(self.header_name.upper())
        except Exception:
            req_id = None

        if not req_id:
            req_id = _gen_request_id()

        # Optionally pick up a user id header if present (middleware can be extended)
        user_id = request.headers.get("x-user-id") or None
        tenant_id = request.headers.get("x-tenant-id") or None

        # Store context for this request
        set_request_context({"request_id": req_id, "user_id": user_id, "tenant_id": tenant_id})

        # Call downstream and ensure response echoes the request id
        response = await call_next(request)
        # Add header if not present
        if self.header_name not in response.headers:
            response.headers[self.header_name] = req_id
        return response