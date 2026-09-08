import streamlit as st
from pymongo import MongoClient
from pathlib import Path

# FIRST Streamlit call
st.set_page_config(page_title="Personal Dashboard", layout="wide")


# Simple CSS for card-style containers
st.markdown(
    """
    <style>
        /* Reduce the default padding inside the sidebar */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0.25rem;
        padding-left: 0.25rem;
        padding-right: 0.25rem;
    }

    /* Logo wrapper: no margins at all */
    .sidebar-logo-wrapper {
        margin: 0;
        padding: 0;
        display: flex;
        align-items: flex-start;
    }

    .sidebar-logo-wrapper img {
        width: 130px;          /* make it bigger/smaller as you like */
        display: block;
        margin: 0;             /* no extra margin around the img */
    }
        /* Sidebar background + border */
    [data-testid="stSidebar"] {
        background-color: #1D1D26;  /* deep slate */
        border-right: 1px solid #111827;
    }

    /* Container spacing inside sidebar */
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.5rem;
    }

    /* “Doctor Portal” title */
    .sidebar-header-logo {
        width: 28px;
        height: 28px;
        border-radius: 8px;          
        object-fit: contain;         
    }

    /* Card behind logged-in text */
    .sidebar-card {
        background: none;
        border-radius: 0.75rem;
        margin-bottom: 1.25rem;
    }

    .sidebar-badge {
        background: rgba(34, 197, 94, 0.15); /* soft green */
        color: #bbf7d0;
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        font-size: 0.85rem;
        display: inline-flex;
        align-items: center;
        gap: 1rem;
    }

    .sidebar-badge-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: #22c55e;
    }

    /* “Navigate” label */
    .sidebar-section-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #9ca3af;
        margin-bottom: 0.35rem;
    }

    /* Radio buttons as pill-like nav items */
    div[data-baseweb="radio"] > div {
        row-gap: 1rem;
    }

    div[data-baseweb="radio"] label {
        background: #020617;
        border-radius: 0.5rem;
        padding: 0.35rem 0.75rem;
        border: 1px solid #111827;
        width: 100%;
    }

    div[data-baseweb="radio"] label:hover {
        border-color: #1f2937;
        background: #0b1120;
    }

    /* Selected state */
    div[data-baseweb="radio"] input:checked + div {
        color: #f97316;  /* orange accent */
        font-weight: 600;
    }

    /* Logout button: full width + subtle border */
    .sidebar-logout > button {
        width: 100%;
        border-radius: 0.6rem;
        border: 1px solid #374151 !important;
    }
    .card {
        background-color: #111827;      /* slightly lighter than main bg */
        border-radius: 12px;
        padding: 1rem 1.25rem;
        border: 1px solid #1f2937;
        margin-bottom: 1rem;
    }
    div.stButton > button {
        white-space: nowrap;
    }
    .card h4 {
        margin: 0 0 .5rem 0;
        font-size: 1rem;
        font-weight: 600;
    }
    .block-container {
        padding-top: 1rem;
    }

    /* Tighten the title margin so it hugs the top a bit more */
    h1 {
        margin-top: 0.5rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

# Optional auto-refresh (won't break if package isn't installed)
try:
    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(interval=120_000, key="data-refresh")
except Exception:
    pass

import os, json, csv, shutil, random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from uuid import uuid4
import altair as alt
import sys, pathlib
import db_students

sys.path.append(str(pathlib.Path(__file__).parent / "src"))
from services.ai_messaging import build_ai_payload, generate_student_message

# NEW: mongo doctor helpers
from db_doctors import verify_doctor, create_doctor, doctor_to_display

# =========================
# CONFIG / PATHS
# =========================
AUTO_RESET_ON_START = False  # always reset when you (re)run the app
DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Known CSV filenames
CSV_NAMES = [
    "students.csv",
    "doctors.csv",
    "metrics.csv",
    "alerts.csv",
    "assignments.csv",
    "audit_log.csv",
    "email_outbox.csv",
]

# Auto-migrate any CSVs found in project root into data/
for name in CSV_NAMES + [".state.json"]:
    src = pathlib.Path(name)
    dst = pathlib.Path(DATA_DIR) / name
    try:
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
    except Exception:
        pass


# Resolve paths inside data/
def P(name: str) -> str:
    return f"{DATA_DIR}/{name}"


PATH_STUDENTS = P("students.csv")
PATH_DOCTORS = P("doctors.csv")
PATH_METRICS = P("metrics.csv")
PATH_ALERTS = P("alerts.csv")
PATH_ASSIGN = P("assignments.csv")
PATH_EMAILS = P("email_outbox.csv")
PATH_AUDIT = P("audit_log.csv")
PATH_STATE = P(".state.json")

# =========================
# HELPERS
# =========================

MONGO_URI = os.getenv("MONGO_URI")
DOCTOR_DB_NAME = os.getenv("DOCTOR_DB_NAME", "pulse")
DOCTORS_COLL = os.getenv("DOCTORS_COLL", "doctordata")


@st.cache_data(ttl=10)
def load_doctors_from_mongo() -> pd.DataFrame:
    """Load active doctors from MongoDB for the dashboard UI."""
    if not MONGO_URI:
        return pd.DataFrame()
    client = MongoClient(MONGO_URI)
    coll = client[DOCTOR_DB_NAME][DOCTORS_COLL]
    docs = list(coll.find({"status": "active"}))
    if not docs:
        return pd.DataFrame()
    df = pd.DataFrame(docs)
    # normalize fields
    for col in ["_id", "doctor_id", "name", "email"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    if "female" in df.columns:
        df["female"] = df["female"].astype(bool)
    if "active_load" not in df.columns:
        df["active_load"] = 0
    if "max_active_load" not in df.columns:
        df["max_active_load"] = 20
    return df


@st.cache_data(ttl=10)
def load_csv(path, **kwargs) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def save_csv(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)


def rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def ensure_columns(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c, default in cols.items():
        if c not in df.columns:
            df[c] = default
    return df


def compute_age(dob_str):
    try:
        dob = pd.to_datetime(dob_str).date()
        today = datetime.utcnow().date()
        return int((today - dob).days // 365.25)
    except Exception:
        return None


def robust_stats(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return np.nan, np.nan
    med = float(np.median(s))
    mad = float(np.median(np.abs(s - med)))
    if mad == 0.0:
        mad = max(1.0, med * 0.05) if med > 0 else 1.0
    return med, mad


def in_notify_window(now_local: datetime, start_str: str, end_str: str) -> bool:
    try:
        s_h, s_m = map(int, (start_str or "08:00").split(":"))
        e_h, e_m = map(int, (end_str or "20:00").split(":"))
        start = time(s_h, s_m)
        end = time(e_h, e_m)
        if start <= end:
            return start <= now_local.time() <= end
        return now_local.time() >= start or now_local.time() <= end
    except Exception:
        return True


def schedule_next_window(now_local: datetime, start_str: str) -> datetime:
    try:
        s_h, s_m = map(int, (start_str or "08:00").split(":"))
        next_dt = datetime.combine(now_local.date(), time(s_h, s_m))
        if now_local.time() > time(s_h, s_m):
            next_dt = next_dt + timedelta(days=1)
        return next_dt
    except Exception:
        return now_local


FIELDS_EMAIL_OUTBOX = [
    "id",
    "status",
    "queued_at",
    "to",
    "subject",
    "body",
    "send_at",
    "student_id",
    "doctor_name",
    "severity",
    "reason",
]


def log_email(
    to, subject, body, send_at, student_id, doctor_name, severity, reason, status="QUEUED"
):
    row = {
        "id": str(uuid4()),
        "status": status,  # "SENT" | "FAILED" | "QUEUED"
        "queued_at": datetime.utcnow().isoformat(),
        "to": to,
        "subject": subject,
        "body": body,
        "send_at": send_at if isinstance(send_at, str) else send_at.isoformat(),
        "student_id": student_id,
        "doctor_name": doctor_name,
        "severity": severity,
        "reason": reason,
    }
    exists = os.path.exists(PATH_EMAILS)
    os.makedirs(os.path.dirname(PATH_EMAILS), exist_ok=True)
    with open(PATH_EMAILS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=FIELDS_EMAIL_OUTBOX, quoting=csv.QUOTE_ALL
        )
        if not exists:
            w.writeheader()
        w.writerow(row)


def log_audit(action, payload):
    audit = load_csv(PATH_AUDIT)
    audit = ensure_columns(audit, {"timestamp": "", "action": "", "payload": ""})
    new_row = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "payload": json.dumps(payload, ensure_ascii=False),
    }
    audit = pd.concat([audit, pd.DataFrame([new_row])], ignore_index=True)
    save_csv(audit, PATH_AUDIT)


# =========================
# AUTO-RESET ON START
# =========================
def _wipe_state_files():
    for name in [
        "alerts.csv",
        "assignments.csv",
        "audit_log.csv",
        "email_outbox.csv",
        ".state.json",
    ]:
        p = P(name)
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


def _seed_one_demo_case(students_df: pd.DataFrame, doctors_df: pd.DataFrame):
    """Create one alert + assignment so Queue is not empty."""
    if students_df.empty or doctors_df.empty:
        return

    # pick a student (prefer real email if present)
    stu = None
    for _, r in students_df.iterrows():
        em = str(r.get("email", ""))
        if em and "@" in em and not em.endswith("example.edu"):
            stu = r
            break
    if stu is None:
        stu = students_df.iloc[0]

    # pick a doctor name from CSV (still used by worker / demo)
    dname = str(doctors_df.get("name", pd.Series(["On-duty Doctor"])).iloc[0])

    now = datetime.utcnow()
    # create alert
    alert_id = str(uuid4())
    metric = random.choice(["heartRate", "oxygenSaturation", "respiratoryRate"])
    reason = {
        "heartRate": "Elevated heart rate vs baseline",
        "oxygenSaturation": "Lower oxygen saturation detected",
        "respiratoryRate": "Elevated respiratory rate vs baseline",
    }[metric]
    severity = random.choice(["moderate", "critical"])
    features = json.dumps(
        {
            "value": (
                random.randint(110, 124)
                if metric == "heartRate"
                else (
                    random.randint(90, 93)
                    if metric == "oxygenSaturation"
                    else random.randint(22, 26)
                )
            )
        },
        ensure_ascii=False,
    )

    alerts_df = pd.DataFrame(
        [
            {
                "alert_id": alert_id,
                "student_id": stu.get("_id")
                or stu.get("student_id")
                or "S001",
                "metric": metric,
                "severity": severity,
                "reason": reason,
                "features": features,
                "routed_specialty": "Internal Medicine",
                "created_at": now.isoformat(),
                "window_start": (now - timedelta(minutes=10)).isoformat(),
                "window_end": now.isoformat(),
            }
        ]
    )
    save_csv(alerts_df, PATH_ALERTS)

    # create matching assignment
    assign_id = str(uuid4())
    assign_df = pd.DataFrame(
        [
            {
                "assignment_id": assign_id,
                "alert_id": alert_id,
                "student_id": alerts_df.iloc[0]["student_id"],
                "doctor_name": dname,
                "status": "PENDING",
                "rationale": "",
                "rejection_reason": "",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        ]
    )
    save_csv(assign_df, PATH_ASSIGN)

    # empty audit/outbox files (headers only)
    save_csv(pd.DataFrame(columns=["timestamp", "action", "payload"]), PATH_AUDIT)
    save_csv(pd.DataFrame(columns=FIELDS_EMAIL_OUTBOX), PATH_EMAILS)


# Run reset once per process start
if AUTO_RESET_ON_START and not st.session_state.get("_did_auto_reset"):
    _wipe_state_files()
    # Load minimal data to seed (students/doctors only)
    _students_tmp = load_csv(PATH_STUDENTS)
    _doctors_tmp = load_csv(PATH_DOCTORS)
    # normalize booleans if present
    if "female" in _students_tmp.columns:
        _students_tmp["female"] = _students_tmp["female"].astype(bool)
    if "female" in _doctors_tmp.columns:
        _doctors_tmp["female"] = _doctors_tmp["female"].astype(bool)
    _seed_one_demo_case(_students_tmp, _doctors_tmp)
    st.session_state["_did_auto_reset"] = True
    st.cache_data.clear()  # make sure subsequent loads see fresh files

# =========================
# LOAD DATA (normal flow)
# =========================
students = db_students.get_students_df()
doctors = load_doctors_from_mongo()
metrics = load_csv(PATH_METRICS, parse_dates=["timestamp"])  # ok if empty
alerts = load_csv(PATH_ALERTS)
assignments_file = load_csv(PATH_ASSIGN)

# Normalize
if "female" in students.columns:
    students["female"] = students["female"].astype(bool)
if "female" in doctors.columns:
    doctors["female"] = doctors["female"].astype(bool)
if "created_at" in alerts.columns:
    alerts["created_at"] = (
        pd.to_datetime(alerts["created_at"], errors="coerce", utc=True)
        .dt.tz_convert(None)
    )

# ---- Make assignments robust: guarantee core columns exist ----
assignments_file = ensure_columns(
    assignments_file,
    {
        "assignment_id": "",
        "alert_id": "",
        "student_id": "",
        "doctor_name": "",
        "status": "",
        "rationale": "",
        "rejection_reason": "",
        "created_at": "",
        "updated_at": "",
    },
)
assignments_file["status"] = (
    assignments_file["status"].replace("", np.nan).fillna("PENDING")
)

# Initialize session state
if "assignments" not in st.session_state:
    st.session_state.assignments = assignments_file.copy()
if "busy_actions" not in st.session_state:
    st.session_state.busy_actions = set()

assignments = st.session_state.assignments

# If assignments has doctor_id but no doctor_name, map it
if (
    "doctor_name" in assignments.columns
    and assignments["doctor_name"].eq("").all()
    and "doctor_id" in assignments.columns
    and "name" in doctors.columns
):
    mapping = (
        doctors.set_index("doctor_id")["name"]
        if "doctor_id" in doctors.columns
        else pd.Series(dtype=str)
    )
    if not mapping.empty:
        assignments["doctor_name"] = assignments["doctor_id"].map(mapping).fillna(
            assignments["doctor_id"]
        )

# =========================
# JOIN HELPERS + OVERVIEW
# =========================
# def join_alerts(df: pd.DataFrame) -> pd.DataFrame:
#     if df.empty:
#         return df
#     df = df.drop(
#         columns=[c for c in ["student_id", "created_at"] if c in df.columns]
#     )
#     cols_keep = [
#         "alert_id",
#         "student_id",
#         "metric",
#         "severity",
#         "reason",
#         "features",
#         "routed_specialty",
#         "created_at",
#         "window_start",
#         "window_end",
#     ]
#     a = alerts.loc[:, [c for c in cols_keep if c in alerts.columns]].copy()
#     return df.merge(a, on="alert_id", how="left")


# def join_students(df: pd.DataFrame) -> pd.DataFrame:
#     if df.empty:
#         return df

#     # If both sides have student_id, just join on that
#     if "student_id" in df.columns and "student_id" in students.columns:
#         return df.merge(
#             students,
#             on="student_id",
#             how="left",
#             suffixes=("", "_student"),
#         )

#     # Original behavior: df has student_id, students have _id
#     if "student_id" in df.columns and "_id" in students.columns:
#         return df.merge(
#             students,
#             left_on="student_id",
#             right_on="_id",
#             how="left",
#             suffixes=("", "_student"),
#         )

#     # If we can't find a key to join on, just return df unchanged
#     return df

def join_alerts(df: pd.DataFrame) -> pd.DataFrame:
    """Join assignments with alerts data."""
    if df.empty or alerts.empty:
        return df
    
    # Don't drop student_id or created_at from df!
    # Only select the columns we want from alerts to avoid duplicates
    alert_cols = [
        "alert_id",
        "student_id",
        "metric",
        "severity",
        "reason",
        "features",
        "routed_specialty",
        "created_at",
        "window_start",
        "window_end",
    ]
    
    # Only keep columns that exist in alerts
    cols_to_use = [c for c in alert_cols if c in alerts.columns]
    
    if "alert_id" not in cols_to_use:
        return df  # Can't join without alert_id
    
    alerts_subset = alerts[cols_to_use].copy()
    
    # Merge on alert_id, using suffixes to handle overlapping columns
    result = df.merge(
        alerts_subset,
        on="alert_id",
        how="left",
        suffixes=("", "_alert")
    )
    
    # If we got duplicate columns, prefer the alert version for key fields
    for col in ["student_id", "created_at", "severity", "reason", "metric"]:
        alert_col = f"{col}_alert"
        if alert_col in result.columns:
            # Fill missing values in original column with alert version
            if col in result.columns:
                result[col] = result[col].fillna(result[alert_col])
            else:
                result[col] = result[alert_col]
            result = result.drop(columns=[alert_col])
    
    return result


def join_students(df: pd.DataFrame) -> pd.DataFrame:
    """Join dataframe with student information."""
    if df.empty or students.empty:
        return df
    
    # Determine which ID column to use
    df_id_col = "student_id" if "student_id" in df.columns else "_id"
    students_id_col = "student_id" if "student_id" in students.columns else "_id"
    
    if df_id_col not in df.columns:
        return df  # Can't join without an ID column
    
    if students_id_col not in students.columns:
        return df  # Students don't have ID column
    
    # If the ID columns have different names, we need to handle that
    if df_id_col == students_id_col:
        # Same column name - simple merge
        result = df.merge(
            students,
            on=df_id_col,
            how="left",
            suffixes=("", "_student")
        )
    else:
        # Different column names - merge with left_on/right_on
        result = df.merge(
            students,
            left_on=df_id_col,
            right_on=students_id_col,
            how="left",
            suffixes=("", "_student")
        )
    
    # Clean up duplicate columns - prefer student data for demographics
    for col in ["name", "email", "dob", "female"]:
        student_col = f"{col}_student"
        if student_col in result.columns:
            if col in result.columns:
                # If original column exists, fill NaN with student version
                result[col] = result[col].fillna(result[student_col])
            else:
                # Otherwise just rename the student column
                result[col] = result[student_col]
            result = result.drop(columns=[student_col])
    
    return result

import json, ast

def get_spo2_value_from_row(row, default=92.0):
    feats = row.get("features", {})

    # If it's already a dict, just grab it
    if isinstance(feats, dict):
        v = feats.get("value", default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    # If it's a string like "{'value': 88.0, ...}"
    if isinstance(feats, str):
        try:
            # first try JSON
            parsed = json.loads(feats)
        except json.JSONDecodeError:
            try:
                # fall back to Python literal (handles single quotes)
                parsed = ast.literal_eval(feats)
            except (ValueError, SyntaxError):
                return default

        if isinstance(parsed, dict):
            try:
                return float(parsed.get("value", default))
            except (TypeError, ValueError):
                return default

    # Any other weird case
    return default

def build_generic_alert_chart(row: pd.Series):
    """
    Return a small generic Altair chart based only on alert type
    (reason / metric), no real student data needed.
    """
    reason = str(row.get("reason", "")).lower()
    metric = str(row.get("metric", "")).lower()

    # ----- pick a "type" -----
    if "irregular_heart_rhythm" in reason:
        chart_type = "ecg"
    elif "tachycardia" in reason or metric == "heartrate":
        chart_type = "tachycardia"
    elif "fall" in reason:
        chart_type = "fall"
    elif "oxygensaturation" in metric or "hypoxemia" in reason:
        chart_type = "oxygen"
    elif "sleep" in reason or "sleepanalysisvalue" in metric:
        chart_type = "sleep"
    else:
        chart_type = "generic"

    # ----- build dummy data -----
    if chart_type == "ecg":
        # ECG-style wave: small baseline + repeated sharp spikes
        n_points = 140
        x = np.linspace(0, 12, n_points)

        # tiny baseline wobble
        y = 0.05 * np.sin(2 * np.pi * x)

        # positions (in "time") of heart beats
        beat_positions = [1, 3, 5, 7, 9, 11]

        for bp in beat_positions:
            # find closest index to the beat position
            idx = int(np.argmin(np.abs(x - bp)))

            # a simple P-QRS-T complex:
            # small bump (P)
            if idx - 5 >= 0:
                y[idx - 5] += 0.15
            # small dip (Q)
            if idx - 2 >= 0:
                y[idx - 2] -= 0.2
            # tall spike (R)
            y[idx] += 2.5
            # small dip (S)
            if idx + 2 < n_points:
                y[idx + 2] -= 0.3
            # small positive T wave a bit later
            t_idx = min(idx + 7, n_points - 1)
            y[t_idx] += 0.5

        df = pd.DataFrame({"t": x, "v": y})
        chart = (
            alt.Chart(df)
            .mark_line(size=2)
            .encode(
                x=alt.X("t:Q", axis=None),
                y=alt.Y("v:Q", axis=None),
            )
            .properties(height=70)
        )

    elif chart_type == "tachycardia":
        # More realistic tachycardia pattern:
        # baseline -> sharp rise -> high plateau with jitter -> recovery
        n = 120
        t = np.arange(n)

        hr = np.empty(n, dtype=float)

        # 0–35: resting baseline
        hr[:35] = 65 + np.random.normal(0, 1, 35)

        # 35–45: sharp rise
        hr[35:45] = np.linspace(70, 135, 10)

        # 45–95: high, slightly jittery plateau
        hr[45:95] = 135 + np.random.normal(0, 2, 50)

        # 95–end: gradual recovery
        hr[95:] = np.linspace(135, 80, n - 95) + np.random.normal(0, 1, n - 95)

        df = pd.DataFrame({"t": t, "v": hr})

        chart = (
            alt.Chart(df)
            .mark_line(size=2)
            .encode(
                x=alt.X("t:Q", axis=None),
                y=alt.Y("v:Q", axis=None),
            )
            .properties(height=70)
        )


    elif chart_type == "fall":
        # Flat line with one big drop
        x = np.arange(20)
        y = np.ones_like(x, dtype=float)
        y[10:] = 0.1
        df = pd.DataFrame({"t": x, "v": y})
        chart = (
            alt.Chart(df)
            .mark_area()
            .encode(
                x=alt.X("t:Q", axis=None),
                y=alt.Y("v:Q", axis=None),
            )
            .properties(height=70)
        )

    elif chart_type == "oxygen":
        val = get_spo2_value_from_row(row, default=92.0)
        val = max(0.0, min(100.0, val))  # clamp to [0, 100]

        df = pd.DataFrame(
            {"segment": ["filled", "remaining"],
            "value": [val, 100.0 - val]}
        )

        base = alt.Chart(df).encode(
            theta=alt.Theta("value:Q", stack=True),
            color=alt.Color(
                "segment:N",
                legend=None,
                scale=alt.Scale(range=["#4fc3f7", "#333333"]),
            ),
        )

        chart = (
            base
            .mark_arc(innerRadius=16, outerRadius=26)
            .properties(width=50, height=50, padding=5)
            .configure_view(strokeWidth=0)
        )


        base = alt.Chart(df).encode(
            theta=alt.Theta("value:Q", stack=True),
            color=alt.Color(
                "segment:N",
                legend=None,
                # tweak colors if you like
                scale=alt.Scale(range=["#4fc3f7", "#333333"]),
            ),
        )

        # donut-style gauge
        chart = (
            base.mark_arc(innerRadius=20, outerRadius=30)
            .properties(width=60, height=60, padding = {"top": 5, "bottom": 5, "left": 0, "right": 0})
            .configure_view(strokeWidth=0)  # Add this line

        )

    elif chart_type == "sleep":
        reason = str(row.get("reason", "")).lower()

        if "fragmentation" in reason:
            stages = ["Awake", "REM", "Awake", "Light", "REM", "Awake", "Deep", "Awake"]
        elif "insomnia" in reason:
            stages = ["Awake", "Awake", "Light", "Awake", "REM", "Awake"]
        elif "short_sleep" in reason:
            stages = ["Awake", "Light", "REM"]
        elif "latency" in reason:
            stages = ["Awake", "Awake", "Awake", "Light", "Deep", "REM"]
        else:
            stages = ["Awake", "REM", "Light", "Deep", "Light", "REM", "Awake"]

        t = list(range(len(stages)))
        df = pd.DataFrame({"t": t, "stage": stages})
        stage_order = ["Awake", "REM", "Light", "Deep"]

        chart = (
            alt.Chart(df)
            .mark_bar(size=10)
            .encode(
                x=alt.X("t:O", axis=None),
                y=alt.Y("stage:N", sort=stage_order, axis=None),
                color=alt.Color("stage:N", scale=alt.Scale(
                    domain=stage_order,
                    range=["#c62828", "#ff7043", "#64b5f6", "#283593"]
                ))
            )
            .properties(height=70)
        )


    else:  # generic smooth wave
        x = np.arange(60)
        y = 1.0 + 0.4 * np.sin(x / 5)
        df = pd.DataFrame({"t": x, "v": y})
        chart = (
            alt.Chart(df)
            .mark_line(size=2)
            .encode(
                x=alt.X("t:Q", axis=None),
                y=alt.Y("v:Q", axis=None),
            )
            .properties(height=70)
        )

    return chart



# def build_metric_sparkline(row: pd.Series, metrics_df: pd.DataFrame):
#     """
#     Tiny line chart for the alert's metric around the alert time.
#     Very forgiving so we almost always show *something*.
#     """
#     if metrics_df is None or metrics_df.empty:
#         return None

#     # Which metric is this alert about?
#     metric_name = str(row.get("metric", "")).strip()
#     student_id = row.get("student_id", None)

#     if not student_id or "timestamp" not in metrics_df.columns:
#         return None

#     # Filter metrics for this student
#     if "student_id" in metrics_df.columns:
#         m = metrics_df[metrics_df["student_id"] == student_id].copy()
#     elif "_id" in metrics_df.columns:
#         m = metrics_df[metrics_df["_id"] == student_id].copy()
#     else:
#         return None

#     if m.empty:
#         return None

#     # Map alert metric → actual column name in metrics.csv
#     # (for event alerts, show heartRate trend by default)
#     col = metric_name
#     metric_fallback_map = {
#         "event": "heartRate",
#         "fall": "numberOfTimesFallen",
#     }
#     col = metric_fallback_map.get(col, col)

#     if col not in m.columns:
#         # Still not found → if heartRate exists, use that as a generic trend
#         if "heartRate" in m.columns:
#             col = "heartRate"
#         else:
#             return None

#     # Clean + sort
#     m["timestamp"] = pd.to_datetime(m["timestamp"], errors="coerce")
#     m = m.dropna(subset=["timestamp"]).sort_values("timestamp")

#     if m.empty:
#         return None

#     # Try to focus on a window around the alert time; if that is empty, fall
#     # back to the last N points for this student instead of returning None.
#     created = row.get("created_at")
#     subset = m
#     try:
#         if created is not None and not pd.isna(created):
#             created_dt = pd.to_datetime(created)
#             window = pd.Timedelta(hours=6)   # a bit wider than before
#             win = m[(m["timestamp"] >= created_dt - window) &
#                     (m["timestamp"] <= created_dt + window)]
#             if not win.empty:
#                 subset = win
#     except Exception:
#         pass

#     # Limit points to keep chart small & fast
#     if len(subset) > 40:
#         subset = subset.tail(40)

#     if subset.empty:
#         return None

#     # Build tiny sparkline (no axes)
#     chart = (
#         alt.Chart(subset)
#         .mark_line()
#         .encode(
#             x=alt.X("timestamp:T", axis=None),
#             y=alt.Y(f"{col}:Q", axis=None)
#         )
#         .properties(height=70)
#     )
#     return chart


def render_doctor_overview(doctor_name: str, assignments_all: pd.DataFrame):
    """Small KPI + compact charts for the logged-in doctor."""
    if not doctor_name or assignments_all.empty or alerts.empty:
        return

    # Pull *all* this doctor's alerts (pending + accepted etc.)
    if "doctor_name" in assignments_all.columns:
        my_all = assignments_all.loc[assignments_all["doctor_name"] == doctor_name].copy()
    else:
        my_all = assignments_all.iloc[0:0].copy()

    if my_all.empty:
        return

    df = join_alerts(my_all.copy())
    if df.empty:
        return

    # Normalize created_at
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True).dt.tz_convert(None)

    # -------- KPI row --------
    total_pending = (df["status"] == "PENDING").sum()
    total_active  = (df["status"] == "ACCEPTED").sum()
    crit_pending  = ((df["status"] == "PENDING") & (df["severity"] == "critical")).sum()

    st.markdown("### Overview")
    k1, k2, k3 = st.columns(3)
    k1.metric("Pending alerts", int(total_pending))
    k2.metric("Active cases", int(total_active))
    k3.metric("Pending critical", int(crit_pending))

    # -------- Compact charts in aligned "cards" --------
    with st.container():
        col_left, col_right = st.columns(2)

        # 1) Alerts by severity & status  (left card)
        with col_left:
            if {"severity", "status"}.issubset(df.columns):
                sev = (
                    df.groupby(["severity", "status"])
                      .size()
                      .reset_index(name="count")
                )
                if not sev.empty:
                    chart_sev = (
                        alt.Chart(sev)
                        .mark_bar()
                        .encode(
                            x=alt.X("severity:N", title="Severity"),
                            y=alt.Y("count:Q", title="Alerts"),
                            color=alt.Color("status:N", title="Status"),
                            tooltip=["status", "severity", "count"],
                        )
                        .properties(height=260)
                    )
                    # CARD
                    with st.container(border=True):
                        st.markdown("#### Alerts by severity & status")
                        st.altair_chart(chart_sev, use_container_width=True)

        # 2) Alerts by metric as PIE chart (right card)
        with col_right:
            if "metric" in df.columns:
                met = (
                    df.groupby("metric")
                      .size()
                      .reset_index(name="count")
                      .sort_values("count", ascending=False)
                )
                if not met.empty:
                    chart_met_pie = (
                        alt.Chart(met)
                        .mark_arc(outerRadius=80)
                        .encode(
                            theta=alt.Theta("count:Q", title="Alerts"),
                            color=alt.Color(
                                "metric:N",
                                title="Metric",
                                legend=alt.Legend(orient="right"),
                            ),
                            tooltip=["metric", "count"],
                        )
                        .properties(height=260)
                    )
                    # CARD
                    with st.container(border=True):
                        st.markdown("#### Alerts by metric")
                        st.altair_chart(chart_met_pie, use_container_width=True)


