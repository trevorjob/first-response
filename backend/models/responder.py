import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class Responder(Base):
    __tablename__ = "responders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    type = Column(String(20), nullable=False)
    zone = Column(String(100), nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    current_incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    current_incidents = relationship("Incident", back_populates="assigned_responder", foreign_keys="Incident.assigned_responder_id")
    ping_logs = relationship("PingLog", back_populates="responder")
