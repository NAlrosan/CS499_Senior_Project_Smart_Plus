from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING
from .csv_compat import df_to_csv_if_enabled
from ..config import CFG
import pandas as pd

_client: Optional[MongoClient] = None

def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(CFG.mongo_uri, serverSelectionTimeoutMS=5000)
    return _client

def fetch_students_and_doctors() -> (pd.DataFrame, pd.DataFrame):
    cli = get_client()
    db = cli[CFG.db_name]
    try:
        students = pd.DataFrame(list(db[CFG.students_coll].find({})))
        doctors  = pd.DataFrame(list(db[CFG.doctors_coll].find({})))
        # normalize _id
        if "_id" in students.columns:
            students["_id"] = students["_id"].astype(str)
        if "_id" in doctors.columns:
            doctors["_id"] = doctors["_id"].astype(str)
        return students, doctors
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

def fetch_raw_since(last_ts_iso: Optional[str]) -> pd.DataFrame:
    cli = get_client()
    db = cli[CFG.db_name]
    q = {}
    if last_ts_iso:
        q = {"timestamp": {"$gt": last_ts_iso}}
    cursor = db[CFG.raw_coll].find(q).sort("timestamp", ASCENDING)
    df = pd.DataFrame(list(cursor))
    if not df.empty:
        if "_id" in df.columns:
            df["_id"] = df["_id"].astype(str)
    return df

def upsert_clean(df: pd.DataFrame) -> None:
    if df.empty: return
    cli = get_client()
    db = cli[CFG.db_name]
    coll = db[CFG.clean_coll]
    records: List[Dict[str, Any]] = df.to_dict(orient="records")
    for r in records:
        key = {"_id": r["_id"], "timestamp": r["timestamp"]}
        coll.update_one(key, {"$set": r}, upsert=True)

def upsert_alerts(df: pd.DataFrame) -> None:
    if df.empty: return
    cli = get_client()
    db = cli[CFG.db_name]
    coll = db[CFG.alerts_coll]
    for r in df.to_dict(orient="records"):
        coll.update_one({"alert_id": r["alert_id"]}, {"$set": r}, upsert=True)

def upsert_assignments(df: pd.DataFrame) -> None:
    if df.empty: return
    cli = get_client()
    db = cli[CFG.db_name]
    coll = db[CFG.assign_coll]
    for r in df.to_dict(orient="records"):
        coll.update_one({"assignment_id": r["assignment_id"]}, {"$set": r}, upsert=True)

def persist_csv_compat(metrics: pd.DataFrame, alerts: pd.DataFrame, assignments: pd.DataFrame,
                       students: pd.DataFrame, doctors: pd.DataFrame):
    df_to_csv_if_enabled(metrics, "metrics.csv")
    df_to_csv_if_enabled(alerts, "alerts.csv")
    df_to_csv_if_enabled(assignments, "assignments.csv")
    df_to_csv_if_enabled(students, "students.csv")
    df_to_csv_if_enabled(doctors, "doctors.csv")