# =========================
# ASSIGNMENT + EMAIL HELPERS
# =========================
# def accept_assignment(assign_id, doctor_name) -> bool:
#     if assign_id == "":
#         return False

#     df = st.session_state.assignments
#     idx = df.index[df["assignment_id"] == assign_id]
#     if len(idx) == 0:
#         st.error("Assignment not found")
#         return False

#     df.loc[idx, "status"] = "ACCEPTED"
#     df.loc[idx, "updated_at"] = datetime.utcnow().isoformat()

#     # Update doctor's active_load in Mongo (optional but nice)
#     try:
#         if MONGO_URI and doctor_name:
#             client = MongoClient(MONGO_URI)
#             coll = client[DOCTOR_DB_NAME][DOCTORS_COLL]
#             coll.update_one({"name": doctor_name}, {"$inc": {"active_load": 1}})
#     except Exception as e:
#         st.warning(f"Could not update doctor load in Mongo: {e}")

#     # Persist assignments to CSV (Streamlit still reads assignments.csv)
#     save_csv(df, PATH_ASSIGN)
#     st.cache_data.clear()
#     return True
def accept_assignment(assign_id, doctor_name) -> bool:
    if assign_id == "":
        return False

    df = st.session_state.assignments.copy()  # Make a copy
    idx = df.index[df["assignment_id"] == assign_id]
    if len(idx) == 0:
        st.error("Assignment not found")
        return False

    df.loc[idx, "status"] = "ACCEPTED"
    df.loc[idx, "updated_at"] = datetime.utcnow().isoformat()

    # Update doctor's active_load in Mongo
    try:
        if MONGO_URI and doctor_name:
            client = MongoClient(MONGO_URI)
            coll = client[DOCTOR_DB_NAME][DOCTORS_COLL]
            coll.update_one({"name": doctor_name}, {"$inc": {"active_load": 1}})
    except Exception as e:
        st.warning(f"Could not update doctor load in Mongo: {e}")

    # Persist and update session state
    save_csv(df, PATH_ASSIGN)
    st.session_state.assignments = df  # Update session state with the new df
    st.cache_data.clear()
    return True


