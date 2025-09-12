import os
import logging
from typing import Optional


logger = logging.getLogger(__name__)

class Settings:
    """
    Smart settings that adapt to environment
    """
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.is_production = self.environment == 'production'
        
        # Basic app settings
        self.app_name = "Multi agent advisor"
        self.debug = not self.is_production
        
    # DATABASE SETTINGS
    @property
    def database_url(self) -> str:
        """
        Get database connection URL
        
        FLOW:
        Development → sqlite:///./multi_agent_advisor.db
        """
        
        # Development: Use local SQLite
        return "sqlite:///./ai_legal_assistant.db"
    
    # REDIS SETTINGS
    @property
    def redis_url(self) -> str:
        return os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    @property
    def redis_host(self) -> str:
        return os.getenv('REDIS_HOST', 'localhost')
        
    @property
    def redis_port(self) -> str:
        return os.getenv('REDIS_PORT', '6379')

    @property
    def openai_api_key(self) -> str:
        key = os.getenv('OPENAI_API_KEY')

        if not key:
            raise ValueError("OpenAI API key not configured")
        return key

    @property
    def langsmith_api_key(self) -> Optional[str]:
        return os.getenv('LANGSMITH_API_KEY', None)

    @property
    def jwt_secret_key(self) -> str:
        return os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
    
    # COST MONITORING
    @property
    def cost_monitoring_enabled(self) -> bool:
        return os.getenv('COST_MONITORING_ENABLED', 'true').lower() == 'true'

# Global settings instance
settings = Settings()

# Helper functions for easy access
def is_production() -> bool:
    return settings.is_production

def get_database_url() -> str:
    return settings.database_url

def get_redis_url() -> str:
    return settings.redis_url