"""
Tests the full WhatsApp image flow against the live Railway API.
Usage:
    cd backend
    python test_image_flow.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ.get("APP_URL", "http://localhost:8000").rstrip("/")
SEP = "=" * 60


def latest_incident():
    r = requests.get(f"{BASE}/incidents", timeout=10)
    r.raise_for_status()
    incidents = r.json()
    if not incidents:
        print("  No incidents in DB. Make a test call first.")
        return None
    return incidents[0]


def test_check_scene_image(incident_id: str, short: bool = False):
    id_to_send = incident_id[:8] if short else incident_id
    print(f"\n  POST /check-scene-image  (incident_id={id_to_send})")
    r = requests.post(
        f"{BASE}/check-scene-image",
        json={"arguments": {"incident_id": id_to_send}},
        timeout=10,
    )
    print(f"  Status: {r.status_code}")
    print(f"  Body  : {r.json()}")
    return r.json()


def test_send_whatsapp(incident_id: str):
    print(f"\n  POST /send-whatsapp  (incident_id={incident_id[:8]})")
    r = requests.post(
        f"{BASE}/send-whatsapp",
        json={"arguments": {"incident_id": incident_id[:8]}},
        timeout=10,
    )
    print(f"  Status: {r.status_code}")
    print(f"  Body  : {r.json()}")


def main():
    print(f"\n{SEP}")
    print("FIRST RESPONSE — IMAGE FLOW API TEST")
    print(f"BASE: {BASE}")
    print(SEP)

    inc = latest_incident()
    if not inc:
        return

    incident_id = inc["id"]
    print(f"\n  Latest incident : {incident_id[:8]}")
    print(f"  Type            : {inc.get('emergency_type','').upper()}")
    print(f"  Status          : {inc.get('status','')}")
    print(f"  image_insight   : {inc.get('image_insight') or '(none)'}")
    print(f"  image_url       : {inc.get('image_url') or '(none)'}")

    print(f"\n{SEP}")
    print("1. Check scene image — full UUID")
    result = test_check_scene_image(incident_id, short=False)

    print(f"\n{SEP}")
    print("2. Check scene image — 8-char prefix (what agent sends)")
    result = test_check_scene_image(incident_id, short=True)

    if result.get("status") == "not_ready":
        print(f"\n{SEP}")
        print("3. Sending WhatsApp prompt to trigger image flow")
        test_send_whatsapp(incident_id)
        print("\n  -> Send a photo to your WhatsApp sandbox number now")
        print("  -> Then run this script again to verify the insight is stored")
    else:
        print(f"\n{SEP}")
        print("RESULT: Image insight is present and endpoint returns it correctly.")
        print("If the agent is still saying it cannot analyze, the issue is the agent LLM,")
        print("not the backend. The system prompt fix should resolve it.")

    print(f"\n{SEP}\n")


if __name__ == "__main__":
    main()
