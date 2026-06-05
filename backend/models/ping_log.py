import uuid
from datetime import datetime
from sqlalchemy import Column, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class PingLog(Base):
    __tablename__ = "ping_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    responder_id = Column(UUID(as_uuid=True), ForeignKey("responders.id"), nullable=False)
    sent_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    acknowledged = Column(Boolean, default=False, nullable=False)

    incident = relationship("Incident", back_populates="ping_logs")
    responder = relationship("Responder", back_populates="ping_logs")
