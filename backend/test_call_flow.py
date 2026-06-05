"""
Full call flow test script for First Response.

What this tests:
  - You call the number and speak naturally
  - This script monitors your backend in real time and tells you what's happening
  - After the call it verifies everything was saved correctly

Usage:
    cd backend
    python test_call_flow.py

Requirements:
  - uvicorn running: uvicorn main:app --reload --port 8000
  - ngrok running and APP_URL set in .env
  - Database seeded: python -m seed
"""

import time
import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "http://localhost:8000"
POLL_INTERVAL = 3  # seconds between status checks
SEP = "=" * 60


def clear_line():
    print("\r" + " " * 80 + "\r", end="")


def get_incidents():
    try:
        r = requests.get(f"{BASE}/incidents", timeout=5)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def watch_incident(incident_id: str):
    """Poll the incident until it reaches completed status or timeout."""
    print(f"\n  Watching incident {incident_id[:8]}...\n")
    last_status = None
    last_responders = None
    start = time.time()

    while time.time() - start < 300:  # 5 min timeout
        try:
            r = requests.get(f"{BASE}/incident/{incident_id}", timeout=5)
            if r.status_code != 200:
                time.sleep(POLL_INTERVAL)
                continue
            inc = r.json()
        except Exception:
            time.sleep(POLL_INTERVAL)
            continue

        status = inc.get("status")
        eta = inc.get("eta_minutes")
        responder_id = inc.get("assigned_responder_id")
        image_insight = inc.get("image_insight")
        transcript = inc.get("transcript")

        if status != last_status:
            print(f"  [{int(time.time()-start):>3}s] Status: {status.upper()}")
            last_status = status

        if responder_id and responder_id != last_responders:
            resp = inc.get("assigned_responder")
            name = resp.get("name", "Unknown") if resp else "Unknown"
            print(f"  [{int(time.time()-start):>3}s] Responder confirmed: {name} — ETA {eta} min")
            last_responders = responder_id

        if image_insight:
            print(f"  [{int(time.time()-start):>3}s] Scene photo analysed:")
            print(f"       \"{image_insight[:120]}...\"" if len(image_insight) > 120 else f"       \"{image_insight}\"")

        if status == "completed":
            print(f"\n  [{int(time.time()-start):>3}s] Call ended — transcript saved")
            if transcript:
                turns = transcript if isinstance(transcript, list) else []
                print(f"       {len(turns)} transcript turns recorded")
            return inc

        time.sleep(POLL_INTERVAL)

    print("\n  Timed out waiting for incident to complete.")
    return None


def print_summary(inc: dict):
    print(f"\n{SEP}")
    print("CALL SUMMARY")
    print(SEP)
    print(f"  Incident ID   : {str(inc.get('id',''))[:8]}")
    print(f"  Type          : {inc.get('emergency_type','').upper()}")
    print(f"  Location      : {inc.get('location_text','')}")
    print(f"  Severity      : {inc.get('severity','')}")
    print(f"  Status        : {inc.get('status','')}")
    print(f"  ETA           : {inc.get('eta_minutes', '—')} min")
    print(f"  Caller phone  : {inc.get('caller_phone','—')}")

    resp = inc.get("assigned_responder")
    if resp:
        print(f"  Responder     : {resp.get('name','')} ({resp.get('zone','')})")

    if inc.get("image_url"):
        print(f"  Scene photo   : ✓")
        print(f"  GPT-4o insight: {(inc.get('image_insight','')[:100])}...")

    transcript = inc.get("transcript") or []
    print(f"  Transcript    : {len(transcript)} turns")

    details = inc.get("details","")
    if "AI Summary" in (details or ""):
        print(f"\n  AI Summary:")
        summary = details.split("--- AI Summary ---")[-1].strip()
        for line in summary[:400].split("\n"):
            print(f"    {line}")

    print(f"\n{SEP}")


def main():
    print(f"\n{SEP}")
    print("FIRST RESPONSE — CALL FLOW TEST")
    print(SEP)

    # Check server is up
    try:
        r = requests.get(f"{BASE}/health", timeout=3)
        if r.status_code != 200:
            raise Exception()
        print(f"  ✓ Server is up at {BASE}")
    except Exception:
        print(f"  ✗ Cannot reach {BASE} — is uvicorn running?")
        sys.exit(1)

    # Check responders are seeded
    try:
        r = requests.get(f"{BASE}/responders", timeout=3)
        responders = r.json() if r.status_code == 200 else []
        available = [x for x in responders if x.get("is_available")]
        print(f"  ✓ {len(available)} responders available in DB")
        if len(available) == 0:
            print("  ✗ No available responders — run: python -m seed")
            sys.exit(1)
    except Exception:
        print("  ✗ Could not fetch responders")
        sys.exit(1)

    twilio_number = os.environ.get("TWILIO_PHONE_NUMBER", "your Twilio number")
    print(f"\n{SEP}")
    print("CALL SCRIPT")
    print(SEP)
    print(f"""
  DIAL: {twilio_number}

  ── STEP 1: Report the emergency ────────────────────────────
  When the agent answers, say:

    "Please help me, there is a man who has collapsed at
     Lekki Phase 1, near the toll gate. He fell and is not
     responding. I think it is a cardiac event."

  ── STEP 2: Answer follow-up questions ──────────────────────
  The agent will ask about severity / details. Say:

    "He is in his 50s, he is breathing but unconscious.
     There are about 3 people around him."

  ── STEP 3: Wait for dispatch confirmation ──────────────────
  The agent will confirm help is on the way with an ETA.
  This script will show you the dispatch hitting the server.

  ── STEP 4: Test the WhatsApp photo flow ────────────────────
  When the agent asks if you want to send a photo, say YES.
  The agent will say: "I've sent you a WhatsApp message,
  please reply with a photo of the scene."

  Open WhatsApp → find the message from First Response
  → reply with any photo (your camera, a saved image, anything).

  ── STEP 5: Hear the insight ────────────────────────────────
  The agent will read GPT-4o's analysis of your photo aloud.

  ── STEP 6: End the call ────────────────────────────────────
  Say: "Thank you, the ambulance is here."
  Then hang up.
""")

    snapshot_before = {i["id"] for i in get_incidents()}
    print(f"{SEP}")
    print("MONITORING — waiting for your call...")
    print(f"{SEP}\n")

    # Wait for a new incident to appear (agent called /dispatch)
    new_incident_id = None
    wait_start = time.time()
    print("  Waiting for dispatch tool call", end="", flush=True)

    while time.time() - wait_start < 600:  # 10 min to start the call
        current = get_incidents()
        new = [i for i in current if i["id"] not in snapshot_before]
        if new:
            new_incident_id = new[0]["id"]
            clear_line()
            print(f"  ✓ Dispatch received! Incident {new_incident_id[:8]} created")
            print(f"    Type     : {new[0].get('emergency_type','').upper()}")
            print(f"    Location : {new[0].get('location_text','')}")
            print(f"    Severity : {new[0].get('severity','')}")
            break
        print(".", end="", flush=True)
        time.sleep(POLL_INTERVAL)

    if not new_incident_id:
        print("\n\n  Timed out — no dispatch received.")
        print("  Make sure you dialled and the agent called the dispatch tool.")
        sys.exit(1)

    # Now watch until completed
    print(f"\n  Monitoring incident in real time (hang up when done)...\n")
    final = watch_incident(new_incident_id)

    if final:
        print_summary(final)
    else:
        print("\n  Call ended but incident not marked completed yet.")
        print(f"  Check the dashboard or run: GET {BASE}/incident/{new_incident_id}")


if __name__ == "__main__":
    main()
