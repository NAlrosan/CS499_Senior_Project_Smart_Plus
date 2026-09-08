# db_students.py
import os
from uuid import uuid4

from dotenv import load_dotenv, find_dotenv
from pymongo import MongoClient
import pandas as pd

load_dotenv(find_dotenv(usecwd=True))

_client = None

def get_client() -> MongoClient:
    """Shared Mongo client using MONGO_URI."""
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGO_URI is not set in environment")
        _client = MongoClient(uri)
    return _client

def get_coll():
    """Return the students collection handle."""
    client = get_client()
    db_name = os.getenv("STUDENTS_DB_NAME", "studentdb")
    coll_name = os.getenv("STUDENTS_COLL_NAME", "students")
    return client[db_name][coll_name]

def create_student(name: str, email: str, female: bool, dob: str, device_id: str):
    """
    Insert a new student document.
    We generate a student_id and store device so we can map health_data → student.
    """
    coll = get_coll()
    student_id = str(uuid4())  # you can switch to your own scheme if you want
    doc = {
        "student_id": student_id,
        "name": name.strip(),
        "email": email.strip(),
        "female": bool(female),
        "dob": dob,          # ISO date string from UI
        "device": device_id.strip(),
        "status": "active",
    }
    coll.insert_one(doc)
    return doc

def get_students_df() -> pd.DataFrame:
    """Return all students as a pandas DataFrame."""
    coll = get_coll()
    docs = list(coll.find({}))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    # normalize ids/device to strings
    for col in ["_id", "student_id", "device"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    if "student_id" not in df.columns and "_id" in df.columns:
        df["student_id"] = df["_id"]
    return df