def reject_assignment(assign_id, reason) -> bool:
    if assign_id == "":
        return False
    df = st.session_state.assignments
    idx = df.index[df["assignment_id"] == assign_id]
    if len(idx) == 0:
        st.error("Assignment not found")
        return False

    df.loc[idx, "status"] = "REJECTED"
    df.loc[idx, "rejection_reason"] = reason
    df.loc[idx, "updated_at"] = datetime.utcnow().isoformat()

    save_csv(df, PATH_ASSIGN)
    st.cache_data.clear()
    return True


def send_email_smtp(to_addr: str, subject: str, body: str, is_html: bool = False) -> str:
    """Send immediately via SMTP, or write an .eml if EMAIL_MODE=eml or SMTP not set.
    Returns 'SENT' or 'EML:<path>' (preview mode). Raises on hard errors."""
    import smtplib, ssl
    from email.message import EmailMessage
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM", user or "no-reply@example.com")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    mode = os.getenv("EMAIL_MODE", "smtp").lower()

    # Preview mode or no SMTP → write .eml file
    if mode == "eml" or not host:
        out_dir = pathlib.Path(DATA_DIR) / "out_eml"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        if is_html:
            msg = MIMEMultipart('alternative')
            msg["From"], msg["To"], msg["Subject"] = from_addr, to_addr, subject
            msg.attach(MIMEText(body, 'html'))
        else:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = from_addr, to_addr, subject
            msg.set_content(body)
            
        fname = (
            out_dir
            / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}_{to_addr.replace('@','_')}.eml"
        )
        with open(fname, "wb") as f:
            f.write(bytes(msg))
        return f"EML:{fname}"

    # Real send
    if not all([host, port, user, pwd]):
        raise RuntimeError(
            "SMTP envs missing. Set SMTP_HOST/PORT/USER/PASS/SMTP_USE_TLS."
        )

    if is_html:
        msg = MIMEMultipart('alternative')
        msg["From"], msg["To"], msg["Subject"] = from_addr, to_addr, subject
        msg.attach(MIMEText(body, 'html'))
    else:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = from_addr, to_addr, subject
        msg.set_content(body)

    if use_tls:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.login(user, pwd)
            s.send_message(msg)

    return "SENT"


