import asyncio
import logging
import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

_client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
_from_number = os.environ["TWILIO_PHONE_NUMBER"]


def _send_sms_sync(to: str, body: str) -> str:
    msg = _client.messages.create(body=body, from_=_from_number, to=to)
    logger.info("SMS sent to=%s sid=%s status=%s", to, msg.sid, msg.status)
    if msg.error_code:
        logger.error("SMS error to=%s code=%s message=%s", to, msg.error_code, msg.error_message)
    return msg.sid


async def send_sms(to: str, body: str) -> str:
    return await asyncio.to_thread(_send_sms_sync, to, body)


async def send_sms_bulk(recipients: list[tuple[str, str]]) -> list[dict]:
    tasks = [asyncio.to_thread(_send_sms_sync, phone, msg) for phone, msg in recipients]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [
        {"phone": phone, "sid": r} if not isinstance(r, Exception)
        else {"phone": phone, "error": str(r)}
        for (phone, _), r in zip(recipients, results)
    ]


def _send_whatsapp_sync(to: str, body: str) -> str:
    whatsapp_from = f"whatsapp:{os.environ['TWILIO_WHATSAPP_NUMBER']}"
    whatsapp_to = f"whatsapp:{to}" if not to.startswith("whatsapp:") else to
    msg = _client.messages.create(body=body, from_=whatsapp_from, to=whatsapp_to)
    logger.info("WhatsApp sent to=%s sid=%s status=%s", whatsapp_to, msg.sid, msg.status)
    if msg.error_code:
        logger.error("WhatsApp error to=%s code=%s message=%s", whatsapp_to, msg.error_code, msg.error_message)
    return msg.sid


async def send_whatsapp(to: str, body: str) -> str:
    return await asyncio.to_thread(_send_whatsapp_sync, to, body)


def build_responder_sms(incident, responder, app_url: str) -> str:
    ack_url = f"{app_url}/respond?incident_id={incident.id}&responder_id={responder.id}"
    return (
        f"FIRST RESPONSE DISPATCH\n"
        f"Type: {incident.emergency_type.upper()}\n"
        f"Location: {incident.location_text}\n"
        f"Severity: {incident.severity}\n"
        f"Details: {incident.details or 'N/A'}\n"
        f"Caller: {incident.caller_phone or 'Unknown'}\n\n"
        f"Confirm en route:\n{ack_url}"
    )
