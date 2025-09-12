import time
import hashlib
from typing import Optional, Dict, List, Tuple
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import logging

from config.rate_limits import rate_limit_config, RateLimitRule, RateLimitType
from utils.rate_limit_storage import create_rate_limit_storage, RateLimitStorage
from utils.request_context import get_request_context

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Main rate limiting engine.
    
    This orchestrates the rate limiting by:
    1. Extracting identifiers from requests (IP, session, etc.)
    2. Checking multiple rate limit rules
    3. Returning appropriate responses
    """

    def __init__(self):
        self.storage = create_rate_limit_storage()
        self.config = rate_limit_config

    def _get_client_identifier(self, request: Request, limit_type: RateLimitType) -> str:
        """
        Extract the appropriate identifier for rate limiting.
        
        Why different identifiers? Different types of abuse need different tracking:
        - IP addresses for basic abuse/DDoS
        - Session IDs for cost control per user
        - Global for infrastructure protection
        """

        ctx = get_request_context() or {}
        
        if limit_type == RateLimitType.PER_IP:
            # Get real IP, considering proxy headers
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                # Use first IP in chain (original client)
                client_ip = forwarded_for.split(",")[0].strip()
            else:
                client_ip = request.client.host if request.client else "unknown"
            return f"ip:{client_ip}"
        
        elif limit_type == RateLimitType.PER_SESSION:
            user_from_ctx = ctx.get("user_id")
            if user_from_ctx:
                session_id = user_from_ctx
            else:
                session_id = (
                    request.headers.get("X-Session-ID") or
                    request.cookies.get("session_id") or
                    request.headers.get("Authorization", "anonymous")
                )
            # Hash session ID for privacy
            session_hash = hashlib.md5(session_id.encode()).hexdigest()[:16]
            return f"session:{session_hash}"

        elif limit_type == RateLimitType.GLOBAL:
            return "global:all"
            
        else:
            return "unknown"
        
    def _build_redis_key(self, identifier: str, endpoint: str, window_seconds: int) -> str:
        """
        Build Redis key for rate limiting.
        
        Format: legal_assistant:rate_limit:{identifier}:{endpoint}:{window}
        Why this format? Hierarchical keys make it easy to analyze usage patterns.
        """
        # Sanitize endpoint for Redis key
        safe_endpoint = endpoint.replace("/", "_").replace(":", "_")
        """
        By dividing the current timestamp by the size of the rate limit window (e.g., 60s, 300s), 
        we effectively group all timestamps into the same “bucket ID” for that window.
            Example:
                Assume window_seconds = 60 (1-minute window).
                Current time.time() = 1734501234.
                1734501234 // 60 = 28908353.
                Every second in the same minute will floor to the same bucket number (28908353 here).
        Key idea: Instead of storing every timestamp, just maintain a counter per window.
        """
        window_id = int(time.time() // window_seconds)  # Window bucket

        return f"{self.config.redis_key_prefix}:{identifier}:{safe_endpoint}:{window_seconds}:{window_id}"
    
    def _check_admin_bypass(self, request: Request) -> bool:
        """
        Check if request has admin bypass token.
        Why bypass? Emergency access during incidents, internal testing.
        """
        admin_token = request.headers.get("X-Admin-Token")
        return admin_token in self.config.admin_bypass_tokens
    
    def check_rate_limit(self, request: Request) -> Tuple[bool, Dict]:
        """
        Check if request should be rate limited.
        
        Returns: (is_allowed, headers_dict)
        """

        # Attach request id to logs if available
        ctx = get_request_context() or {}
        req_id = ctx.get("request_id")

        # Admin bypass
        if self._check_admin_bypass(request):
            return True, {}
        
        endpoint = request.url.path
        limits = self.config.get_limits_for_endpoint(endpoint)

        # Check each rate limit rule
        for limit_rule in limits:
            # Check IP-based limits
            ip_identifier = self._get_client_identifier(request, RateLimitType.PER_IP)
            ip_key = self._build_redis_key(ip_identifier, endpoint, limit_rule.window_seconds)

            current_count, is_allowed = self.storage.increment_and_check(ip_key, limit_rule.window_seconds, limit_rule.requests)

            if not is_allowed:
                reset_time = self.storage.get_reset_time(ip_key, limit_rule.window_seconds)
                headers = self._build_rate_limit_headers(
                    limit_rule.requests, current_count, reset_time
                )
                logger.warning(f"Rate limit exceeded for IP {ip_identifier} on {endpoint} request_id={req_id}")
                return False, headers
            
        # Check session-based limits for expansive endpoints
        if endpoint.startswith("/api/evaluate"):
            session_identifier = self._get_client_identifier(request, RateLimitType.PER_SESSION)

            for limit_rule in self.config.session_limits:
                session_key = self._build_redis_key(session_identifier, endpoint, limit_rule.window_seconds)
                
                current_count, is_allowed = self.storage.increment_and_check(
                    session_key, limit_rule.window_seconds, limit_rule.requests
                )
                
                if not is_allowed:
                    reset_time = self.storage.get_reset_time(session_key, limit_rule.window_seconds)
                    headers = self._build_rate_limit_headers(
                        limit_rule.requests, current_count, reset_time
                    )
                    logger.warning(f"Session rate limit exceeded for {session_identifier} on {endpoint} request_id={req_id}")
                    return False, headers

        # Check global limits
        for limit_rule in self.config.global_limits:
            global_key = self._build_redis_key("global:all", endpoint, limit_rule.window_seconds)
            
            current_count, is_allowed = self.storage.increment_and_check(
                global_key, limit_rule.window_seconds, limit_rule.requests
            )
            
            if not is_allowed:
                reset_time = self.storage.get_reset_time(global_key, limit_rule.window_seconds)
                headers = self._build_rate_limit_headers(
                    limit_rule.requests, current_count, reset_time
                )
                logger.error(f"Global rate limit exceeded on {endpoint} request_id={req_id}")
                return False, headers
            
        # All checks passed
        return True, {}

    def _build_rate_limit_headers(self, limit: int, current: int, reset_time: int) -> Dict[str, str]:
        """
        Build HTTP headers for rate limit responses.
        
        Why headers? Standard way to communicate rate limits to clients.
        Clients can implement proper backoff strategies.
        """
        remaining = max(0, limit - current)
        retry_after = max(1, reset_time - int(time.time()))

        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
            "Retry-After": str(retry_after),
        }
    
# Global rate limiter instance
rate_limiter = RateLimiter()