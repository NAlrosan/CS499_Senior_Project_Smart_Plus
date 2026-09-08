
# worker_mongo.py
# Polls MongoDB every N seconds, runs validation -> rules -> assignments,
# and writes metrics.csv, alerts.csv, assignments.csv for your Streamlit app.

import time
import json
import os

import pandas as pd
import numpy as np
from dotenv import load_dotenv, find_dotenv
from pymongo import MongoClient, errors

from src.paths import data_path
from src.pipeline.validate import clip_ranges, ensure_types, drop_dupes
from src.pipeline.rules import detect_alerts
from src.pipeline.assign import build_assignments
import db_students  # <-- new

load_dotenv(find_dotenv(usecwd=True))

# ---------- CONFIG ----------

MONGO_URI = os.getenv("MONGO_URI")
HEALTH_DB_NAME = os.getenv("HEALTH_DB_NAME", "healthdb")
HEALTH_COLL_NAME = os.getenv("HEALTH_COLL_NAME", "health_data")
DOCTOR_DB_NAME = os.getenv("DOCTOR_DB_NAME", "pulse")
DOCTORS_COLL = os.getenv("DOCTORS_COLL", "doctordata")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))
STATE_PATH = ".state.json"

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set in .env")

print(f"[config] HEALTH={HEALTH_DB_NAME}.{HEALTH_COLL_NAME}")
print(f"[config] DOCTORS={DOCTOR_DB_NAME}.{DOCTORS_COLL}")

# ---------- CSV paths ----------

METRICS_PATH = data_path("metrics.csv")
ALERTS_PATH = data_path("alerts.csv")
ASSIGN_PATH = data_path("assignments.csv")

# ---------- helpers ----------

def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            return {"last_ts": None}
        last_ts = state.get("last_ts")
        if not last_ts or str(last_ts).upper() == "NAT":
            state["last_ts"] = None
        return state
    return {"last_ts": None}

def save_state(state: dict):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)

def get_client() -> MongoClient:
    print("[debug][worker] MONGO_URI:", repr(MONGO_URI))
    client = MongoClient(MONGO_URI)
    client.admin.command("ping")
    return client

def fetch_health_since(last_ts: str | None) -> pd.DataFrame:
    client = get_client()
    coll = client[HEALTH_DB_NAME][HEALTH_COLL_NAME]

    query = {}
    if last_ts:
        dt = pd.to_datetime(last_ts, errors="coerce", utc=True)
        if not pd.isna(dt):
            query["timestamp"] = {"$gt": dt.to_pydatetime()}

    print(f"[mongo] Querying {HEALTH_DB_NAME}.{HEALTH_COLL_NAME} with {query or '{}'}")
    docs = list(coll.find(query))
    if not docs:
        return pd.DataFrame()

    df = pd.DataFrame(docs)
    if "_id" in df.columns:
        df["_id"] = df["_id"].astype(str)
    return df

