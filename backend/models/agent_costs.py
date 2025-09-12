from datetime import datetime
from sqlalchemy import Column, DateTime, Float, String, Integer, Text, Numeric, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from config.db_base import Base

def _gen_uuid():
    return str(uuid.uuid4())

class ModelPricing(Base):
    __tablename__ = "model_pricing"
    model_name = Column(String, primary_key=True)
    input_usd_per_1k = Column(Float, nullable=False)
    output_usd_per_1k = Column(Float, nullable=False)

class CostEvent(Base):
    __tablename__ = "cost_events"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_gen_uuid)
    ts = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(String, nullable=True, index=True)
    request_id = Column(String, nullable=True, index=True)
    graph_node_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=True, index=True)
    tool_id = Column(String, nullable=True, index=True)
    provider = Column(String, nullable=True)
    model_name = Column(String, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    operation_type = Column(String, nullable=True)
    cost_snapshot_usd = Column(Float, nullable=True)
    successful = Column(Boolean, nullable=True)
    cached = Column(Boolean, nullable=True)
    note = Column(Text, nullable=True)
    prompt_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())
