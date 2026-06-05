import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    emergency_type = Column(String(50), nullable=False)
    location_text = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)
    details = Column(Text)
    caller_phone = Column(String(20))
    status = Column(String(20), default="pending", nullable=False)
    assigned_responder_id = Column(UUID(as_uuid=True), ForeignKey("responders.id"), nullable=True)
    eta_minutes = Column(Integer, nullable=True)
    acknowledged_at = Column(TIMESTAMP, nullable=True)
    transcript = Column(JSONB, nullable=True)
    image_url = Column(Text, nullable=True)
    image_insight = Column(Text, nullable=True)
    conversation_id = Column(String(100), nullable=True)

    assigned_responder = relationship("Responder", back_populates="current_incidents", foreign_keys=[assigned_responder_id])
    ping_logs = relationship("PingLog", back_populates="incident")
