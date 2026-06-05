# run_once_setup.py  (create this file, run it, then delete it)
import os
from dotenv import load_dotenv
from aethexai import AethexAI

load_dotenv()
client = AethexAI(api_key=os.environ["AETHEX_API_KEY"])
AGENT_ID = "YOUR_AGENT_ID_HERE"   # from Aethex dashboard
APP_URL  = os.environ["APP_URL"]

# Register dispatch tool
tool = client.add_agent_tool(
    AGENT_ID,
    name="dispatch_emergency",
    description="Call this as soon as emergency_type and location are confirmed. Do not wait for the call to end.",
    parameters={
        "type": "object",
        "properties": {
            "emergency_type": {"type": "string", "enum": ["medical", "fire"]},
            "location":       {"type": "string", "description": "Full location from caller"},
            "severity":       {"type": "string", "enum": ["critical", "moderate", "low"]},
            "details":        {"type": "string"},
            "caller_phone":   {"type": "string"},
        },
        "required": ["emergency_type", "location", "severity"],
    },
    endpoint_url=f"{APP_URL}/dispatch",
)
print("Tool registered:", tool["id"])