def relaxed_ensure_types(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if col in {"_id", "timestamp", "ecgClassification", "appleWalkingSteadinessEvent", "device"}:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "timestamp" in df.columns:
        df = df.dropna(subset=["timestamp"])
    return df.copy()

def load_students() -> pd.DataFrame:
    df = db_students.get_students_df()
    print(f"[debug] Loaded {len(df)} students from db_students.get_students_df()")
    if not df.empty:
        print("[debug] Sample student rows:")
        print(df[["student_id", "device"]].head())
    else:
        print("[students] no students in Mongo yet")
    return df

def load_doctors() -> pd.DataFrame:
    client = get_client()
    coll = client[DOCTOR_DB_NAME][DOCTORS_COLL]
    docs = list(coll.find({"status": "active"}))
    if not docs:
        print("[doctors] no active doctors in Mongo")
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    if "specialty" in df.columns:
        df["specialty"] = df["specialty"].apply(
            lambda x: x if isinstance(x, list) else [x]
        )
    if "female" in df.columns:
        df["female"] = df["female"].astype(bool)
    if "active_load" not in df.columns:
        df["active_load"] = 0
    if "max_active_load" not in df.columns:
        df["max_active_load"] = 20
    return df

def attach_student_ids_by_device(raw: pd.DataFrame, students: pd.DataFrame) -> pd.DataFrame:
    print("[debug] Starting attach_student_ids_by_device")
    if raw.empty:
        print("[debug] raw health data is empty")
        return raw
    if "device" not in raw.columns:
        print("[map] health_data has no 'device' field; cannot map to students")
        return raw
    if students.empty:
        print("[map] no students available; cannot map")
        return raw

    print("[debug] student DataFrame columns:", students.columns.tolist())
    print("[debug] raw['device'] sample:", raw["device"].dropna().unique()[:5])
    print("[debug] students['device'] sample:", students["device"].dropna().unique()[:5])

    sid_col = "student_id" if "student_id" in students.columns else "_id"
    if "device" not in students.columns:
        print("[map] students collection missing 'device' field; cannot map")
        return raw

    s = students.dropna(subset=["device"]).copy()
    s["device"] = s["device"].astype(str)
    s[sid_col] = s[sid_col].astype(str)

    print("[debug] cleaned student devices:", s["device"].unique())

    mapping = s.drop_duplicates(subset=["device"]).set_index("device")[sid_col].to_dict()

    print("[debug] device -> student_id mapping:")
    for k, v in mapping.items():
        print(f"    {k} → {v}")

    raw["device"] = raw["device"].astype(str)
    raw["student_id"] = raw["device"].map(mapping)

    matched = raw["student_id"].notna().sum()
    print(f"[map] mapped {matched}/{len(raw)} rows to students via device")

    mask = raw["student_id"].notna()
    raw.loc[mask, "_id"] = raw.loc[mask, "student_id"].astype(str)

    unmapped = raw[raw["student_id"].isna()]
    if not unmapped.empty:
        print("[map] ⚠️ Unmapped devices:")
        print(unmapped["device"].value_counts())

    return raw

# ---------- main pipeline ----------

def run_once():
    state = load_state()
    last_ts = state.get("last_ts")

    students = load_students()
    doctors = load_doctors()

    try:
        raw = fetch_health_since(last_ts)
    except Exception as e:
        print(f"[mongo] fetch error: {e}")
        return

    if raw.empty:
        print("[mongo] no new data since last_ts")
        return

    print(f"[mongo] fetched {len(raw)} raw docs from Mongo")
    print("[debug] Sample raw devices:", raw["device"].dropna().unique()[:5])

    if "timestamp" not in raw.columns:
        print("[mongo] 'timestamp' field missing in documents")
        return

    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce", utc=True)
    raw = raw.dropna(subset=["timestamp"])

    if last_ts:
        last = pd.to_datetime(last_ts, errors="coerce", utc=True)
        if not pd.isna(last):
            before = len(raw)
            raw = raw[raw["timestamp"] > last]
            print(f"[mongo] filtered by last_ts → {before} → {len(raw)} rows")

    if raw.empty:
        print("[mongo] no new rows after filtering by last_ts")
        return

    raw = attach_student_ids_by_device(raw, students)
    m = raw.copy()
    m = relaxed_ensure_types(m)
    m = clip_ranges(m)
    m = drop_dupes(m)
    print(f"[pipeline] after cleaning → {len(m)} rows")

    if m.empty:
        print("[pipeline] nothing left after cleaning; skipping.")
        return

    alerts = detect_alerts(m.copy(), students)
    print(f"[pipeline] detect_alerts → {len(alerts)} alerts")

    assignments = build_assignments(alerts.copy(), doctors.copy(), students.copy())
    print(f"[pipeline] build_assignments → {len(assignments)} assignments")

    os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
    m_out = m.copy()
    m_out["timestamp"] = m_out["timestamp"].dt.tz_convert(None)
    m_out.to_csv(METRICS_PATH, index=False)
    alerts.to_csv(ALERTS_PATH, index=False)
    assignments.to_csv(ASSIGN_PATH, index=False)

    new_last_ts = m["timestamp"].max()
    if pd.isna(new_last_ts):
        print("[state] no valid timestamps to advance last_ts")
        return

    new_last = new_last_ts.tz_convert(None).isoformat()
    save_state({"last_ts": new_last})
    print(f"[ok][mongo] wrote {len(m_out)} metrics, {len(alerts)} alerts, {len(assignments)} assignments; last_ts={new_last}")

if __name__ == "__main__":
    run_once()
    try:
        while True:
            time.sleep(POLL_INTERVAL_SECONDS)
            run_once()
    except KeyboardInterrupt:
        print("[mongo] worker stopped by user")
