from sqlalchemy import Column, String, DateTime, Boolean, Enum, Float, Integer
from datetime import datetime
import uuid

from config.cost_limits import UserTier
from config.db_base import Base

class User(Base):
    __tablename__ = 'users'

    user_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)

    full_name = Column(String, nullable=True)
    tier = Column(Enum(UserTier), default=UserTier.FREE)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    prompt_sanitization = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<User {self.email} ({self.tier.value})>"
    
class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    token_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Session {self.session_id[:8]}... for user {self.user_id[:8]}...>"
    
class UserBudget(Base):
    __tablename__ = "user_budgets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    
    # BUDGET LIMITS
    daily_limit_usd = Column(Float, nullable=False)
    monthly_limit_usd = Column(Float, nullable=False)
    hourly_limit = Column(Integer, nullable=False)

    # CURRENT USAGE
    daily_spent_usd = Column(Float, default=0.0)
    monthly_spent_usd = Column(Float, default=0.0)
    requests_this_hour = Column(Integer, default=0)
    
    # RESET TRACKING (when to reset counters)
    daily_reset_date = Column(DateTime, default=datetime.utcnow)
    monthly_reset_date = Column(DateTime, default=datetime.utcnow)
    hourly_reset_date = Column(DateTime, default=datetime.utcnow)

    s_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Budget {self.user_id[:8]}... ${self.daily_spent_usd:.2f}/${self.daily_limit_usd:.2f}>"