import json as _json

_UNITS = {
    "heartRate": "bpm",
    "oxygenSaturation": "%",
    "respiratoryRate": "brpm",
    "bodyTemperature": "°C",
}


def _row_get(row, key, default=None):
    # works for dicts AND pandas.Series
    try:
        if isinstance(row, dict):
            return row.get(key, default)
        return row[key] if key in row else default
    except Exception:
        return default


def _extract_feature_value(row):
    f = _row_get(row, "features")
    if isinstance(f, dict):
        return f.get("value")
    if isinstance(f, str):
        # try JSON first
        try:
            obj = _json.loads(f)
            if isinstance(obj, dict) and "value" in obj:
                return obj.get("value")
        except Exception:
            pass
        # then try to pull the first number from the string
        import re

        m = re.search(r"(-?\d+(?:\.\d+)?)", f)
        return float(m.group(1)) if m else None
    return None


def build_ai_payload_safe(row, doctor_name: str) -> dict:
    """Always return a well-formed payload dict built from the assignment/alert row."""
    student_id = _row_get(row, "student_id", "") or _row_get(row, "_id", "")
    student_name = _row_get(row, "name", "Student")
    student_email = _row_get(row, "email", "")
    metric = _row_get(row, "metric", "")
    value = _extract_feature_value(row)
    unit = _UNITS.get(metric, "")

    # Friendly default if reason is missing/technical
    reason = (
        _row_get(row, "reason") or "a reading that needs a quick in-person check"
    )
    severity = _row_get(row, "severity", "moderate")

    payload = {
        "student": {
            "id": student_id,
            "name": student_name,
            "email": student_email,
        },
        "doctor": {"name": doctor_name},
        "alert": {
            "reason": reason,
            "severity": severity,
            "metrics": (
                [{"name": metric, "value": value, "unit": unit}]
                if metric
                else []
            ),
        },
        # visit-focused steps (you can override elsewhere if you set them)
        "next_steps": [
            f"Please come to {os.getenv('CLINIC_LOCATION', 'the campus clinic')} {os.getenv('VISIT_HINT','today')}.",
            "Bring your student ID.",
        ],
    }
    return payload


