from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models.incident import Incident

router = APIRouter()


class ResponderOut(BaseModel):
    id: UUID
    name: str
    phone: str
    type: str
    zone: str

    model_config = {"from_attributes": True}


class IncidentOut(BaseModel):
    id: UUID
    created_at: datetime
    emergency_type: str
    location_text: str
    severity: str
    details: str | None
    caller_phone: str | None
    status: str
    assigned_responder_id: UUID | None
    eta_minutes: int | None
    acknowledged_at: datetime | None
    image_url: str | None
    image_insight: str | None
    conversation_id: str | None
    transcript: Any
    assigned_responder: ResponderOut | None = None

    model_config = {"from_attributes": True}


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    return (
        db.query(Incident)
        .options(joinedload(Incident.assigned_responder))
        .order_by(Incident.created_at.desc())
        .all()
    )


@router.get("/incident/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = (
        db.query(Incident)
        .options(joinedload(Incident.assigned_responder))
        .filter(Incident.id == incident_id)
        .first()
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
