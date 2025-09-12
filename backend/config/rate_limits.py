from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class RateLimitType(str, Enum):
    """Different types of rate limits we can apply"""
    PER_IP = "per_ip" # Limit based on client IP address
    PER_SESSION = "per_session" # Limit based on user session ID
    PER_ENDPOINT = "per_endpoint" # Different limits for different endpoints
    GLOBAL = "global" # Global limit across all users, overall system protection

@dataclass
class RateLimitRule:
    """
    A single rate limiting rule.

    Why dataclass? It gives us clean, typed configuration that's easy to validate.
    """
    requests: int # How many requests are allowed
    window_seconds: int # In what time period
    burst_allowance: int = 0  # Extra requests allowed for bursty traffic

class RateLimitConfig:
    """
    Central configuration for all rate limits.

    Why separate class? This lets us easily swap configurations for 
    different environments (dev/staging/prod) or user tiers (free/premium).
    """

    def __init__(self):
        # Per-IP limits (prevents basic abuse and DDos)
        self.ip_limits = [
            RateLimitRule(requests=60, window_seconds=60), # 60/minute
            RateLimitRule(requests=1000, window_seconds=3600), # 1000/hour
        ]

        # Per-session limits (prevents cost abuse from legitimate users)
        self.session_limits = [
            RateLimitRule(requests=20, window_seconds=3600),   # 20 chat/hour
            RateLimitRule(requests=100, window_seconds=86400), # 100 chat/day
        ]

        # Global limits (protects infrastructure)
        self.global_limits = [
            RateLimitRule(requests=1000, window_seconds=60),   # 1000/minute globally
        ]

        # Endpoint-specific overrides
        self.endpoint_overrides = {
            "/health": [  # Health checks need higher limits for monitoring
                RateLimitRule(requests=300, window_seconds=60),
            ],
            "/api/evaluate": [
                RateLimitRule(requests=10, window_seconds=60),
                RateLimitRule(requests=50, window_seconds=3600),
            ],
        }

        # Admin bypass tokens (for emergency access)
        self.admin_bypass_tokens = []  # Will be loaded from secrets
        
        # Redis configuration
        self.redis_key_prefix = "agent-advisor:rate_limit"
        self.redis_key_ttl = 86400  # 24 hours - prevents memory leaks

    def get_limits_for_endpoint(self, endpoint: str) -> List[RateLimitRule]:
        """
        Get the appropriate rate limits for a specific endpoint.
        
        Why method? Different endpoints need different limits - health checks
        can be more frequent than expensive AI operations.
        """
        return self.endpoint_overrides.get(endpoint, self.ip_limits)
    
# Global instance
rate_limit_config = RateLimitConfig()