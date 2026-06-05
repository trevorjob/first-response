from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from database import get_db
from models.responder import Responder

router = APIRouter()


class ResponderOut(BaseModel):
    id: UUID
    name: str
    phone: str
    type: str
    zone: str
    is_available: bool
    current_incident_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResponderPatch(BaseModel):
    is_available: bool


@router.get("/responders", response_model=list[ResponderOut])
def list_responders(db: Session = Depends(get_db)):
    return db.query(Responder).order_by(Responder.zone, Responder.name).all()


@router.patch("/responders/{responder_id}", response_model=ResponderOut)
def patch_responder(responder_id: str, body: ResponderPatch, db: Session = Depends(get_db)):
    responder = db.query(Responder).filter(Responder.id == responder_id).first()
    if not responder:
        raise HTTPException(status_code=404, detail="Responder not found")
    responder.is_available = body.is_available
    db.commit()
    db.refresh(responder)
    return responder
