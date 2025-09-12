from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import logging
import uuid

from services.auth_service import auth_service
from models.user import User, UserSession, UserBudget
from config.database import get_db
from config.cost_limits import UserTier, get_budget_for_tier

logger = logging.getLogger(__name__)

router = APIRouter()

# Security scheme for protected endpoints
security = HTTPBearer()

class UserRegistrationRequest(BaseModel):
    email: str
    password: str
    full_name: str
    tier: UserTier = UserTier.FREE

class UserLoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    tier: str
    is_active: bool
    created_at: str
    budget_info: dict
    prompt_sanitization: bool           

@router.post("/auth/register", response_model=AuthResponse)
async def register_user(
    request: UserRegistrationRequest,
    db: Session = Depends(get_db)
):
    logger.info(f"🔐 Registration attempt for email: {request.email}")

    try:
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            logger.warning(f"❌ Registration failed: Email {request.email} already in use")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        password_hash = auth_service.hash_password(request.password)

        new_user_id = str(uuid.uuid4())

        new_user = User(
            user_id=new_user_id,
            email=request.email,
            password_hash=password_hash,
            full_name=request.full_name,
            tier=request.tier,
            is_active=True
        )
        db.add(new_user)

        tier_limits = get_budget_for_tier(request.tier)

        user_budget = UserBudget(
            user_id=new_user_id,
            daily_limit_usd=tier_limits.daily_usd,
            monthly_limit_usd=tier_limits.monthly_usd,
            hourly_limit=tier_limits.hourly_usd,
            daily_spent_usd=0.0,
            monthly_spent_usd=0.0,
            requests_this_hour=0
        )
        
        db.add(user_budget)

        access_token, expire = auth_service.create_access_token(new_user)
        
        session = UserSession(
            session_id=str(uuid.uuid4()),
            user_id=new_user_id,
            token_hash=access_token,
            expires_at=expire,
            is_active=True
        )
        
        db.add(session)
        db.commit()
        db.refresh(new_user)

        logger.info(f"✅ User created successfully: {new_user.email} (ID: {new_user.user_id})")

        logger.info(f"💰 Budget limits set for {new_user.email}: "
                   f"${tier_limits.daily_usd}/day, ${tier_limits.monthly_usd}/month")
        
        return AuthResponse(
            access_token=access_token,
            user={
                "user_id": new_user.user_id,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "tier": new_user.tier.value,
                "is_active": new_user.is_active,
                "prompt_sanitization": new_user.prompt_sanitization,
                "budget_limits": tier_limits.to_dict()  # Convert to dict for JSON response
            }
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (like email already exists)
        raise
    except Exception as e:
        logger.error(f"❌ Registration error for {request.email}: {e}")
        db.rollback()  # Undo any partial database changes
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )
    
@router.post("/auth/login", response_model=AuthResponse)
async def login_user(
    request: UserLoginRequest,
    db: Session = Depends(get_db)
):
    logger.info(f"🔐 Login attempt for email: {request.email}")

    try:
        # Step 1: Find user by email
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            logger.warning(f"❌ Login failed: User not found - {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Step 2: Verify password
        if not auth_service.verify_password(request.password, user.password_hash):
            logger.warning(f"❌ Login failed: Invalid password for {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Step 3: Check if account is active
        if not user.is_active:
            logger.warning(f"❌ Login failed: Inactive account - {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated"
            )
        
        # Step 4: Update last login time
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Step 5: Generate new JWT token
        access_token, expire = auth_service.create_access_token(user)
        
        session = UserSession(
            session_id=str(uuid.uuid4()),
            user_id=user.user_id,
            token_hash=access_token,
            expires_at=expire,
            is_active=True
        )

        # Step 6: Get current budget info
        budget_limits = db.query(UserBudget).filter(UserBudget.user_id == user.user_id).first()
        
        logger.info(f"✅ Login successful: {user.email} (tier: {user.tier.value})")

         # Step 7: Return success response
        return AuthResponse(
            access_token=access_token,
            user={
                "user_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "tier": user.tier.value,
                "is_active": user.is_active,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "prompt_sanitization": user.prompt_sanitization,
                "budget_info": {
                    "limits": {
                        "daily_limit": budget_limits.daily_limit_usd,
                        "monthly_limit": budget_limits.monthly_limit_usd,
                        "hourly_limit": budget_limits.hourly_limit
                    },
                    "usage": {
                        "daily_spent": budget_limits.daily_spent_usd,
                        "monthly_spent": budget_limits.monthly_spent_usd,
                        "hourly_spent": budget_limits.requests_this_hour
                    }
                }
            }
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (like invalid credentials)
        raise
    except Exception as e:
        logger.error(f"❌ Login error for {request.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again."
        )
    
@router.get("/auth/profile", response_model=UserProfileResponse)
async def get_user_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    try:
        # Step 1: Extract and verify JWT token
        token = credentials.credentials
        user_info = auth_service.get_user_from_token(token)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Step 2: Get full user details from database
        user = db.query(User).filter(User.user_id == user_info["user_id"]).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        budget_limits = db.query(UserBudget).filter(UserBudget.user_id == user.user_id).first()
        
        budget_info = {
            "limits": {
                "daily_limit": budget_limits.daily_limit_usd,
                "monthly_limit": budget_limits.monthly_limit_usd,
                "hourly_limit": budget_limits.hourly_limit
            },
            "usage": {
                "daily_spent": budget_limits.daily_spent_usd,
                "monthly_spent": budget_limits.monthly_spent_usd,
                "hourly_spent": budget_limits.requests_this_hour
            }
        }
        
        # Step 4: Return user profile
        return UserProfileResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            tier=user.tier.value,
            is_active=user.is_active,
            created_at=user.created_at.isoformat(),
            budget_info=budget_info,
            prompt_sanitization=user.prompt_sanitization
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Profile fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch profile"
        )
