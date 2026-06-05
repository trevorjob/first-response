import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

from models.responder import Responder
from database import Base

engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)

RESPONDERS = [
    # --- Ambulance / Medical ---
    {"name": "EMS Lagos Unit 1",        "phone": "+2348104899622", "type": "ambulance", "zone": "Lekki Phase 1"},
    {"name": "EMS Lagos Unit 2",        "phone": "+2348104899622", "type": "ambulance", "zone": "Lekki Phase 2"},
    {"name": "Flying Doctors Unit A",   "phone": "+2348104899622", "type": "ambulance", "zone": "Victoria Island"},
    {"name": "Flying Doctors Unit B",   "phone": "+2348104899622", "type": "ambulance", "zone": "Ikoyi"},
    {"name": "Greenfield Ambulance 1",  "phone": "+2348104899622", "type": "ambulance", "zone": "Ikeja"},
    {"name": "Greenfield Ambulance 2",  "phone": "+2348104899622", "type": "ambulance", "zone": "Surulere"},
    {"name": "Reddington EMS",          "phone": "+2348104899622", "type": "ambulance", "zone": "Victoria Island"},
    {"name": "Lagos Island Medics",     "phone": "+2348104899622", "type": "ambulance", "zone": "Lagos Island"},
    {"name": "Apapa Medical Response",  "phone": "+2348104899622", "type": "ambulance", "zone": "Apapa"},
    {"name": "Yaba Rapid Response",     "phone": "+2348104899622", "type": "ambulance", "zone": "Yaba"},
    {"name": "Ajah EMS Unit",           "phone": "+2348104899622", "type": "ambulance", "zone": "Ajah"},
    {"name": "Gbagada Medics",          "phone": "+2348104899622", "type": "ambulance", "zone": "Gbagada"},

    # --- Fire ---
    {"name": "LASEMA Fire Unit 1",      "phone": "+2348104899622", "type": "fire", "zone": "Lekki Phase 1"},
    {"name": "LASEMA Fire Unit 2",      "phone": "+2348104899622", "type": "fire", "zone": "Victoria Island"},
    {"name": "Ikeja Fire Station",      "phone": "+2348104899622", "type": "fire", "zone": "Ikeja"},
    {"name": "Apapa Fire Brigade",      "phone": "+2348104899622", "type": "fire", "zone": "Apapa"},
    {"name": "Lagos Island Fire",       "phone": "+2348104899622", "type": "fire", "zone": "Lagos Island"},
    {"name": "Surulere Fire Unit",      "phone": "+2348104899622", "type": "fire", "zone": "Surulere"},
    {"name": "Yaba Fire Station",       "phone": "+2348104899622", "type": "fire", "zone": "Yaba"},
    {"name": "Ajah Fire Response",      "phone": "+2348104899622", "type": "fire", "zone": "Ajah"},

    # --- First Aid ---
    {"name": "St John Ambulance VI",    "phone": "+2348104899622", "type": "first_aid", "zone": "Victoria Island"},
    {"name": "St John Ambulance Ikeja", "phone": "+2348104899622", "type": "first_aid", "zone": "Ikeja"},
    {"name": "Red Cross Lekki",         "phone": "+2348104899622", "type": "first_aid", "zone": "Lekki Phase 1"},
    {"name": "Red Cross Surulere",      "phone": "+2348104899622", "type": "first_aid", "zone": "Surulere"},
]


def seed():
    db = Session()
    try:
        existing = db.query(Responder).count()
        if existing > 0:
            print(f"DB already has {existing} responders — skipping seed.")
            return

        for r in RESPONDERS:
            db.add(Responder(
                id=uuid.uuid4(),
                name=r["name"],
                phone=r["phone"],
                type=r["type"],
                zone=r["zone"],
                is_available=True,
                created_at=datetime.utcnow(),
            ))

        db.commit()
        print(f"Seeded {len(RESPONDERS)} responders across Lagos zones.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
