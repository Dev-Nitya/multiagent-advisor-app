from typing import Optional
from sqlalchemy.orm import Session
from models.user import User

from config.database import db_manager  

def get_prompt_sanitization_for_user(user_id: str) -> Optional[bool]:
    if not user_id:
        return None
    
    session_local = db_manager.get_session()
    with session_local as db:  # context-managing session
        user = db.query(User).filter(User.user_id == user_id).one_or_none()
        if not user:
            return None
        return bool(user.prompt_sanitization)

def set_prompt_sanitization_for_user(user_id: str, enabled: bool) -> bool:
    if not user_id:
        return False
    
    session_local = db_manager.get_session()
    with session_local as db:
        user = db.query(User).filter(User.user_id == user_id).one_or_none()
        if user is None:
            return False
        user.prompt_sanitization = bool(enabled)
        db.add(user)
        db.commit()
        return True