import os
from uuid import uuid4
from pymongo import MongoClient
from dotenv import load_dotenv
import random

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("STUDENTS_DB_NAME", "studentdb")
COLL_NAME = os.getenv("STUDENTS_COLL_NAME", "students")

client = MongoClient(MONGO_URI)
collection = client[DB_NAME][COLL_NAME]

devices = [
    "com.apple.health.DEVICE9",
    "com.apple.health.DEVICE10",
    "com.apple.health.DEVICE11",
    "com.apple.health.DEVICE12"
]

names = [
    "Nada Alsaif",
    "Talal Alshahrani",
    "Rania Alharthi",
    "Hussain Almadani"
]

docs = []
for i, name in enumerate(names):
    email = f"{name.lower().replace(' ', '')}@psu.edu.sa"
    female = name.split()[0].lower() in ["nada", "rania"]
    doc = {
        "student_id": str(uuid4()),
        "name": name,
        "email": email,
        "female": female,
        "dob": "2005-01-01",
        "device": devices[i],
        "status": "active"
    }
    docs.append(doc)

# Insert without deleting previous ones
result = collection.insert_many(docs)
print(f"Inserted {len(result.inserted_ids)} students.")
