"""
Wipes all responders, incidents, and ping_logs, then seeds a single test responder.
Run from inside backend/:  python reset_responders.py
"""
import os
import uuid
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models.responder import Responder

engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
Session = sessionmaker(bind=engine)

YOUR_PHONE = "+2348104899622"

def reset():
    db = Session()
    try:
        # TRUNCATE CASCADE handles all FK dependencies in one shot
        db.execute(text("TRUNCATE TABLE ping_log, incidents, responders RESTART IDENTITY CASCADE"))
        db.commit()
        print("Cleared ping_log, incidents, responders")

        responder = Responder(
            id=uuid.uuid4(),
            name="Test Responder",
            phone=YOUR_PHONE,
            type="ambulance",
            zone="Lekki Phase 1",
            is_available=True,
        )
        db.add(responder)
        db.commit()
        print(f"Added 1 responder: {responder.name} ({responder.type}) — {responder.phone}")
    finally:
        db.close()

if __name__ == "__main__":
    reset()