def send_accept_email(row: dict, doctor_name_str: str) -> None:
    student_email = _row_get(row, "email", "")
    if not student_email:
        st.warning("Student email missing; skipping send.")
        return

    # Try your original builder; if it returns None or raises, fall back
    try:
        payload = build_ai_payload(row, doctor_name_str)
    except Exception:
        payload = None
    if not payload or not isinstance(payload, dict):
        payload = build_ai_payload_safe(row, doctor_name_str)

    # Ensure visit-specific steps (can be set via env)
    clinic_loc = os.getenv("CLINIC_LOCATION", "Campus Clinic (Room 2B)")
    visit_hint = os.getenv("VISIT_HINT", "today after class")
    clinic_phone = os.getenv("CLINIC_PHONE", "")
    steps = [
        f"Please come to {clinic_loc} {visit_hint}.",
        "Bring your student ID.",
    ]
    if clinic_phone:
        steps.append(f"If you feel unwell before you arrive, call {clinic_phone}.")
    payload["next_steps"] = steps

    # Generate the message (your AI/template function)
    subject, html_body, text_body = generate_student_message(payload)
    body = html_body  # Change this to text_body if you need plain text

    # Send immediately
    try:
        result = send_email_smtp(student_email, subject, html_body, is_html=True)
        log_email(
            student_email,
            subject,
            body,
            datetime.utcnow(),
            _row_get(row, "student_id", ""),
            doctor_name_str,
            _row_get(row, "severity", ""),
            _row_get(row, "reason", ""),
            status="SENT" if result == "SENT" else "SENT_PREVIEW",
        )
        log_audit(
            "email_sent",
            {"to": student_email, "result": result, "subject": subject},
        )
        st.toast("Email sent to student.", icon="✉️")
    except Exception as e:
        log_email(
            student_email,
            subject,
            body,
            datetime.utcnow(),
            _row_get(row, "student_id", ""),
            doctor_name_str,
            _row_get(row, "severity", ""),
            f"send_error: {e}",
            status="FAILED",
        )
        log_audit("email_failed", {"to": student_email, "error": str(e)})
        st.error(f"Email send failed: {e}")

