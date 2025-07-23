"""
LLM Manager with connection pooling for efficient resource management
"""
import os
from typing import Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseLLM
import httpx
from threading import Lock


class LLMManager:
    """
    Singleton LLM manager that provides connection pooling and reuse of LLM instances
    """
    _instance = None
    _lock = Lock()
    _llm_instances: Dict[str, BaseLLM] = {}
    _http_client: Optional[httpx.Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self._initialize_http_client()
            self.initialized = True
    
    def _initialize_http_client(self):
        """Initialize HTTP client with connection pooling"""
        self._http_client = httpx.Client(
            # Connection pooling settings
            limits=httpx.Limits(
                max_keepalive_connections=20,  # Keep 20 connections alive
                max_connections=100,           # Max total connections
                keepalive_expiry=30.0         # Keep connections alive for 30 seconds
            ),
            # Timeout settings
            timeout=httpx.Timeout(
                connect=10.0,   # Connection timeout
                read=60.0,      # Read timeout
                write=10.0,     # Write timeout
                pool=5.0        # Pool timeout
            ),
            # Retry settings
            transport=httpx.HTTPTransport(retries=2)
        )
    
    @classmethod
    def get_openai_llm(
        cls, 
        model_name: str = "gpt-3.5-turbo", 
        temperature: float = 0.1,
        max_tokens: Optional[int] = None
    ) -> ChatOpenAI:
        """Get a pooled OpenAI LLM instance"""
        instance = cls()
        key = f"openai_{model_name}_{temperature}_{max_tokens}"
        
        if key not in instance._llm_instances:
            with cls._lock:
                if key not in instance._llm_instances:
                    # Create OpenAI LLM with pooled HTTP client
                    instance._llm_instances[key] = ChatOpenAI(
                        model=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        max_retries=2,
                        request_timeout=60,
                        # Use our pooled HTTP client
                        http_client=instance._http_client,
                        # Connection reuse settings
                        streaming=False,  # Disable streaming for better pooling
                    )
        
        return instance._llm_instances[key]
    
    @classmethod
    def get_default_llm(cls, **kwargs) -> BaseLLM:
        """Get the default LLM based on available API keys"""
        if os.getenv("OPENAI_API_KEY"):
            return cls.get_openai_llm(**kwargs)
        elif os.getenv("ANTHROPIC_API_KEY"):
            return cls.get_anthropic_llm(**kwargs)
        else:
            # Fallback to OpenAI (will raise error if no key)
            return cls.get_openai_llm(**kwargs)
    
    @classmethod
    def get_fast_llm(cls) -> BaseLLM:
        """Get a fast, low-cost LLM for simple tasks"""
        if os.getenv("OPENAI_API_KEY"):
            return cls.get_openai_llm(model_name="gpt-3.5-turbo", temperature=0.1)
        else:
            return cls.get_default_llm(temperature=0.1)
    
    @classmethod
    def get_smart_llm(cls) -> BaseLLM:
        """Get a more capable LLM for complex tasks"""
        if os.getenv("OPENAI_API_KEY"):
            return cls.get_openai_llm(model_name="gpt-4", temperature=0.1)
        elif os.getenv("ANTHROPIC_API_KEY"):
            return cls.get_anthropic_llm(model_name="claude-3-sonnet-20240229", temperature=0.1)
        else:
            return cls.get_default_llm(temperature=0.1)
    
    @classmethod
    def close_connections(cls):
        """Close all pooled connections (call on app shutdown)"""
        instance = cls()
        if instance._http_client:
            instance._http_client.close()
            instance._http_client = None
        instance._llm_instances.clear()
    
    @classmethod
    def get_pool_stats(cls) -> Dict[str, int]:
        """Get connection pool statistics"""
        instance = cls()
        return {
            "cached_llm_instances": len(instance._llm_instances),
            "http_client_active": 1 if instance._http_client else 0
        }
