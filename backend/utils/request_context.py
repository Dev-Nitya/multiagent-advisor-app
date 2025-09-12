"""
Request-scoped context helpers.

Provides a single ContextVar `request_context` holding a dict with keys like:
  - request_id
  - user_id
  - tenant_id

Other modules (middleware, callbacks, services) should import and read/write this.
"""
from typing import Dict, Any
import contextvars

# default empty dict ensures get() always returns a dict
request_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("request_context", default={})


def get_request_context() -> Dict[str, Any]:
    return request_context.get()


def set_request_context(ctx: Dict[str, Any]):
    # store a shallow copy to avoid accidental mutation across contexts
    request_context.set(dict(ctx))