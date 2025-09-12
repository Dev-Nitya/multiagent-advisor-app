import time
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from middleware.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    
    Why middleware? It runs on every request automatically, providing
    consistent protection across all endpoints without modifying each route.
    """

    def __init__(self, app, skip_paths: list = None):
        super().__init__(app)
        # Paths to skip rate limiting (usually static assets)
        self.skip_paths = skip_paths or ["/docs", "/redoc", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        """
        Main middleware function that processes each request.
        
        Flow:
        1. Check if path should be skipped
        2. Apply rate limiting
        3. If blocked, return 429 error
        4. If allowed, proceed to route handler
        5. Add rate limit headers to response
        """
        start_time = time.time()

        # Skip rate limiting for specified paths
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        # Check rate limit
        try:
            is_allowed, rate_limit_headers = rate_limiter.check_rate_limit(request)

            if not is_allowed:
                # Return late limit exceeded response
                error_response = JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": "Too many requests. Please try again later.",
                        "error_code": "RATE_LIMIT_EXCEEDED",
                        "retry_after": rate_limit_headers.get("Retry-After", "60")
                    },
                    headers=rate_limit_headers
                )

                # Log rate limit event
                process_time = time.time() - start_time
                logger.warning(
                    f"Rate limit blocked",
                    extra={
                        "path": request.url.path,
                        "method": request.method,
                        "client_ip": request.client.host if request.client else "unknown",
                        "user_agent": request.headers.get("User-Agent", ""),
                        "process_time": process_time,
                        "headers": dict(rate_limit_headers)
                    }
                )
                
                return error_response
            
        except Exception as e:
            # If rate limiting fails, log error but allow request through
            # (fail open for availability)
            logger.error(f"Rate limiting error: {e}")
            # Continue to route handler

        # Process the request
        response = await call_next(request)

        # Add rate limit headers to successful responses too
        # (so clients know their current usage)

        try:
            if hasattr(request.state, 'rate_limit_headers'):
                for key, value in request.state.rate_limit_headers.items():
                    response.headers[key] = value
        except Exception as e:
            logger.error(f"Error adding rate limit headers: {e}")
        
        return response
    
def create_rate_limit_middleware(skip_paths: list = None):
    """
    Factory function to create rate limit middleware with configuration.
    
    Why factory? Makes it easy to configure different skip paths for
    different environments or deployments.
    """
    return lambda app: RateLimitMiddleware(app, skip_paths=skip_paths)