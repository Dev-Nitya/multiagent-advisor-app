"""
Cost Monitoring Middleware - The "Budget Security Guard"

Think of this as a security checkpoint that every AI request must pass through.
It automatically checks budgets and records costs without us having to 
remember to do it in every API endpoint.

Simple Flow:
1. User makes AI request
2. Middleware intercepts it 
3. Checks: "Can this user afford this?"
4. If YES: Let request continue → Record cost after
5. If NO: Block request → Return "budget exceeded" error
"""

import json
import logging
from typing import Optional, Dict, Any, Tuple
import uuid
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from services.auth_service import auth_service
from services.cost_monitoring_service import cost_monitoring_service
from utils.token_calculator import count_tokens, token_calculator
from config.redis_cache import cache
from config.cost_limits import COST_DATA_TTL
from utils.request_context import set_request_context, get_request_context

logger = logging.getLogger(__name__)

class CostMonitoringMiddleware(BaseHTTPMiddleware):
    """
    The "Budget Security Guard" for our AI application.
    
    This middleware automatically:
    1. Checks budgets before expensive AI requests
    2. Records actual costs after requests complete
    3. Provides cost information to users
    4. Blocks requests that would exceed budgets
    
    Think of it like a bouncer at a club - checks everyone automatically!
    """

    def __init__(self, app, enabled: bool = True):
        """
        Set up the budget security guard.
        
        Args:
            app: Our FastAPI application
            enabled: Turn budget checking on/off (useful for testing)
        """
        super().__init__(app)
        self.enabled = enabled

        # Which API endpoints use AI and need budget checking
        self.ai_endpoints = [
            "/api/evaluate",
        ]

        # Skip budget checking for these endpoints (they don't cost money)
        self.free_endpoints = [
            "/health",             # Health checks
            "/docs",               # API documentation  
            "/api/auth",           # Authentication
            "/api/user/profile"    # User management
        ]

        logger.info(f"Cost monitoring middleware initialized (enabled={enabled})")

    async def dispatch(self, request: Request, call_next):
        """
        The main "security checkpoint" function.
            
        This runs for EVERY request to our API. It decides whether
        to check budgets or just let the request through.
            
        Flow:
            1. Check if this request needs budget monitoring
            2. If YES: Check budget → Allow/Block → Record cost
            3. If NO: Just let it through normally
        """

        if not self.enabled or not self._should_check_budget(request):
            return await call_next(request)
            
        logger.info(f"Checking budget for AI request: {request.url.path}")

        try:
            user_id, user_tier = self._get_user_info_from_request(request)
            if not user_id:
                logger.warning("No user ID found, allowing request without budget check")
                return await call_next(request)
            
            # Step 3: How much will this request cost?
            estimated_cost, request_body = await self._estimate_request_cost_and_preserve_body(request)
            
            ctx = get_request_context() or {}
            if ctx.get("request_id"):
                request_id = ctx.get("request_id")
            else:
                request_id = str(uuid.uuid4())
                try:
                    set_request_context({"request_id": request_id, "user_id": user_id})
                except Exception:
                    pass

            try:
                ttl_seconds = int(COST_DATA_TTL.get("hourly_usage").total_seconds())
                payload = estimated_cost or {}
                cache.set(f"cost_est:{request_id}", json.dumps(payload), ttl_seconds)
            except Exception as e:
                logger.info("Failed to persist cost estimate to cache: %s", e)

            # Step 4: Can this user afford this request?
            can_afford, reason = cost_monitoring_service.can_user_afford_this_request(
                user_id=user_id, 
                estimated_cost=estimated_cost,
                user_tier=user_tier)

            if not can_afford:
                logger.warning(f"Blocking request - budget exceeded for user {user_id}: {reason}")
                return self._create_budget_exceeded_response(estimated_cost, reason)

            logger.info(f"Budget check passed for user {user_id}: ${estimated_cost['total_cost']:.4f}")
            
            # Recreate the request with the preserved body
            if request_body is not None:
                updated_request = await self._recreate_request_with_body(request, request_body, request_id)
            
            response = await call_next(updated_request)

            self._add_cost_info_to_response(response, estimated_cost)

            return response
        
        except Exception as e:
            logger.error(f"Error in cost monitoring middleware: {e}")
            # If anything goes wrong, allow the request (fail-open)
            # This prevents budget bugs from breaking our entire app
            return await call_next(request)

    def _should_check_budget(self, request: Request) -> bool:
        """
        Decide if this request needs budget checking.
            
        Simple logic:
            - If it's an AI endpoint → Check budget
            - If it's a free endpoint → Skip budget check
            - If it's not a POST request → Skip (GET requests are usually free)
            
        Args:
            request: The incoming HTTP request
                
        Returns:
            True if we should check budget, False otherwise
        """
        request_path = request.url.path

        # Skip free endpoints
        for free_path in self.free_endpoints:
            if request_path.startswith(free_path):
                logger.debug(f"Skipping budget check for free endpoint: {request_path}")
                return False
                
        # Only check POST requests
        if request.method != "POST":
            logger.debug(f"Skipping budget check for non-POST request: {request.method} {request_path}")
            return False

        # Check if this is an AI endpoint
        for ai_path in self.ai_endpoints:
            if request_path.startswith(ai_path):
                logger.debug(f"Budget check required for AI endpoint: {request_path}")
                return True

        logger.debug(f"No budget check required for request: {request.method} {request_path}")
        return False
        
    def _get_user_info_from_request(self, request: Request) -> Tuple[Optional[str], str]:
        """
        Figure out who is making this request.
        
        We try multiple methods to identify the user:
        1. Check request headers (most common)
        2. Check authentication token (if using JWT)
        3. Use IP address as fallback (for anonymous users)
        
        Args:
            request: The HTTP request
            
        Returns:
            Tuple of (user_id, user_tier)
        """
        try:
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                user_info = auth_service.get_user_from_token(token)
                if user_info:
                    logger.debug(f"Found authenticated user: {user_info['user_id']}")
                    return user_info['user_id'], user_info['tier']
        except Exception as e:
            logger.debug(f"Could not extract user from token: {e}")
            
        # Method 3: Use IP address as fallback (for anonymous users)
        if request.client:
            ip_address = request.client.host
            logger.debug(f"Using IP address as user ID: {ip_address}")
            return f"ip_{ip_address.replace('.', '_')}", 'free'
        
        # Method 4: Can't identify user
        logger.warning("Cannot identify user for budget tracking")
        return None

    async def _estimate_request_cost_and_preserve_body(self, request: Request) -> Tuple[Optional[Dict[str, Any]], Optional[bytes]]:
        """
        Estimate how much this AI request will cost while preserving the request body.
        
        This version reads the body once and returns both the cost estimate and the body
        so we can recreate the request for the route handler.
        
        Args:
            request: The HTTP request containing user's question
            
        Returns:
            Tuple of (cost_estimate, request_body_bytes)
        """
        try:
            # Step 1: Get the request content (only read once)
            body_bytes = await request.body()
            if not body_bytes:
                logger.warning("Empty request body, cannot estimate cost")
                return None, None
            
            # Parse the JSON
            try:
                request_body = json.loads(body_bytes)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in request body: {e}")
                return None, body_bytes  # Still preserve the body even if we can't parse it
            
            # Step 2: Extract the text that will be sent to OpenAI
            user_idea = request_body.get("idea", "")
            if not user_idea:
                logger.warning("No 'idea' field in request body, cannot estimate cost")
                return None, body_bytes
            
            # Step 3: Which AI model will be used?
            ai_model = request_body.get("model", "gpt-3.5-turbo")

            # Step 4: Estimate response length based on idea complexity
            estimated_response_tokens = self._estimate_response_length(user_idea, ai_model)

            # Step 5: Use token_calculator to get detailed cost estimation
            cost_estimate = token_calculator.estimate_cost_detailed(
                input_text=user_idea,
                model=ai_model,
                estimated_output_tokens=estimated_response_tokens
            )
        
            return cost_estimate, body_bytes
        
        except Exception as e:
            logger.error(f"Error estimating request cost: {e}")
            # Try to get the body even if cost estimation fails
            try:
                body_bytes = await request.body()
                return None, body_bytes
            except:
                return None, None

    async def _recreate_request_with_body(self, original_request: Request, body_bytes: bytes, request_id: str = None) -> Request:
        """
        Recreate the request with the preserved body so the route handler can read it.
        
        Args:
            original_request: The original request
            body_bytes: The preserved request body
            
        Returns:
            New request with the body available for reading
        """
        from fastapi import Request
        import io
        import json

        new_body_bytes = body_bytes
        if request_id:
            try:
                parsed = json.loads(body_bytes)
                # only inject if not present already
                if isinstance(parsed, dict) and not parsed.get("request_id"):
                    parsed["request_id"] = request_id
                    new_body_bytes = json.dumps(parsed).encode()
            except Exception:
                # not JSON or failed to parse — leave body as-is
                new_body_bytes = body_bytes

        # Create a new scope with the body
        scope = original_request.scope.copy()

        headers = list(scope.get("headers", []))
        if request_id:
            headers = [h for h in headers if h[0].lower() != b"x-request-id"]  # remove existing if any
            headers.append((b"x-request-id", request_id.encode()))
        scope["headers"] = headers
        
        # Create a readable stream from the preserved body
        body_stream = io.BytesIO(new_body_bytes)
        
        # Create a new receive callable that provides the body
        async def receive():
            return {
                "type": "http.request",
                "body": new_body_bytes,
                "more_body": False
            }
        
        # Create new request with the body
        new_request = Request(scope, receive)
        new_request.state.request_id = request_id

        return new_request

    async def _estimate_request_cost(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        Estimate how much this AI request will cost.
        
        Steps:
        1. Extract the user's question from the request
        2. Use token_calculator to count input tokens accurately
        3. Use smart logic to estimate how long the AI response will be  
        4. Use current OpenAI pricing to calculate exact cost
        
        Args:
            request: The HTTP request containing user's question
            
        Returns:
            Dictionary with detailed cost estimate, or None if can't estimate
        """
        try:
            # Step 1: Get the request content
            request_body = await self._get_request_body(request)
            if not request_body:
                logger.warning("Empty request body, cannot estimate cost")
                return None
            
            # Step 2: Extract the text that will be sent to OpenAI
            user_question = request_body.get("question", "")
            if not user_question:
                logger.warning("No 'question' field in request body, cannot estimate cost")
                return None
            
            # Step 3: Which AI model will be used?
            ai_model = request_body.get("model", "gpt-3.5-turbo")

            # Step 4: Estimate response length based on question complexity
            estimated_response_tokens = self._estimate_response_length(user_question, ai_model)

            # Step 5: Use token_calculator to get detailed cost estimation
            cost_estimate = token_calculator.estimate_cost_detailed(
                input_text=user_question,
                model=ai_model,
                estimated_output_tokens=estimated_response_tokens
            )
        
            return cost_estimate
        
        except Exception as e:
            logger.error(f"Error estimating request cost: {e}")
            return None

    def _estimate_response_length(self, user_idea: str, model: str) -> int:
        """
        Intelligently estimate how long the AI's response will be.
        SIMPLE LOGIC:
        1. Count how many tokens are in the user's question
        2. Analyze how complex the question is (simple vs detailed analysis request)
        3. Different AI models respond differently (GPT-4 is more detailed)
        4. Calculate intelligent estimate based on all factors
        """

        # Step 1: Count input tokens
        input_tokens = count_tokens(user_idea, model)
        logger.debug(f"Input tokens for cost estimation: {input_tokens}")

        # Step 2: How complex is the idea?
        complexity_factor = self._analyze_idea_complexity(user_idea, input_tokens)

        # Step 3: Model-specific response patterns
        model_response_factor = self._get_model_response_factor(model)

        # Step 4: Calculate estimated response length
        base_response_tokens = int(input_tokens * complexity_factor * model_response_factor)

         # Step 5: Apply reasonable bounds (prevent extreme estimates)
        min_response = max(50, input_tokens * 0.2)  # At least 20% of input length
        max_response = min(2000, input_tokens * 3.0)  # At most 3x input length

        estimated_tokens = max(min_response, min(max_response, base_response_tokens))
    
        logger.info(f"Smart response estimate for model {model}: {estimated_tokens} tokens for {input_tokens} input tokens")
    
        return int(estimated_tokens)

    def _analyze_idea_complexity(self, idea: str, input_tokens: int) -> float:
        """
        Analyze how complex the idea is to estimate response length.
        Simple heuristics:
        - Long ideas usually need detailed answers
        - Ideas with technical terms need more explanation
        - Ideas asking for analysis need comprehensive responses
        - Simple ideas get concise answers

        Args:
            user_idea: The user's idea
            input_tokens: Number of tokens in the idea

        Returns:
            Complexity factor (0.5 = simple, 2.0 = very complex)
        """
        complexity_score = 1.0 # Base complexity

        # Factor 1: Length of question
        if input_tokens > 500:
            complexity_score += 0.5  # Long question
        elif input_tokens > 200:
            complexity_score += 0.2  # Medium length

        # Factor 2: Question words that indicate complexity
        complexity_indicators = {
            # Analysis requests (need detailed responses)
            'analyze': 0.6,
            'breakdown': 0.5,
            'comprehensive': 0.7,
            'detailed': 0.4,
            'explain': 0.3,
            'compare': 0.4,
            'evaluate': 0.5,

            # Simple requests (shorter responses expected)
            'summary': -0.2,
            'briefly': -0.3,
            'quick': -0.2,
            'simple': -0.2,
            'yes/no': -0.4
        }
        idea_lower = idea.lower()
        for indicator, weight in complexity_indicators.items():
            if indicator in idea_lower:
                complexity_score += weight
                logger.debug(f"Found complexity indicator '{indicator}': +{weight}")

        # Factor 3: Idea structure analysis
        idea_marks = idea.count('?')
        if idea_marks > 1:
            complexity_score += 0.2

        complexity_score = max(0.5, min(2.5, complexity_score))

        logger.debug(f"Idea complexity score: {complexity_score}")
        return complexity_score
    
    def _get_model_response_factor(self, model: str) -> float:
        """
        Different AI models have different response patterns.
        
        This accounts for model-specific behavior:
        - GPT-4 gives more detailed, thorough responses
        - GPT-3.5 gives more concise responses
        - Some models are naturally verbose, others are terse
        
        Args:
            model: OpenAI model name
            
        Returns:
            Response length factor for this model
        """

        model_factors = {
            # GPT-4 models (more thorough and detailed)
            'gpt-4': 1.3,
            'gpt-4-turbo': 1.2,
            'gpt-4-32k': 1.4,
            
            # GPT-3.5 models (more concise)
            'gpt-3.5-turbo': 1.0,
            'gpt-3.5-turbo-16k': 1.1,
            
            # Older models (varied patterns)
            'text-davinci-003': 1.2,
            'text-davinci-002': 1.1
        }

        factor = model_factors.get(model, 1.0)  # Default to neutral
        logger.debug(f"Model response factor for {model}: {factor}")
        return factor

    async def _get_request_body(self, request: Request) -> Optional[Dict]:
        """
        Extract JSON data from the HTTP request.

        Args:
            request: HTTP request
            
        Returns:
            Dictionary with request data, or None if can't parse
        """
        try:
            body_bytes = await request.body()
            if not body_bytes:
                return None
            
            content_type = request.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                logger.warning(f"Unsupported Content-Type for cost estimation: {content_type}")
                return None
            
            # Convert bytes to dict
            body_data = json.loads(body_bytes)
            return body_data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading request body: {e}")
            return None
        
    def _create_budget_exceeded_response(self, estimated_cost: Dict, reason: str) -> JSONResponse:
        return JSONResponse(
            status_code=429,  # Too Many Requests
            content={
                "error": "Budget exceeded",
                "message": reason,
                "estimated_cost": estimated_cost.get('total_cost_usd', 0) if estimated_cost else 0,
                "suggestion": "Upgrade your plan or wait for budget reset to continue using AI features."
            },
            headers={
                "X-Budget-Exceeded": "true",
                "X-Estimated-Cost": str(estimated_cost.get('total_cost_usd', 0)) if estimated_cost else "0"
            }
        )

    def _add_cost_info_to_response(self, response: Response, estimated_cost: Optional[Dict]):
        if estimated_cost:
            # Add estimated cost info to response headers
            response.headers["X-Estimated-Cost-USD"] = str(estimated_cost.get('total_cost_usd', 0))
            response.headers["X-Estimated-Tokens"] = str(estimated_cost.get('total_tokens', 0))
            response.headers["X-Model-Used"] = estimated_cost.get('model', 'unknown')
            
            # Note about actual vs estimated
            response.headers["X-Cost-Note"] = "Estimated cost - actual cost may vary based on AI response length"
    
        
def create_cost_monitoring_middleware(enabled: bool = True):
    """
    Factory function to create the cost monitoring middleware.

    Args:
        enabled: Whether to actually check budgets (useful for testing)
        
    Returns:
        Middleware function that can be added to FastAPI
        
    Usage in main.py:
        app.add_middleware(create_cost_monitoring_middleware(enabled=True))
    """

    def middleware_factory(app):
        return CostMonitoringMiddleware(app, enabled=enabled)
    
    return middleware_factory

cost_monitoring_middleware = create_cost_monitoring_middleware()