"""
Cost limits configuration for OpenAI usage monitoring.

This file defines budget configurations, cost thresholds, and pricing models
for comprehensive OpenAI cost management across the application.

Key Components:
- Budget tier definitions (free, premium, enterprise)
- OpenAI model pricing (updated regularly)
- Alert thresholds for proactive notifications
- Cost enforcement policies
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import timedelta

class UserTier(str, Enum):
    """
    User tier definitions for different budget levels.
    
    Different tiers allow for flexible pricing models:
    - FREE: Limited usage for trial users
    - BASIC: Individual professionals
    - PREMIUM: Small law firms
    - ENTERPRISE: Large organizations
    """
    FREE = "free"
    BASIC = "basic" 
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class CostEnforcementMode(str, Enum):
    """
    Cost enforcement modes for different scenarios.
    
    STRICT: Block requests that exceed budget (production)
    WARN: Allow overages with warnings (development)
    DISABLED: No cost enforcement (testing)
    """
    STRICT = "strict"
    WARN = "warn"
    DISABLED = "disabled"

@dataclass
class BudgetLimits:
    """
    Budget limits for different time periods.
    
    Multiple period limits provide granular control:
    - Hourly: Prevents burst spending
    - Daily: Most common limit for individuals  
    - Weekly: Good for small teams
    - Monthly: Enterprise budgets
    """
    hourly_usd: float
    daily_usd: float
    weekly_usd: float
    monthly_usd: float

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for storage."""
        return {
            "hourly": self.hourly_usd,
            "daily": self.daily_usd,
            "weekly": self.weekly_usd,
            "monthly": self.monthly_usd
        }
    
# Predefined budget tiers for different user types
BUDGET_TIERS: Dict[UserTier, BudgetLimits] = {
    UserTier.FREE: BudgetLimits(
        hourly_usd=1.0,    # $1/hour - prevents abuse
        daily_usd=5,   # $5/day - ~150 GPT-3.5 requests
        weekly_usd=20.0,   # $20/week
        monthly_usd=50.0   # $50/month
    ),
    UserTier.BASIC: BudgetLimits(
        hourly_usd=10.0,   # $10/hour
        daily_usd=50.0,    # $50/day - ~1500 GPT-3.5 requests
        weekly_usd=200.0,  # $200/week
        monthly_usd=500.0  # $500/month
    ),
    UserTier.PREMIUM: BudgetLimits(
        hourly_usd=25.0,   # $25/hour
        daily_usd=150.0,   # $150/day
        weekly_usd=750.0,  # $750/week
        monthly_usd=2000.0 # $2000/month
    ),
    UserTier.ENTERPRISE: BudgetLimits(
        hourly_usd=100.0,  # $100/hour
        daily_usd=1000.0,  # $1000/day
        weekly_usd=5000.0, # $5000/week
        monthly_usd=20000.0 # $20,000/month
    )
}

# Alert thresholds as percentages of budget limit
ALERT_THRESHOLDS = {
    "info": 0.50,      # 50% - informational
    "warning": 0.75,   # 75% - user should be aware
    "critical": 0.90,  # 90% - urgent attention needed
    "emergency": 1.0   # 100% - budget exceeded
}

# OpenAI model pricing (per 1,000 tokens) - UPDATE WHEN PRICES CHANGE
OPENAI_PRICING = {
    "gpt-3.5-turbo-0125": {
        "input_cost_per_1k": 0.0005,
        "output_cost_per_1k": 0.0015,
        "max_tokens": 4096,
        "recommended_max_input": 3000  # Leave room for output
    },
    "gpt-3.5-turbo": {
        "input_cost_per_1k": 0.0015,
        "output_cost_per_1k": 0.002,
        "max_tokens": 4096,
        "recommended_max_input": 3000  # Leave room for output
    },
    "gpt-3.5-turbo-16k": {
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.004,
        "max_tokens": 16384,
        "recommended_max_input": 12000
    },
    "gpt-4": {
        "input_cost_per_1k": 0.03,
        "output_cost_per_1k": 0.06,
        "max_tokens": 8192,
        "recommended_max_input": 6000
    },
    "gpt-4-32k": {
        "input_cost_per_1k": 0.06,
        "output_cost_per_1k": 0.12,
        "max_tokens": 32768,
        "recommended_max_input": 24000
    },
     "gpt-4-turbo-preview": {
        "input_cost_per_1k": 0.01,
        "output_cost_per_1k": 0.03,
        "max_tokens": 128000,
        "recommended_max_input": 100000
    }
}

# Cost enforcement configuration
COST_ENFORCEMENT_CONFIG = {
    "enabled": True,  # Set to False to disable cost monitoring
    "mode": CostEnforcementMode.STRICT,  # Default enforcement mode
    "grace_period_seconds": 300,  # 5 minutes grace period for budget resets
    "max_request_cost_usd": 5.0,  # Maximum cost for a single request
    "emergency_shutdown_threshold": 10.0,  # Auto-disable at 10x daily budget
}

# Redis TTL configuration for cost data
COST_DATA_TTL = {
    "hourly_usage": timedelta(days=2),    # Keep 2 days of hourly data
    "daily_usage": timedelta(days=31),    # Keep 31 days of daily data
    "weekly_usage": timedelta(days=365),  # Keep 1 year of weekly data
    "monthly_usage": timedelta(days=365), # Keep 1 year of monthly data
    "cost_records": timedelta(days=90),   # Keep detailed records for 90 days
    "budget_configs": timedelta(days=365), # Budget configs persist 1 year
    "alerts": timedelta(days=30)          # Keep alerts for 30 days
}

def get_budget_for_tier(tier: UserTier) -> BudgetLimits:
    """
    Get budget limits for a specific user tier.
    
    Args:
        tier: User tier enum
        
    Returns:
        Budget limits for the tier
        
    Raises:
        ValueError: If tier is not recognized
    """
    if tier not in BUDGET_TIERS:
        raise ValueError(f"Unrecognized user tier: {tier}")
    return BUDGET_TIERS[tier]

def get_model_pricing(model: str) -> Optional[Dict]:
    """
    Get pricing information for an OpenAI model.
    
    Args:
        model: OpenAI model name

    Returns:
        Pricing dictionary or None if model not found
    """
    return OPENAI_PRICING.get(model)

def calculate_max_tokens_for_budget(model: str, budget_usd: float) -> int:
    """
    Calculate maximum tokens that can be used within a budget.
    
    Args:
        model: OpenAI model name
        budget_usd: Available budget in USD
        
    Returns:
        Maximum number of tokens (conservative estimate)
    """
    pricing = get_model_pricing(model)

    # Use higher cost (output) for conservative estimate
    cost_per_token = pricing["output_cost_per_1k"] / 1000 if pricing else 0.0

    return int(budget_usd / cost_per_token) if cost_per_token > 0 else 0

def estimate_request_cost(model: str, input_tokens: int, output_tokens: int = 500) -> float:
    """
    Estimate cost for a specific request.
    
    Args:
        model: OpenAI model name
        input_tokens: Number of input tokens
        output_tokens: Expected output tokens
        
    Returns:
        Estimated cost in USD
    """
    pricing = get_model_pricing(model)
    if not pricing:
        return 0.0
    
    input_cost = (input_tokens / 1000) * pricing["input_cost_per_1k"]
    output_cost = (output_tokens / 1000) * pricing["output_cost_per_1k"]

    return input_cost + output_cost