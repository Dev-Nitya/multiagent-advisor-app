import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from models.user import User, UserSession, UserTier
from config.settings import Settings

logger = logging.getLogger(__name__)

class AuthService:
    """
    Handles JWT token creation and verification.
    """
    
    def __init__(self):
        self.settings = Settings()
        # Use a strong secret key for JWT signing
        self.secret_key = getattr(self.settings, 'jwt_secret_key', 'your-secret-key-change-this')
        self.algorithm = "HS256"
        self.access_token_expire_hours = 24  # Tokens valid for 24 hours
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password securely.
        
        SIMPLE EXPLANATION:
        We never store actual passwords. Instead, we store a "scrambled" version
        that can't be unscrambled. Like having a secret code for each password.
        """
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
        return password_hash.decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Check if a password matches the stored hash.
        
        SIMPLE EXPLANATION:
        When user logs in, we scramble their entered password the same way
        and see if it matches the stored scrambled version.
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def create_access_token(self, user: User) -> str:
        # Calculate when token expires
        expire = datetime.utcnow() + timedelta(hours=self.access_token_expire_hours)
        
        payload = {
            "user_id": user.user_id,
            "email": user.email,
            "tier": user.tier.value,
            "full_name": user.full_name,
            "exp": expire,
            "iat": datetime.utcnow(),  # Issued at time
            "type": "access"
        }
        
        # Create and sign the token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Created access token for user {user.email} (tier: {user.tier.value})")
        return token, expire
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            # Decode and verify the token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if token type is correct
            if payload.get("type") != "access":
                logger.warning("Invalid token type")
                return None
            
            logger.debug(f"Token verified for user {payload.get('email')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    def get_user_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Extract user information from a valid token.
        """
        payload = self.verify_token(token)
        if not payload:
            return None
        
        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"), 
            "tier": payload.get("tier"),
            "full_name": payload.get("full_name")
        }

# Global auth service instance
auth_service = AuthService()