"""
Enhanced OpenAI token calculation utility with cost monitoring integration.

This utility provides accurate token counting and cost estimation for OpenAI models,
integrating with the cost monitoring system for budget enforcement.
"""

import tiktoken
import logging
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime
from enum import Enum

from config.cost_limits import (
    OPENAI_PRICING,
    get_model_pricing,
    estimate_request_cost as config_estimate_cost
)

logger = logging.getLogger(__name__)

class TokenCalculator:
    """
    Enhanced token calculator with cost monitoring integration.
    
    This class provides:
    1. Accurate token counting using tiktoken
    2. Cost estimation with current pricing
    3. Model recommendations based on budget
    4. Batch processing for performance
    5. Integration with cost monitoring system
    """
    
    def __init__(self):
        """Initialize the enhanced token calculator."""

        # Cache for tokenizers (performance optimization)
        self._encoders = {}

        # Cache for model capabilities
        self._model_cache = {}

        logger.info("Enhanced token calculator initialized")

    def count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> int:
        """
        Count tokens in text using the appropriate tokenizer.
        
        Args:
            text: Text content to count tokens for
            model: OpenAI model name (determines tokenizer)
            
        Returns:
            Number of tokens in the text
        """
         
        if not text:
            return 0
        
        try:
            # Get encoding name for this model
            encoding_name = self._get_encoding_for_model(model)

            # Get or create cached encoder
            if encoding_name not in self._encoders:
                self._encoders[encoding_name] = tiktoken.get_encoding(encoding_name)
                logger.debug(f"Created tokenizer for encoding: {encoding_name}")
            
            encoder = self._encoders[encoding_name]

            # Count tokens
            tokens = encoder.encode(text)
            token_count = len(tokens)

            logger.debug(f"Counted {token_count} tokens for {len(text)} characters using {model}")
            
            return token_count
            
        except Exception as e:
            logger.error(f"Error counting tokens for model {model}: {e}")
            # Fallback: rough estimation (1 token ≈ 4 characters for English)
            fallback_count = max(1, len(text) // 4)
            logger.warning(f"Using fallback token count: {fallback_count}")
            return fallback_count

    def count_tokens_batch(self, texts: List[str], model: str = "gpt-3.5-turbo") -> List[int]:
        """
        Count tokens for multiple texts efficiently.
        
        Args:
            texts: List of text strings
            model: OpenAI model name
            
        Returns:
            List of token counts corresponding to input texts
            
        Why Batch Processing:
        - Reuses tokenizer instance for performance
        - Reduces overhead for multiple texts
        - Better for document processing
        """
        if not texts:
            return []
        
        try:
            encoding_name = self._get_encoding_for_model(model)

            if encoding_name not in self._encoders:
                self._encoders[encoding_name] = tiktoken.get_encoding(encoding_name)

            encoder = self._encoders[encoding_name]

            # Process all texts with same encoder
            token_counts = []
            for text in texts:
                if text:
                    tokens = encoder.encode(text)
                    token_counts.append(len(tokens))
                else:
                    token_counts.append(0)
                
            logger.debug(f"Batch counted tokens for {len(texts)} texts using {model}")
            
            return token_counts
        
        except Exception as e:
            logger.error(f"Error in batch token counting: {e}")
            # Fallback to individual counting
            return [self.count_tokens(text, model) for text in texts]
        
    def estimate_cost_detailed(self, input_text: str, model: str = "gpt-3.5-turbo", 
                             estimated_output_tokens: int = 500) -> Dict:
        """
        Provide detailed cost estimation with breakdown.
        
        Args:
            input_text: Input text for the request
            model: OpenAI model to use
            estimated_output_tokens: Expected response length
            
        Returns:
            Detailed cost breakdown dictionary
        """
        input_tokens = self.count_tokens(input_text, model)

         # Get current pricing
        pricing = get_model_pricing(model)
        if not pricing:
            logger.error(f"No pricing found for model: {model}")
            return self._create_error_cost_estimate(input_tokens, estimated_output_tokens, model)
        
        # Calculate costs
        input_cost = (input_tokens / 1000) * pricing.get("input_cost_per_1k", 0.0)
        output_cost = (estimated_output_tokens / 1000) * pricing.get("output_cost_per_1k", 0.0)
        total_cost = input_cost + output_cost

        # Create detailed breakdown
        cost_breakdown = {
            "input_tokens": input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "total_tokens": input_tokens + estimated_output_tokens,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(total_cost, 6),
            "model": model,
            "pricing_per_1k": {
                "input": pricing["input_cost_per_1k"],
                "output": pricing["output_cost_per_1k"]
            },
            "model_limits": {
                "max_tokens": pricing["max_tokens"],
                "recommended_max_input": pricing.get("recommended_max_input", pricing["max_tokens"] // 2)
            },
            "estimated_at": datetime.utcnow().isoformat(),
            "currency": "USD"
        }

        logger.info(f"Cost estimate for {model}: ${total_cost:.6f} ({input_tokens}+{estimated_output_tokens} tokens)")
        
        return cost_breakdown
    
    def recommend_model_for_budget(self, input_text: str, budget_usd: float, 
                                 estimated_output_tokens: int = 500) -> Dict:
        """
        Recommend the best model that fits within budget.
        
        Args:
            input_text: Input text for the request
            budget_usd: Available budget in USD
            estimated_output_tokens: Expected response length
            
        Returns:
            Dictionary with model recommendation and cost comparison
        """
        input_tokens = self.count_tokens(input_text)

        # Check all available models
        model_options = []

        for model_name in OPENAI_PRICING.keys():
            pricing = get_model_pricing(model_name)

            if input_tokens > pricing.get("recommended_max_input", pricing["max_tokens"]):
                continue

            # Calculate cost for this model
            input_cost = (input_tokens / 1000) * pricing["input_cost_per_1k"]
            output_cost = (estimated_output_tokens / 1000) * pricing["output_cost_per_1k"]
            total_cost = input_cost + output_cost

            # Check if within budget
            within_budget = total_cost <= budget_usd

            model_options.append({
                "model": model_name,
                "total_cost_usd": round(total_cost, 6),
                "input_cost_usd": round(input_cost, 6),
                "output_cost_usd": round(output_cost, 6),
                "within_budget": within_budget,
                "budget_utilization": round((total_cost / budget_usd) * 100, 1) if budget_usd > 0 else float('inf'),
                "max_tokens": pricing["max_tokens"],
                "cost_per_1k_output": pricing["output_cost_per_1k"]
            })

        # Sort by cost (ascending)
        model_options.sort(key=lambda x: x["total_cost_usd"])

        # Find best model within budget
        recommended_model = None
        affordable_models = [m for m in model_options if m["within_budget"]]

        if affordable_models:
            # Recommend highest quality model within budget
            # (assuming more expensive = higher quality)
            recommended_model = max(affordable_models, key=lambda x: x["total_cost_usd"])

        recommendation = {
            "recommended_model": recommended_model["model"] if recommended_model else None,
            "recommended_cost": recommended_model["total_cost_usd"] if recommended_model else None,
            "budget_usd": budget_usd,
            "input_tokens": input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "all_options": model_options,
            "affordable_count": len(affordable_models),
            "cheapest_option": model_options[0] if model_options else None,
            "reason": self._get_recommendation_reason(recommended_model, affordable_models, budget_usd)
        }
        
        logger.info(f"Model recommendation: {recommendation['recommended_model']} for budget ${budget_usd}")
        
        return recommendation
    
    def validate_context_length(self, text: str, model: str) -> Dict:
        """
        Validate if text fits within model's context length.
        
        Args:
            text: Text to validate
            model: OpenAI model name
            
        Returns:
            Validation result with recommendations
        """
        token_count = self.count_tokens(text, model)
        pricing = get_model_pricing(model)
        
        if not pricing:
            return {
                "valid": False,
                "reason": f"Unknown model: {model}",
                "token_count": token_count
            }
    
        max_tokens = pricing["max_tokens"]
        recommended_max = pricing.get("recommended_max_input", max_tokens // 2)

        # Validation logic
        if token_count <= recommended_max:
            status = "optimal"
            valid = True
            reason = f"Text fits comfortably within recommended limit"
        elif token_count <= max_tokens:
            status = "acceptable"
            valid = True
            reason = f"Text fits but leaves little room for response"
        else:
            status = "too_long"
            valid = False
            reason = f"Text exceeds model's maximum context length"

        return {
            "valid": valid,
            "status": status,
            "reason": reason,
            "token_count": token_count,
            "max_tokens": max_tokens,
            "recommended_max_input": recommended_max,
            "utilization_percent": round((token_count / max_tokens) * 100, 1),
            "tokens_over_limit": max(0, token_count - max_tokens),
            "suggested_truncation": max(0, token_count - recommended_max) if token_count > recommended_max else 0
        }


    def _get_recommendation_reason(self, recommended: Optional[Dict], affordable: List[Dict], budget: float) -> str:
        """Generate human-readable recommendation reason."""
        if not recommended:
            if not affordable:
                return f"No models fit within ${budget:.2f} budget. Consider increasing budget or reducing input length."
            else:
                return "No suitable model found within budget."
        
        if recommended["model"] == "gpt-3.5-turbo":
            return "GPT-3.5 Turbo recommended for cost efficiency and good quality."
        elif recommended["model"].startswith("gpt-4"):
            return "GPT-4 recommended for highest quality within budget."
        else:
            return f"Best quality model within ${budget:.2f} budget."

    def _create_error_cost_estimate(self, input_tokens: int, output_tokens: int, model: str) -> Dict:
        """Create a fallback cost estimate when pricing is unavailable."""
        return {
            "input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "input_cost_usd": 0.0,
            "output_cost_usd": 0.0,
            "total_cost_usd": 0.0,
            "model": model,
            "error": "Pricing information not available",
            "estimated_at": datetime.utcnow().isoformat(),
            "currency": "USD"
        }

    def _get_encoding_for_model(self, model: str) -> str:
        """
        Get the appropriate encoding for an OpenAI model.
        
        Args:
            model: OpenAI model name
            
        Returns:
            Encoding name for tiktoken
        """
        # Most current models use cl100k_base
        if model.startswith(("gpt-4", "gpt-3.5-turbo")):
            return "cl100k_base"
        elif model.startswith("text-davinci"):
            return "p50k_base"
        elif model.startswith(("text-ada", "text-babbage", "text-curie")):
            return "r50k_base"
        else:
            # Default to most common encoding
            logger.warning(f"Unknown model {model}, using default encoding")
            return "cl100k_base"


# Global instance for application use
token_calculator = TokenCalculator()

# Convenience functions for easy importing
def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Quick token counting function."""
    return token_calculator.count_tokens(text, model)

def estimate_cost(input_text: str, model: str = "gpt-3.5-turbo", output_tokens: int = 500) -> Dict:
    """Quick cost estimation function."""
    return token_calculator.estimate_cost_detailed(input_text, model, output_tokens)

def recommend_model(input_text: str, budget_usd: float, output_tokens: int = 500) -> Dict:
    """Quick model recommendation function."""
    return token_calculator.recommend_model_for_budget(input_text, budget_usd, output_tokens)