logo_path = Path(__file__).parent / "src" / "assets" / "logo.png"

# =========================
# AUTH: Mongo-backed login / signup
# =========================
def doctor_auth_ui():
    # ---- SIDEBAR SHELL ----
    with st.sidebar:
        # BIG logo at the very top
        st.image(str(logo_path), width=140)   # adjust width as you like

        # Title under the logo
        st.markdown(
            """
            <div style="
                font-size: 1.4rem;
                font-weight: 700;
                margin-top: 0.5rem;
                margin-bottom: 1.5rem;
            ">
                Doctor Portal
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Already logged in
    if "doctor" in st.session_state:
        doc = st.session_state["doctor"]

        with st.sidebar:
            # Logged-in pill card
            st.markdown(
                f"""
                <div class="sidebar-card">
                    <div class="sidebar-badge">
                        <span class="sidebar-badge-dot"></span>
                        <span>Logged in as: <strong>{doc['name']}</strong></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Navigation label
            st.markdown('<div class="sidebar-section-label">Navigate</div>', unsafe_allow_html=True)

            page = st.radio(
                "Navigation",  # Use a non-empty label
                ["Queue", "Active", "Student Detail"],
                index=["Queue", "Active", "Student Detail"].index("Queue"),
                label_visibility="collapsed"  # Hide the label in UI
            )


            st.markdown("")  # small gap
            # Logout button
            with st.container():
                st.markdown('<div class="sidebar-logout">', unsafe_allow_html=True)
                if st.button("Logout"):
                    st.session_state.pop("doctor", None)
                    rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        return doc, page


    # Not logged in → choose Login / Sign up
    mode = st.sidebar.radio("Mode", ["Login", "Sign up"])

    if mode == "Login":
        st.sidebar.subheader("Login")
        email = st.sidebar.text_input("Email")
        password = st.sidebar.text_input("Password", type="password")
        page = "Queue"

        if st.sidebar.button("Login"):
            try:
                doc = verify_doctor(email, password)
            except Exception as e:
                st.sidebar.error(f"Login error: {e}")
                return None, page

            if not doc:
                st.sidebar.error("Invalid email or password.")
            else:
                display_doc = doctor_to_display(doc)
                st.session_state["doctor"] = display_doc
                st.sidebar.success("Login successful.")
                rerun()

        return None, page

    else:  # Sign up
        st.sidebar.subheader("Sign up as a doctor")

        name = st.sidebar.text_input("Full name")
        email = st.sidebar.text_input("Email")
        password = st.sidebar.text_input("Password", type="password")
        password2 = st.sidebar.text_input("Confirm password", type="password")
        specialty = st.sidebar.text_input("Specialty", value="cardiology")
        languages = st.sidebar.text_input(
            "Languages (comma-separated)", value="en"
        )
        max_load = st.sidebar.number_input(
            "Max active load", min_value=1, max_value=100, value=20, step=1
        )
        female = st.sidebar.checkbox("Female?", value=False)
        page = "Queue"

        if st.sidebar.button("Create account"):
            if not name or not email or not password:
                st.sidebar.error("Name, email, and password are required.")
                return None, page
            if password != password2:
                st.sidebar.error("Passwords do not match.")
                return None, page

            try:
                doc = create_doctor(
                    name=name,
                    email=email,
                    password=password,
                    specialty=specialty,
                    female=female,
                    languages=languages,
                    max_active_load=max_load,
                )
                display_doc = doctor_to_display(doc)
                st.session_state["doctor"] = display_doc
                st.sidebar.success("Account created and logged in.")
                rerun()
            except Exception as e:
                st.sidebar.error(str(e))

        return None, page


# =========================
# MAIN APP FLOW
# =========================
doctor_doc, page = doctor_auth_ui()
doctor_id = doctor_doc["doctor_id"] if doctor_doc else None
doctor_name = doctor_doc["name"] if doctor_doc else None

# Scope to this doctor (by name; worker writes doctor_name into assignments)
if doctor_name and not assignments.empty:
    if "doctor_name" in assignments.columns:
        my_assign = assignments.loc[
            assignments["doctor_name"] == doctor_name
        ].copy()
    else:
        my_assign = assignments.iloc[0:0].copy()
else:
    my_assign = assignments.iloc[0:0].copy()

if "status" not in my_assign.columns:
    my_assign["status"] = "PENDING"

my_pending = my_assign.loc[my_assign["status"] == "PENDING"].copy()
my_active = my_assign.loc[my_assign["status"] == "ACCEPTED"].copy()

# -------- UI --------
st.title("Personal Dashboard")

if not doctor_doc:
    st.info("Please log in or sign up as a doctor using the sidebar.")
else:
    if page in ("Queue"):
        # doctor-level metrics + charts
        render_doctor_overview(doctor_name, assignments)
        st.divider()

    if page == "Queue":
        st.subheader("Pending Alerts")
        df = join_students(join_alerts(my_pending.copy()))
        if df.empty:
            st.success("No pending alerts.")
        else:
            colf1, colf2, colf3 = st.columns(3)
            with colf1:
                severities = sorted(df["severity"].dropna().unique().tolist())
                f_sev = st.multiselect("Severity", severities, default=severities)
            with colf2:
                metrics_list = sorted(df["metric"].dropna().unique().tolist())
                f_met = st.multiselect("Metric", metrics_list, default=metrics_list)
            with colf3:
                since_default = datetime(2025, 11, 1).date()
                since = st.date_input("Since", value=since_default)

            # Apply filters
            if f_sev and "severity" in df.columns:
                df = df[df["severity"].isin(f_sev)]
            if f_met and "metric" in df.columns:
                df = df[df["metric"].isin(f_met)]

            # Date filter with proper datetime conversion
            if "created_at" in df.columns and since is not None:
                # Ensure created_at is datetime
                df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
                df = df.dropna(subset=["created_at"])
                
                # Convert since to timestamp with UTC timezone
                start_ts = pd.Timestamp(since, tz="UTC")
                
                # Now compare
                df = df[df["created_at"] >= start_ts]

            for _, row in df.sort_values("created_at", ascending=False).iterrows():
                with st.container():
                    st.divider()
                    c1, c2, c3, c4 = st.columns([3, 2, 3, 2])

                    # --- Left: avatar + student identity + reason/created ---
                    avatar_col, text_col = c1.columns([1, 5])

                    # Placeholder avatar (emoji; you can swap for st.image(...) later)
                    with avatar_col:
                        avatar_col.markdown(
                            """
                            <div style="
                                width: 42px;
                                height: 42px;
                                border-radius: 50%;
                                overflow: hidden;
                                border: 1px solid #374151;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                            ">
                                <img src="https://imgs.search.brave.com/RZ-seWKu77LHPYdVx97SY0pTe0LaVwVQ9m4Ga4FrkMQ/rs:fit:860:0:0:0/g:ce/aHR0cHM6Ly9tZWRp/YS5pc3RvY2twaG90/by5jb20vaWQvMTEy/OTc0ODE4OC92ZWN0/b3IvcGVyc29uLWdy/YXktcGhvdG8tcGxh/Y2Vob2xkZXItbWFu/LmpwZz9zPTYxMng2/MTImdz0wJms9MjAm/Yz0xYjh4R0h2amNJ/clBMbXN3cmlkTnN3/TWRSRDl6SENnUzNY/eHdfRTdBd3RzPQ"
                                    style="width: 100%; height: 100%; object-fit: cover;">
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    with text_col:
                        student_line = f"{row.get('name','(unknown)')}  •  {'Female' if row.get('female', False) else 'Male'}"
                        age_val = compute_age(row.get('dob'))
                        if age_val:
                            student_line += f"  •  {age_val}y"
                        text_col.markdown(f"**{student_line}**")

                        # Reason + metric
                        text_col.caption(
                            f"Reason: {row.get('reason','')}  |  Metric: {row.get('metric','')}"
                        )

                        # Created at
                        created_val = row.get("created_at", "")
                        if isinstance(created_val, (pd.Timestamp, datetime)):
                            created_str = created_val.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            created_str = str(created_val)
                        text_col.caption(f"Created: {created_str}")


                    # --- Middle: severity + features ---
                    sev = str(row.get("severity","")).capitalize()
                    c2.markdown(f"**Severity:** {sev}")
                    feat = row.get("features","")
                    c2.caption(f"Features: {feat if isinstance(feat,str) else str(feat)}")

                    with c3:
                        st.caption("Alert pattern")
                        chart = build_generic_alert_chart(row)
                        if chart is not None:
                            st.altair_chart(chart, use_container_width=True)
                        else:
                            # simple fallback if something goes wrong
                            st.caption("Created")
                            st.write(str(row.get("created_at", "")))


                    # --- Right: accept / reject controls ---
                    with c4:
                        aid = row.get("assignment_id","")
                        reason_choice = st.selectbox(
                            "Reject reason",
                            ["Not relevant", "Capacity", "Out of scope", "Other"],
                            key=f"rr_{aid}"
                        )
                        disabled = aid in st.session_state.busy_actions

                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("✅ Accept", key=f"a_{aid}", disabled=disabled):
                                st.session_state.busy_actions.add(aid)
                                with st.spinner("Accepting..."):
                                    ok = accept_assignment(aid, doctor_name)
                                    if ok:
                                        send_accept_email(row, doctor_name)
                                        log_audit("accept", {"assignment_id": aid, "doctor_name": doctor_name})
                                        st.toast("Accepted. Email queued to student.", icon="✅")
                                rerun()
                        with col_btn2:
                            if st.button("❌ Reject", key=f"r_{aid}", disabled=disabled):
                                st.session_state.busy_actions.add(aid)
                                with st.spinner("Rejecting..."):
                                    ok = reject_assignment(aid, reason_choice)
                                    if ok:
                                        log_audit("reject", {
                                            "assignment_id": aid,
                                            "doctor_name": doctor_name,
                                            "reason": reason_choice,
                                        })
                                        st.toast("Rejected. Re-routing server-side.", icon="⚠️")
                                rerun()


    elif page == "Active":
        st.subheader("Active Cases")

        df = join_students(join_alerts(my_active.copy()))
        if df.empty:
            st.info("No active cases.")
        else:
            # ---- Summary bar chart: active cases by event type ----
            if "reason" in df.columns:
                # group by event type (reason) and severity
                summary = (
                    df.groupby(["reason", "severity"])
                      .size()
                      .reset_index(name="count")
                )

                if not summary.empty:
                    import altair as alt  # already imported earlier, but safe

                    chart = (
                        alt.Chart(summary)
                        .mark_bar()
                        .encode(
                            x=alt.X("reason:N", title="Event type", axis=alt.Axis(labelAngle=0)),
                            y=alt.Y("count:Q", title="Active cases"),
                            color=alt.Color("severity:N", title="Severity"),
                            tooltip=["reason", "severity", "count"],
                        )
                        .properties(height=280)
                    )
                    st.altair_chart(chart, use_container_width=True)
                    st.markdown("---")

            # ---- Details table (same as before) ----
            show_cols = [
                "student_id",
                "name",
                "severity",
                "reason",
                "metric",
                "created_at",
                "rationale",
            ]
            show_cols = [c for c in show_cols if c in df.columns]
            st.dataframe(df[show_cols])


    
    elif page == "Student Detail":
        st.subheader("Student Details")
        ids_series = (
            pd.concat([my_pending["student_id"], my_active["student_id"]])
            if (not my_pending.empty or not my_active.empty)
            else pd.Series([], dtype=str)
        )
        df_ids = ids_series.dropna().unique().tolist()
        if not df_ids:
            st.info("No students to show. Accept or view a pending alert first.")
        else:
            student_id = st.selectbox("Student", options=df_ids)

            # Student card
            srows = pd.DataFrame()
            if "student_id" in students.columns and student_id in students["student_id"].values:
                srows = students[students["student_id"] == student_id]
            elif "_id" in students.columns and student_id in students["_id"].values:
                srows = students[students["_id"] == student_id]

            if not srows.empty:
                srow = srows.iloc[0]
                avatar_col, text_col = st.columns([0.05, 0.95])

                with avatar_col:
                    st.markdown(
                        f'''
                        <div style="
                            width: 42px;
                            height: 42px;
                            border-radius: 50%;
                            overflow: hidden;
                            border: 1px solid #374151;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                        ">
                            <img src="https://imgs.search.brave.com/RZ-seWKu77LHPYdVx97SY0pTe0LaVwVQ9m4Ga4FrkMQ/rs:fit:860:0:0:0/g:ce/aHR0cHM6Ly9tZWRp/YS5pc3RvY2twaG90/by5jb20vaWQvMTEy/OTc0ODE4OC92ZWN0/b3IvcGVyc29uLWdy/YXktcGhvdG8tcGxh/Y2Vob2xkZXItbWFu/LmpwZz9zPTYxMng2/MTImdz0wJms9MjAm/Yz0xYjh4R0h2amNJ/clBMbXN3cmlkTnN3/TWRSRDl6SENnUzNY/eHdfRTdBd3RzPQ"
                                style="width: 100%; height: 100%; object-fit: cover;">
                        </div>
                        ''',
                        unsafe_allow_html=True,
                    )

                with text_col:
                    name = srow.get("name", "Student")
                    gender = "Female" if srow.get("female", False) else "Male"
                    st.markdown(f"**{name} — {gender}**")
                    st.caption(f"Email: {srow.get('email','')}")

            # --- Load metrics matching student_id ---
            m = pd.DataFrame()
            if "student_id" in metrics.columns and student_id in metrics["student_id"].values:
                m = metrics[metrics["student_id"] == student_id].copy()
            elif "_id" in metrics.columns and student_id in metrics["_id"].values:
                m = metrics[metrics["_id"] == student_id].copy()

            if m.empty:
                st.info("No metric data for this student.")
            else:
                if "timestamp" in m.columns:
                    m["timestamp"] = pd.to_datetime(m["timestamp"], errors="coerce")

                if {"metric", "value"}.issubset(m.columns):
                    pivot = (
                        m.pivot_table(index="timestamp", columns="metric", values="value", aggfunc="mean")
                        .reset_index()
                        .sort_values("timestamp")
                    )
                    available_metrics = [c for c in pivot.columns if c != "timestamp"]
                    if not available_metrics:
                        st.info("No numeric metrics to display.")
                    else:
                        metric_name = st.selectbox("Metric", options=sorted(available_metrics))
                        sel = pivot[["timestamp", metric_name]].dropna()
                        if sel.empty:
                            st.info("No data points in range.")
                        else:
                            end = sel["timestamp"].max()
                            start = end - pd.Timedelta(days=7)
                            sel = sel[(sel["timestamp"] >= start) & (sel["timestamp"] <= end)]
                            st.caption("Showing last 7 days")

                            vals = pd.to_numeric(sel[metric_name], errors="coerce").dropna()
                            if len(vals) >= 3:
                                med = float(np.median(vals))
                                mad = float(np.median(np.abs(vals - med))) or max(1.0, med * 0.05)
                                band_low, band_high = med - 3 * mad, med + 3 * mad
                            else:
                                med = sel[metric_name].astype(float).mean()
                                band_low, band_high = med * 0.9, med * 1.1

                            base = alt.Chart(sel).encode(x="timestamp:T")
                            line = base.mark_line().encode(y=alt.Y(f"{metric_name}:Q", title=metric_name))
                            band = base.mark_area(opacity=0.2).encode(
                                y=alt.Y2(value=band_high), y2=alt.Y2(value=band_low)
                            )
                            st.altair_chart((band + line).properties(height=280), use_container_width=True)
                else:
                    numeric_cols = [
                        c for c in m.columns
                        if c not in ["_id", "timestamp", "device", "female", "student_id"]
                        and pd.api.types.is_numeric_dtype(m[c])
                    ]
                    if not numeric_cols:
                        st.info("No numeric metrics to display.")
                    else:
                        metric_name = st.selectbox("Metric", options=sorted(numeric_cols))
                        m = m.sort_values("timestamp")
                        if m["timestamp"].notna().any():
                            end = m["timestamp"].max()
                            start = end - pd.Timedelta(days=7)
                            m_window = m[(m["timestamp"] >= start) & (m["timestamp"] <= end)]
                        else:
                            m_window = m
                        if len(m_window) < 2:
                            m_window = m.tail(30)
                            st.caption("Not enough data in last 7 days – showing latest readings.")
                        else:
                            st.caption("Showing last 7 days")
                        base = alt.Chart(m_window).encode(
                            x=alt.X("timestamp:T", title="Date", axis=alt.Axis(format="%b %d", labelAngle=0))
                        )
                        line = base.mark_line().encode(y=alt.Y(f"{metric_name}:Q", title=metric_name))
                        st.altair_chart(line.properties(height=280), use_container_width=True)

            # Show this student's alerts from queue/active
            stu_alerts = (
                pd.concat([join_alerts(my_pending), join_alerts(my_active)])
                if (not my_pending.empty or not my_active.empty)
                else pd.DataFrame()
            )
            if not stu_alerts.empty:
                stu_alerts = stu_alerts[stu_alerts["student_id"] == student_id]
                if not stu_alerts.empty:
                    st.markdown("**Alerts for this student**")
                    show_cols = [
                        "severity", "reason", "metric", "created_at",
                        "assignment_id", "status"
                    ]
                    show_cols = [c for c in show_cols if c in stu_alerts.columns]
                    st.dataframe(stu_alerts[show_cols].sort_values("created_at", ascending=False))

