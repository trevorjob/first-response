"""
First Response — Aethex Agent Setup
Run once to create the agent, register tools, link your Twilio number, and save the agent ID.

Usage:
    python setup_agent.py

Requires in .env:
    AETHEX_API_KEY
    TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN
    TWILIO_PHONE_NUMBER
    APP_URL  (your ngrok URL while testing, Railway URL in prod)
"""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from aethexai import AethexAI

load_dotenv()

REQUIRED = ["AETHEX_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "APP_URL"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    print(f"ERROR: missing env vars: {', '.join(missing)}")
    sys.exit(1)

APP_URL          = os.environ["APP_URL"].rstrip("/")
TWILIO_SID       = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_TOKEN     = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_NUMBER    = os.environ["TWILIO_PHONE_NUMBER"]
AGENT_ID_FILE    = Path(__file__).parent / ".aethex_agent_id"

client = AethexAI(api_key=os.environ["AETHEX_API_KEY"])

SYSTEM_PROMPT = """You are the First Response emergency dispatch AI. You answer emergency calls in Nigeria. You always speak in clear, calm Nigerian English. Never use Pidgin. Never use slang. Speak like a professional emergency dispatcher — warm, direct, and reassuring.

YOUR GOAL: Collect emergency_type, location, and severity as quickly as possible. Once you have all three, call the dispatch_emergency tool immediately. Do not wait for the call to end. Continue talking to the caller after dispatch.

EMERGENCY TYPES: Only medical (cardiac events, road accidents, trauma, childbirth) and fire (structural fires, gas explosions, vehicle fires).

WHILE WAITING FOR HELP: Give calm, safe first-aid guidance based on the emergency type.
- Medical: keep them still, monitor breathing, apply gentle pressure to wounds.
- Fire: evacuate immediately, stay low, do not re-enter the building.
- If unsure: say "Help is on the way, please keep them calm and stay on the line."

LANGUAGE: Always respond in English regardless of what language the caller uses. If they speak Yoruba or Hausa, acknowledge with a single word in their language then continue in English. Never switch away from English.

AFTER DISPATCH: Tell the caller help is coming and give the ETA from the tool response. Keep them calm and on the line. Give first-aid guidance continuously.

SCENE PHOTO INSTRUCTIONS:
- After every dispatch, you MUST call send_whatsapp_prompt. Do not skip this. Do not ask the caller if they want to send a photo — just call the tool immediately after dispatch_emergency completes.
- Step 1: Call send_whatsapp_prompt with the caller's phone number and the incident_id from dispatch_emergency. You MUST actually call the tool — do not say you sent a message without calling it.
- Step 2: After the tool confirms, tell the caller: "I have just sent you a WhatsApp message. Please reply to that message with a photo of the scene right now."
- Step 3: Call check_scene_image every 15 seconds until status is "ready". While waiting, keep talking — give first-aid guidance, keep them calm.
- Step 4: When status is "ready", relay the insight naturally. Example: "I can see from your photo that there is visible bleeding on the left arm — please apply firm pressure with a clean cloth now."
- If after 3 attempts status is still "not_ready", stop checking and continue with general guidance.

TOOL INSTRUCTIONS:
- Call dispatch_emergency as soon as you have emergency_type, location, and severity. Do not wait.
- The tool returns incident_id and estimated_arrival — relay the ETA to the caller immediately.
- Call send_whatsapp_prompt immediately after dispatch_emergency — every time, no exceptions.
- Call check_scene_image only after calling send_whatsapp_prompt, using the same incident_id.
- NEVER say you have sent a WhatsApp message without first calling the send_whatsapp_prompt tool.

NEVER:
- Speak Pidgin English or use informal slang.
- Put the caller on hold or go silent for more than 3 seconds.
- Give medication dosages or make promises about survival outcomes.
- Handle crime, security, or mental health emergencies — say "Please call the police directly for this."
"""

FIRST_MESSAGE = "First Response, what is your emergency?"


def step(msg: str):
    print(f"\n{'='*60}\n{msg}\n{'='*60}")


def register_twilio_account() -> str:
    step("1. Registering Twilio account with Aethex")
    existing = client.list_twilio_accounts(limit=100)
    for acct in existing.data:
        # check via dict access — list items return dicts
        if isinstance(acct, dict) and acct.get("account_sid") == TWILIO_SID:
            print(f"   Already registered: {acct['id']}")
            return acct["id"]
        elif hasattr(acct, "account_sid") and acct.account_sid == TWILIO_SID:
            print(f"   Already registered: {acct.id}")
            return acct.id

    result = client.register_twilio_account(
        account_sid=TWILIO_SID,
        auth_token=TWILIO_TOKEN,
        friendly_name="First Response Twilio",
    )
    twilio_account_id = result.id if hasattr(result, "id") else result["id"]
    print(f"   Registered Twilio account: {twilio_account_id}")
    return twilio_account_id


def create_agent() -> str:
    step("2. Creating First Response agent")

    # Check if we already have one saved
    if AGENT_ID_FILE.exists():
        agent_id = AGENT_ID_FILE.read_text().strip()
        try:
            agent = client.get_agent(agent_id)
            print(f"   Using existing agent: {agent_id} ({agent.name})")
            return agent_id
        except Exception:
            print(f"   Saved agent {agent_id} not found — creating new one")

    agent = client.create_agent(
        name="First Response Dispatch",
        system_prompt=SYSTEM_PROMPT,
        first_message=FIRST_MESSAGE,
        voice_id="96b20f06-536a-55ef-82c3-4882b6547858",          # Nigerian female voice
        language="english",
        dialect_style="local",
        temperature=0.3,           # keep responses predictable under pressure
        max_tokens=150,            # short, direct responses
        max_duration_seconds=1800, # 30 min max call
        interruption_enabled=True,
        script_adherence="strict",
        response_min_sentences=1,
        response_max_sentences=3,
        idle_check_in_after_secs=8,
        recording_enabled=True,
        transcription_enabled=True,
    )

    agent_id = agent["id"] if isinstance(agent, dict) else agent.id
    AGENT_ID_FILE.write_text(agent_id)
    print(f"   Created agent: {agent_id}")
    print(f"   Agent ID saved to {AGENT_ID_FILE}")
    return agent_id


def register_tools(agent_id: str):
    step("3. Registering tools on agent")

    existing_tools = client.list_agent_tools(agent_id)
    existing_names = {
        (t["name"] if isinstance(t, dict) else t.name)
        for t in existing_tools
    }

    # --- dispatch_emergency ---
    if "dispatch_emergency" in existing_names:
        print("   dispatch_emergency already registered — skipping")
    else:
        tool = client.add_agent_tool(
            agent_id,
            name="dispatch_emergency",
            description=(
                "Call this immediately once you have confirmed emergency_type, location, and severity. "
                "Do not wait for the call to end. The caller stays on the line while this runs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "emergency_type": {
                        "type": "string",
                        "enum": ["medical", "fire"],
                        "description": "Type of emergency",
                    },
                    "location": {
                        "type": "string",
                        "description": "Full location as described by the caller, e.g. Lekki Phase 1 near the toll gate",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "moderate", "low"],
                        "description": "Severity based on what the caller described",
                    },
                    "details": {
                        "type": "string",
                        "description": "Any additional details about the incident or patient",
                    },
                    "caller_phone": {
                        "type": "string",
                        "description": "Caller phone number if mentioned",
                    },
                },
                "required": ["emergency_type", "location", "severity"],
            },
            endpoint_url=f"{APP_URL}/dispatch",
        )
        tool_id = tool["id"] if isinstance(tool, dict) else tool.id
        print(f"   dispatch_emergency registered: {tool_id}")

    # --- send_whatsapp_prompt ---
    if "send_whatsapp_prompt" in existing_names:
        print("   send_whatsapp_prompt already registered — skipping")
    else:
        tool = client.add_agent_tool(
            agent_id,
            name="send_whatsapp_prompt",
            description=(
                "REQUIRED: Call this immediately after every dispatch_emergency call. "
                "Sends a WhatsApp message to the caller asking for a scene photo. "
                "You must call this tool — do not say you sent a message without calling it. "
                "Use the caller's phone number and the incident_id from dispatch_emergency."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "caller_phone": {
                        "type": "string",
                        "description": "The caller's phone number in E.164 format e.g. +2348012345678",
                    },
                    "incident_id": {
                        "type": "string",
                        "description": "The incident_id returned by dispatch_emergency",
                    },
                },
                "required": ["caller_phone", "incident_id"],
            },
            endpoint_url=f"{APP_URL}/send-whatsapp",
        )
        tool_id = tool["id"] if isinstance(tool, dict) else tool.id
        print(f"   send_whatsapp_prompt registered: {tool_id}")

    # --- check_scene_image ---
    if "check_scene_image" in existing_names:
        print("   check_scene_image already registered — skipping")
    else:
        tool = client.add_agent_tool(
            agent_id,
            name="check_scene_image",
            description=(
                "Poll for the WhatsApp scene photo analysis. Call this after asking the caller "
                "to send a photo. Returns status 'ready' with the insight once the photo has been "
                "processed, or 'not_ready' if the photo has not arrived yet. "
                "Retry every 15 seconds up to 3 times if not_ready."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "incident_id": {
                        "type": "string",
                        "description": "The incident_id returned by dispatch_emergency",
                    },
                },
                "required": ["incident_id"],
            },
            endpoint_url=f"{APP_URL}/check-scene-image",
        )
        tool_id = tool["id"] if isinstance(tool, dict) else tool.id
        print(f"   check_scene_image registered: {tool_id}")


