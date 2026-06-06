import os
import json
import uuid
import asyncio
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import cast, Text
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator
from database import get_db
from models.incident import Incident
from services.twilio_service import send_whatsapp

router = APIRouter()

WHATSAPP_PROMPT = (
    "Hi, this is First Response emergency dispatch. "
    "Please reply to this message with a clear photo of the scene right now. "
    "Your photo will help us guide you better."
)


@router.post("/send-whatsapp")
async def send_whatsapp_prompt(request: Request, db: Session = Depends(get_db)):
    """
    Agent tool: send the caller a WhatsApp message asking for a scene photo.
    Aethex tool call body: { "arguments": { "incident_id": "..." }, "call_id": "...", ... }
    caller_phone is resolved from the incident or the Aethex call metadata.
    """
    raw = await request.body()
    payload = json.loads(raw) if raw else {}
    args = payload.get("arguments", payload)

    incident_id = args.get("incident_id", "")
    # Agent may still pass caller_phone — accept it as a fallback
    caller_phone_arg = args.get("caller_phone", "").replace("whatsapp:", "").strip()

    # Resolve incident
    incident = None
    if incident_id:
        try:
            uuid.UUID(incident_id)
            incident = db.query(Incident).filter(Incident.id == incident_id).first()
        except ValueError:
            incident = (
                db.query(Incident)
                .filter(cast(Incident.id, Text).like(f"{incident_id}%"))
                .order_by(Incident.created_at.desc())
                .first()
            )

    # Fallback: most recent active incident if no incident_id given
    if not incident:
        incident = (
            db.query(Incident)
            .filter(Incident.status.in_(["pending", "active"]))
            .order_by(Incident.created_at.desc())
            .first()
        )

    if not incident:
        return {"status": "error", "message": "No active incident found"}

    # Resolve phone: incident record → arg passed by agent → give up
    caller_phone = (incident.caller_phone or caller_phone_arg or "").replace("whatsapp:", "").strip()

    if not caller_phone:
        return {
            "status": "error",
            "message": "No caller phone on record. Ask the caller for their number and try again.",
        }

    try:
        await send_whatsapp(caller_phone, WHATSAPP_PROMPT)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Could not send WhatsApp message: {e}",
        }

    # Persist caller_phone on incident for incoming photo matching
    if not incident.caller_phone:
        incident.caller_phone = caller_phone
        db.commit()

    return {
        "status": "sent",
        "message": "WhatsApp message sent to caller. Tell them: I have just sent you a WhatsApp message, please reply with a photo of the scene.",
    }

_validator = RequestValidator(os.environ.get("TWILIO_AUTH_TOKEN", ""))


@router.post("/whatsapp/incoming", response_class=PlainTextResponse)
async def whatsapp_incoming(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())

    # Validate Twilio signature — only in production (skip locally)
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    is_production = "railway.app" in os.environ.get("APP_URL", "")
    if is_production and auth_token:
        sig = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url)
        validator = RequestValidator(auth_token)
        if not validator.validate(url, form, sig):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    media_url = form.get("MediaUrl0", "")
    num_media = int(form.get("NumMedia", "0"))
    from_number = form.get("From", "")

    if num_media == 0 or not media_url:
        return ""

    # Match incident by caller phone first, fall back to most recent active
    incident = (
        db.query(Incident)
        .filter(
            Incident.status.in_(["pending", "active"]),
            Incident.caller_phone == from_number.replace("whatsapp:", ""),
        )
        .order_by(Incident.created_at.desc())
        .first()
    )
    if not incident:
        incident = (
            db.query(Incident)
            .filter(Incident.status.in_(["pending", "active"]))
            .order_by(Incident.created_at.desc())
            .first()
        )

    if not incident:
        return ""

    # Run vision analysis in background so we respond to Twilio immediately
    incident_id = str(incident.id)
    asyncio.create_task(_analyze_and_store(incident_id, media_url, auth_token))

    return ""


async def _analyze_and_store(incident_id: str, media_url: str, twilio_auth_token: str):
    """Fetch the image (with Twilio auth), run GPT-4o vision, store the insight."""
    from database import SessionLocal
    import httpx, base64

    try:
        # Twilio media URLs require HTTP Basic auth with account SID + auth token
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                media_url,
                auth=(account_sid, twilio_auth_token),
                follow_redirects=True,
                timeout=15,
            )
            resp.raise_for_status()
            image_b64 = base64.b64encode(resp.content).decode("utf-8")
            content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]

        # Build a data URL so openai_service doesn't need to re-fetch
        data_url = f"data:{content_type};base64,{image_b64}"
        insight = await _analyze_data_url(data_url, content_type)

        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == incident_id).first()
            if incident:
                incident.image_url = media_url
                incident.image_insight = insight
                db.commit()
        finally:
            db.close()

    except Exception as e:
        # Log but don't crash — the call must continue
        import logging
        logging.getLogger(__name__).error(f"WhatsApp image analysis failed: {e}")


async def _analyze_data_url(data_url: str, content_type: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    result = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are an emergency response AI. Analyze this scene photo and provide "
                            "a concise 2-3 sentence assessment for an emergency dispatcher. "
                            "Focus on: visible injuries or hazards, immediate actions the bystander "
                            "should take, any safety concerns. Be direct and calm. "
                            "Do not speculate beyond what is visible."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            }
        ],
        max_tokens=200,
    )
    return result.choices[0].message.content.strip()
