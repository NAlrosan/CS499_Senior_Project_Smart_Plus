# worker_http.py
# Polls the HTTP API every 2 minutes, runs validation -> rules -> assignments,
# and writes metrics.csv, alerts.csv, assignments.csv for your Streamlit app.

import time
import json
import os
import requests
import pandas as pd

POLL_INTERVAL_SECONDS = 120
SOURCE_URL = "https://pulseapi-7byk.onrender.com/healthdata"
STATE_PATH = ".state.json"

# ---------- helpers ----------
def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    return {"last_ts": None}

def save_state(state: dict):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)

def fetch_http_all() -> pd.DataFrame:
    r = requests.get(SOURCE_URL, timeout=15)
    r.raise_for_status()
    data = r.json()
    return pd.DataFrame(data)

# ---------- your pipeline pieces (import from src) ----------
from src.pipeline.validate import clip_ranges, ensure_types, drop_dupes
from src.pipeline.rules import detect_alerts
from src.pipeline.assign import build_assignments
from src.paths import data_path

# If you maintain students/doctors in CSVs for the dashboard, load them here.
# (You can later switch these to come from a DB/API—no UI changes required.)
def load_students_doctors():
    students = pd.read_csv(str(data_path("students.csv"))) if os.path.exists(str(data_path("students.csv"))) else pd.DataFrame()
    doctors  = pd.read_csv(str(data_path("doctors.csv")))  if os.path.exists(str(data_path("doctors.csv")))  else pd.DataFrame()
    # Ensure expected columns exist
    if not students.empty and "_id" in students.columns:
        students["_id"] = students["_id"].astype(str)
    return students, doctors

def run_once():
    state = load_state()
    last_ts = state.get("last_ts")  # ISO string or None

    # 1) fetch full payload from HTTP (API doesn’t support incremental)
    try:
        raw = fetch_http_all()
    except Exception as e:
        print(f"[http] fetch error: {e}")
        return

    if raw.empty:
        print("[http] no data returned")
        return

    # 2) normalize and filter "since last timestamp"
    if "timestamp" not in raw.columns:
        print("[http] 'timestamp' column missing in payload")
        return

    raw["_id"] = raw["_id"].astype(str)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce", utc=True)

    if last_ts:
        last = pd.to_datetime(last_ts)
        raw = raw[raw["timestamp"] > last]

    if raw.empty:
        print("[http] no new rows since last_ts")
        return

    # 3) clean
    m = raw.copy()
    # Keep only columns your app expects (if your payload sometimes includes extras)
    # If you want to be strict, declare the list and select it here.
    m = ensure_types(m)
    m = clip_ranges(m)
    m = drop_dupes(m)

    # 4) detect alerts
    students, doctors = load_students_doctors()
    alerts = detect_alerts(m.copy(), students)

    # 5) assign
    assignments = build_assignments(alerts.copy(), doctors.copy(), students.copy())

    # 6) write CSVs for Streamlit app
    m_out = m.copy()
    m_out["timestamp"] = m_out["timestamp"].dt.tz_convert(None)  # make naive for CSV
    m_out.to_csv("metrics.csv", index=False)
    alerts.to_csv("alerts.csv", index=False)
    assignments.to_csv("assignments.csv", index=False)

    # 7) advance state
    new_last = m["timestamp"].max().tz_convert(None).isoformat()
    save_state({"last_ts": new_last})
    print(f"[ok] wrote {len(m_out)} metrics, {len(alerts)} alerts, {len(assignments)} assignments; last_ts={new_last}")

if __name__ == "__main__":
    # Run immediately, then loop
    run_once()
    try:
        while True:
            time.sleep(POLL_INTERVAL_SECONDS)
            run_once()
    except KeyboardInterrupt:
        pass