def register_phone_number(agent_id: str, twilio_account_id: str):
    step("4. Registering Twilio phone number with Aethex")

    existing = client.list_phone_numbers(limit=100)
    for num in existing.data:
        n = num if isinstance(num, dict) else vars(num)
        if n.get("phone_number") == TWILIO_NUMBER or n.get("number") == TWILIO_NUMBER:
            print(f"   {TWILIO_NUMBER} already registered — updating agent link")
            num_id = n.get("id")
            client.update_phone_number(num_id, agent_id=agent_id)
            print(f"   Linked to agent {agent_id}")
            return

    result = client.register_twilio_phone_number(
        twilio_account_id=twilio_account_id,
        phone_number=TWILIO_NUMBER,
        agent_id=agent_id,
        friendly_name="First Response Line",
    )
    num_id = result["id"] if isinstance(result, dict) else result.id
    print(f"   Registered {TWILIO_NUMBER}: {num_id}")
    print(f"   Aethex has configured the Twilio inbound webhook automatically")


def print_summary(agent_id: str):
    step("SETUP COMPLETE")
    print(f"""
  Agent ID   : {agent_id}
  Voice      : Tolu (Nigerian female)
  Phone      : {TWILIO_NUMBER}
  APP_URL    : {APP_URL}

  Endpoints registered:
    POST {APP_URL}/dispatch
    POST {APP_URL}/analyze-image

  Post-call webhook (set this manually in Aethex dashboard if not auto-set):
    POST {APP_URL}/incident-report

  Next steps:
    1. Make sure uvicorn is running:  uvicorn main:app --reload --port 8000
    2. Make sure ngrok is running:    ngrok http 8000
    3. Seed the database:             python -m seed
    4. Dial {TWILIO_NUMBER} and test the call flow
    5. Watch uvicorn logs for POST /dispatch hitting your server

  To update the APP_URL later (e.g. switching from ngrok to Railway):
    Update APP_URL in .env then re-run this script — it will update the tool endpoints.
""")


