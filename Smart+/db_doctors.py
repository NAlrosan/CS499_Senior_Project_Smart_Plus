# db_doctors.py
import os
from uuid import uuid4

from dotenv import load_dotenv, find_dotenv
from pymongo import MongoClient

load_dotenv(find_dotenv(usecwd=True))

_client = None

def get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI")
        print("[debug][app] raw MONGO_URI:", repr(uri))
        if not uri:
            raise RuntimeError("MONGO_URI is not set in .env")
        _client = MongoClient(uri)
    return _client

def get_doctors_coll():
    db_name = os.getenv("DOCTOR_DB_NAME", "pulse")
    coll_name = os.getenv("DOCTORS_COLL", "doctordata")
    return get_client()[db_name][coll_name]

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def find_doctor_by_email(email: str):
    coll = get_doctors_coll()
    return coll.find_one({"email": normalize_email(email)})

def find_doctor_by_id(doctor_id: str):
    coll = get_doctors_coll()
    return coll.find_one({"doctor_id": doctor_id})

def verify_doctor(email: str, password: str):
    """
    SUPER SIMPLE auth for demo:
    - compares plaintext password
    - in real life: hash the password!
    """
    doc = find_doctor_by_email(email)
    if not doc:
        return None
    if doc.get("password") != password:
        return None
    return doc

def create_doctor(
    name: str,
    email: str,
    password: str,
    specialty: str = "",
    female: bool = False,
    languages: str = "en",
    max_active_load: int = 10,
):
    coll = get_doctors_coll()
    email_norm = normalize_email(email)

    # Make sure email is unique
    if coll.find_one({"email": email_norm}):
        raise RuntimeError("A doctor with this email already exists.")

    doctor_id = f"doc_{uuid4().hex[:8]}"

    doc = {
        "doctor_id": doctor_id,
        "name": name.strip(),
        "email": email_norm,
        "password": password,  # PLAIN TEXT (OK for uni demo)
        "specialty": specialty or "",
        "female": bool(female),
        "languages": [s.strip() for s in languages.split(",") if s.strip()],
        "phone": "",
        "timezone": "Europe/Berlin",
        "max_active_load": int(max_active_load),
        "active_load": 0,
        "status": "active",
    }
    coll.insert_one(doc)
    return doc

def doctor_to_display(doc: dict):
    """Return only safe fields for storing in session / UI."""
    if not doc:
        return None
    return {
        "doctor_id": doc.get("doctor_id"),
        "name": doc.get("name"),
        "email": doc.get("email"),
        "specialty": doc.get("specialty", ""),
        "status": doc.get("status", "active"),
        "max_active_load": doc.get("max_active_load", 0),
        "active_load": doc.get("active_load", 0),
    }
