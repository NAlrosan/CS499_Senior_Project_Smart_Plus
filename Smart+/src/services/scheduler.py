import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from ..config import CFG
from ..io.mongo import (
    fetch_raw_since, upsert_clean, upsert_alerts, upsert_assignments,
    fetch_students_and_doctors, persist_csv_compat
)
from ..pipeline.validate import clip_ranges, ensure_types, drop_dupes
from ..pipeline.rules import detect_alerts
from ..pipeline.assign import build_assignments
from .state import load_state, save_state

def run_once():
    state = load_state()
    last_ts = state.get("last_ts")
    raw = fetch_raw_since(last_ts)

    students, doctors = fetch_students_and_doctors()

    if raw.empty:
        # still persist CSV copies for dashboard (so it can load students/doctors)
        persist_csv_compat(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), students, doctors)
        return

    # Clean & validate
    m = raw.copy()
    m = ensure_types(m)
    m = clip_ranges(m)
    m = drop_dupes(m)

    # Persist clean to Mongo
    upsert_clean(m)

    # Alerts
    m["timestamp"] = pd.to_datetime(m["timestamp"], errors="coerce")
    alerts = detect_alerts(m, students)

    # Assignments
    assignments = build_assignments(alerts, doctors, students)

    # Persist alerts/assignments
    upsert_alerts(alerts)
    upsert_assignments(assignments)

    # CSVs for Streamlit (compatibility)
    persist_csv_compat(m, alerts, assignments, students, doctors)

    # Update state
    new_last = str(m["timestamp"].max().tz_localize(None).isoformat()) if not m.empty else last_ts
    save_state({"last_ts": new_last})

def start_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(run_once, "interval", seconds=CFG.poll_interval_seconds, id="poll-job", max_instances=1, coalesce=True)
    sched.start()
    return sched