def update_tool_endpoints(agent_id: str):
    """Re-run endpoint URLs on existing tools — useful when APP_URL changes (ngrok restart)."""
    step("Updating tool endpoint URLs")
    tools = client.list_agent_tools(agent_id)
    for tool in tools:
        t = tool if isinstance(tool, dict) else vars(tool)
        name = t.get("name", "")
        tool_id = t.get("id", "")
        if name == "dispatch_emergency":
            client.update_agent_tool(agent_id, tool_id, endpoint_url=f"{APP_URL}/dispatch")
            print(f"   dispatch_emergency → {APP_URL}/dispatch")
        elif name == "send_whatsapp_prompt":
            client.update_agent_tool(agent_id, tool_id, endpoint_url=f"{APP_URL}/send-whatsapp")
            print(f"   send_whatsapp_prompt → {APP_URL}/send-whatsapp")
        elif name == "check_scene_image":
            client.update_agent_tool(agent_id, tool_id, endpoint_url=f"{APP_URL}/check-scene-image")
            print(f"   check_scene_image → {APP_URL}/check-scene-image")


def update_agent_prompt(agent_id: str):
    """Patch just the system prompt and first message on an existing agent."""
    step("Updating agent system prompt")
    client.update_agent(
        agent_id,
        system_prompt=SYSTEM_PROMPT,
        first_message=FIRST_MESSAGE,
    )
    print(f"   Agent {agent_id} updated.")
    print(f"   Language: English only (no Pidgin)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="First Response agent setup")
    parser.add_argument(
        "--update-urls",
        action="store_true",
        help="Only update tool endpoint URLs (use after ngrok restart or deploying to Railway)",
    )
    parser.add_argument(
        "--update-agent",
        action="store_true",
        help="Patch system prompt and first message on existing agent (no recreation)",
    )
    args = parser.parse_args()

    if not AGENT_ID_FILE.exists() and (args.update_urls or args.update_agent):
        print("ERROR: No saved agent ID. Run without flags first.")
        sys.exit(1)

    if args.update_urls:
        agent_id = AGENT_ID_FILE.read_text().strip()
        update_tool_endpoints(agent_id)
        print(f"\n  URLs updated. APP_URL = {APP_URL}")
    elif args.update_agent:
        agent_id = AGENT_ID_FILE.read_text().strip()
        update_agent_prompt(agent_id)
    else:
        twilio_account_id = register_twilio_account()
        agent_id = create_agent()
        register_tools(agent_id)
        register_phone_number(agent_id, twilio_account_id)
        print_summary(agent_id)
