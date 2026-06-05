"""
WhatsApp integration test — runs without a live call.

Tests:
  1. Send a WhatsApp prompt to a number (POST /send-whatsapp)
  2. Simulate an incoming WhatsApp photo (POST /whatsapp/incoming)
  3. Poll for the insight (POST /check-scene-image)
  4. Confirm the insight is saved on the incident in the DB

Usage:
    cd backend
    python test_whatsapp.py --phone +2348XXXXXXXXX

Requirements:
  - uvicorn running:  uvicorn main:app --reload --port 8000
  - .env loaded with real TWILIO_* and OPENAI_API_KEY values
  - The test phone number must have joined the Twilio WhatsApp sandbox
  - At least one incident in DB (run a dispatch test first), OR pass --incident-id
"""

import argparse
import json
import sys
import time
import requests
from dotenv import load_dotenv
import os

load_dotenv()

BASE = "http://localhost:8000"
SEP = "-" * 60


def ok(label: str, data: dict):
    print(f"\n✓  {label}")
    print(json.dumps(data, indent=2))


def fail(label: str, resp: requests.Response):
    print(f"\n✗  {label} — HTTP {resp.status_code}")
    print(resp.text)
    sys.exit(1)


def get_latest_incident_id() -> str:
    resp = requests.get(f"{BASE}/incidents")
    if resp.status_code != 200:
        print("Could not fetch incidents. Is uvicorn running?")
        sys.exit(1)
    incidents = resp.json()
    active = [i for i in incidents if i["status"] in ("pending", "active")]
    if not active:
        print("No active incidents found. Run a /dispatch test first:")
        print("""
  curl -X POST http://localhost:8000/dispatch \\
    -H "Content-Type: application/json" \\
    -d '{
      "arguments": {
        "emergency_type": "medical",
        "location": "Lekki Phase 1",
        "severity": "critical",
        "details": "Test incident for WhatsApp flow",
        "caller_phone": "REPLACE_WITH_YOUR_PHONE"
      },
      "agent_id": "test", "conversation_id": "test", "call_id": "test"
    }'
        """)
        sys.exit(1)
    return active[0]["id"]


def step1_send_whatsapp(phone: str, incident_id: str):
    print(f"\n{SEP}\nSTEP 1 — Send WhatsApp prompt to {phone}\n{SEP}")
    resp = requests.post(
        f"{BASE}/send-whatsapp",
        json={
            "arguments": {
                "caller_phone": phone,
                "incident_id": incident_id,
            },
            "agent_id": "test",
            "conversation_id": "test",
            "call_id": "test",
        },
    )
    if resp.status_code != 200:
        fail("send-whatsapp", resp)
    data = resp.json()
    ok("WhatsApp message sent", data)

    if data.get("status") != "sent":
        print(f"\n⚠  status={data.get('status')} — check TWILIO_WHATSAPP_NUMBER in .env")
        print("   Also confirm this number has joined the Twilio sandbox:")
        print(f"   Send 'join <sandbox-word>' to {os.environ.get('TWILIO_WHATSAPP_NUMBER', 'your WhatsApp number')} on WhatsApp")
        sys.exit(1)

    print(f"\n   → Check WhatsApp on {phone} — you should have a message from First Response.")
    print("   → Reply to that message with any photo.")


def step2_wait_for_photo(phone: str, incident_id: str, timeout: int = 120):
    print(f"\n{SEP}\nSTEP 2 — Waiting for you to send a WhatsApp photo (timeout {timeout}s)\n{SEP}")
    print("   Send any photo as a reply to the WhatsApp message now...")

    start = time.time()
    while time.time() - start < timeout:
        elapsed = int(time.time() - start)
        resp = requests.post(
            f"{BASE}/check-scene-image",
            json={
                "arguments": {"incident_id": incident_id},
                "agent_id": "test",
                "conversation_id": "test",
                "call_id": "test",
            },
        )
        if resp.status_code != 200:
            fail("check-scene-image", resp)

        data = resp.json()
        if data.get("status") == "ready":
            return data
        elif data.get("status") == "error":
            print(f"\n✗  Error: {data.get('message')}")
            sys.exit(1)

        print(f"   [{elapsed}s] Waiting for photo... (status: not_ready)", end="\r")
        time.sleep(5)

    print(f"\n\n✗  Timed out after {timeout}s — no photo received.")
    print("   Make sure:")
    print("   1. Your number has joined the Twilio WhatsApp sandbox")
    print("   2. The sandbox incoming webhook is set to:")
    print("      http://localhost:8000/whatsapp/incoming  (via ngrok)")
    print("   3. You replied with a photo (not text) to the WhatsApp message")
    sys.exit(1)


