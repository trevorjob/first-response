import asyncio
import base64
import json
import logging
import os
import uuid
from fastapi import APIRouter, Request, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import cast, Text
from sqlalchemy.orm import Session
from database import get_db
from models.incident import Incident
from services.twilio_service import send_whatsapp

logger = logging.getLogger(__name__)

router = APIRouter()

WHATSAPP_PROMPT = (
    "Hi, this is First Response emergency dispatch. "
    "Please reply to this message with a clear photo of the scene right now. "
    "Your photo will help us guide you better."
)


@router.post("/send-whatsapp")
async def send_whatsapp_prompt(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    payload = json.loads(raw) if raw else {}
    args = payload.get("arguments", payload)
    incident_id = args.get("incident_id", "")

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

    if not incident:
        incident = (
            db.query(Incident)
            .filter(Incident.status.in_(["pending", "active"]))
            .order_by(Incident.created_at.desc())
            .first()
        )

    if not incident:
        return {"status": "error", "message": "No active incident found"}

    to_number = os.environ.get("TEST_WHATSAPP_NUMBER", "+2348104899622")

    try:
        await send_whatsapp(to_number, WHATSAPP_PROMPT)
        logger.info("WhatsApp prompt sent to %s for incident %s", to_number, str(incident.id)[:8])
    except Exception as e:
        logger.error("WhatsApp send failed: %s", e)
        return {"status": "error", "message": f"Could not send WhatsApp message: {e}"}

    if not incident.caller_phone:
        incident.caller_phone = to_number
        db.commit()

    return {
        "status": "sent",
        "message": "WhatsApp message sent to caller. Tell them: I have just sent you a WhatsApp message, please reply with a photo of the scene.",
    }


@router.post("/whatsapp/incoming", response_class=PlainTextResponse)
async def whatsapp_incoming(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())

    media_url = form.get("MediaUrl0", "")
    num_media = int(form.get("NumMedia", "0"))
    from_number = form.get("From", "").replace("whatsapp:", "")

    if num_media == 0 or not media_url:
        return ""

    incident = (
        db.query(Incident)
        .filter(
            Incident.status.in_(["pending", "active"]),
            Incident.caller_phone == from_number,
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
        logger.warning("WhatsApp photo received but no active incident found (from=%s)", from_number)
        return ""

    logger.info("WhatsApp photo received from %s, analysing for incident %s", from_number, str(incident.id)[:8])
    asyncio.create_task(_analyze_and_store(str(incident.id), media_url))
    return ""


async def _analyze_and_store(incident_id: str, media_url: str):
    from database import SessionLocal
    import httpx

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")

    try:
        async with httpx.AsyncClient() as http:
            # Step 1: get the redirect URL using Twilio auth
            head = await http.get(
                media_url,
                auth=(account_sid, auth_token),
                follow_redirects=False,
                timeout=10,
            )
            cdn_url = head.headers.get("location", media_url)

            # Step 2: fetch the actual image from CDN without auth
            resp = await http.get(cdn_url, follow_redirects=True, timeout=15)
            resp.raise_for_status()
            image_b64 = base64.b64encode(resp.content).decode("utf-8")
            content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]

        data_url = f"data:{content_type};base64,{image_b64}"
        insight = await _analyze_data_url(data_url)

        db = SessionLocal()
        try:
            incident = db.query(Incident).filter(Incident.id == incident_id).first()
            if incident:
                incident.image_url = media_url
                incident.image_insight = insight
                db.commit()
                logger.info("Scene image analysed for incident %s", incident_id[:8])
        finally:
            db.close()

    except Exception as e:
        logger.error("WhatsApp image analysis failed: %s", e)


async def _analyze_data_url(data_url: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    result = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{
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
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
        max_tokens=200,
    )
    return result.choices[0].message.content.strip()
