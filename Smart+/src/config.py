import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name: str = os.getenv("DB_NAME", "pulse")
    raw_coll: str = os.getenv("RAW_COLL", "health_raw")
    clean_coll: str = os.getenv("CLEAN_COLL", "health_clean")
    alerts_coll: str = os.getenv("ALERTS_COLL", "alerts")
    assign_coll: str = os.getenv("ASSIGN_COLL", "assignments")
    students_coll: str = os.getenv("STUDENTS_COLL", "students")
    doctors_coll: str = os.getenv("DOCTORS_COLL", "doctors")

    poll_interval_seconds: int = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))

    csv_dir: str = os.getenv("CSV_DIR", ".")
    dashboard_writes_csv: bool = os.getenv("DASHBOARD_WRITES_CSV", "true").lower() == "true"
    fallback_to_csv_if_mongo_missing: bool = os.getenv("FALLBACK_TO_CSV_IF_MONGO_MISSING", "true").lower() == "true"

CFG = Config()