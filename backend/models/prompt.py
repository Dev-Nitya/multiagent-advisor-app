from sqlalchemy import JSON, Column, String, DateTime, Boolean, Enum, Float, Integer, Text
from datetime import datetime
import uuid

from config.db_base import Base

class Prompt(Base):
    __tablename__ = 'prompts'

    prompt_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    prompt_text = Column(Text, nullable=False)
    
    model_settings = Column(JSON, nullable=True)  # JSON string for model settings
    output_schema = Column(JSON, nullable=True)   # JSON string for output schema

    hash = Column(String, unique=True, nullable=False)

    author = Column(String, nullable=False)
    changelog = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Prompt {self.name} (v{self.version})>"