def step3_verify_insight(incident_id: str, insight_data: dict):
    print(f"\n{SEP}\nSTEP 3 — Verify insight saved on incident\n{SEP}")
    ok("GPT-4o scene analysis result", insight_data)

    resp = requests.get(f"{BASE}/incident/{incident_id}")
    if resp.status_code != 200:
        fail("get incident", resp)

    incident = resp.json()
    if incident.get("image_insight"):
        print(f"\n✓  Insight confirmed on incident {incident_id[:8]}")
        print(f"   image_url:     {incident.get('image_url', '')[:80]}...")
        print(f"   image_insight: {incident.get('image_insight', '')[:120]}...")
    else:
        print("\n✗  image_insight not saved on incident — check /whatsapp/incoming handler")
        sys.exit(1)


def step4_simulate_incoming(phone: str, incident_id: str):
    """
    Alternative to waiting for a real photo — simulate the Twilio webhook
    with a public test image URL. Use --simulate flag to skip the real photo wait.
    """
    print(f"\n{SEP}\nSTEP 2 (simulated) — Fake incoming WhatsApp photo\n{SEP}")

    # Public domain accident scene image for testing
    test_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"

    # Simulate Twilio's form POST — note: signature validation is skipped when TWILIO_AUTH_TOKEN not set
    resp = requests.post(
        f"{BASE}/whatsapp/incoming",
        data={
            "From": f"whatsapp:{phone}",
            "To": f"whatsapp:{os.environ.get('TWILIO_WHATSAPP_NUMBER', '')}",
            "NumMedia": "1",
            "MediaUrl0": test_image_url,
            "MediaContentType0": "image/png",
            "Body": "",
        },
    )
    if resp.status_code not in (200, 204):
        fail("whatsapp/incoming (simulated)", resp)

    print("   Simulated incoming photo webhook sent. Waiting 10s for GPT-4o to process...")
    time.sleep(10)

    # Now poll
    resp = requests.post(
        f"{BASE}/check-scene-image",
        json={
            "arguments": {"incident_id": incident_id},
            "agent_id": "test",
            "conversation_id": "test",
            "call_id": "test",
        },
    )
    if resp.status_code != 200:
        fail("check-scene-image", resp)
    return resp.json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test WhatsApp integration end to end")
    parser.add_argument("--phone", required=True, help="Your WhatsApp number in E.164 format e.g. +2348012345678")
    parser.add_argument("--incident-id", help="Use a specific incident ID instead of the latest active one")
    parser.add_argument("--simulate", action="store_true", help="Skip real photo — simulate the Twilio webhook with a test image")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds to wait for real photo (default 120)")
    args = parser.parse_args()

    print(f"\nFirst Response — WhatsApp Integration Test")
    print(f"Base URL : {BASE}")
    print(f"Phone    : {args.phone}")
    print(f"Mode     : {'simulated' if args.simulate else 'live'}")

    incident_id = args.incident_id or get_latest_incident_id()
    print(f"Incident : {incident_id[:8]}...")

    step1_send_whatsapp(args.phone, incident_id)

    if args.simulate:
        insight_data = step4_simulate_incoming(args.phone, incident_id)
    else:
        print(f"\n   Waiting up to {args.timeout}s for you to reply with a photo on WhatsApp...")
        insight_data = step2_wait_for_photo(args.phone, incident_id, timeout=args.timeout)

    step3_verify_insight(incident_id, insight_data)

    print(f"\n{SEP}")
    print("ALL STEPS PASSED")
    print(f"{SEP}")
    print("""
What this confirmed:
  ✓ POST /send-whatsapp    → Twilio sent WhatsApp message to caller
  ✓ POST /whatsapp/incoming → Photo received, GPT-4o vision ran
  ✓ POST /check-scene-image → Agent can poll and get the insight
  ✓ GET  /incident/:id     → insight saved on the incident record

On a live call the agent will:
  1. Call send_whatsapp_prompt  → message arrives on caller's WhatsApp
  2. Tell caller: "I've just sent you a WhatsApp message, please reply with a photo"
  3. Call check_scene_image every 15s until ready
  4. Read the insight aloud: "I can see from your photo that..."
""")
