import pandas as pd
import numpy as np
from uuid import uuid4

def pick_doctor(doctors: pd.DataFrame, students: pd.DataFrame, student_id: str, specialty: str):
    students = students.copy()
    doctors = doctors.copy()

    # normalize
    if "female" in students.columns:
        students["female"] = students["female"].astype(bool)
    if "female" in doctors.columns:
        doctors["female"] = doctors["female"].astype(bool)

    # ---- determine student gender ----
    if (
        "_id" in students.columns and
        "female" in students.columns and
        (students["_id"] == student_id).any()
    ):
        student_gender = bool(students.loc[students["_id"] == student_id, "female"].iloc[0])
    else:
        student_gender = False  # default male if unknown

    # ---- filter by gender + active status ----
    pool = doctors[
        (doctors["female"] == student_gender) &
        (doctors.get("status", "active") == "active")
    ].copy()

    # ---- match specialty (list-based) ----
    if "specialty" in pool.columns:
        # primary specialty candidates
        cand = pool[
            pool["specialty"].apply(lambda sp: specialty in sp)
        ]

        # fallback to primary care
        if cand.empty:
            cand = pool[
                pool["specialty"].apply(lambda sp: "primary_care" in sp)
            ]
    else:
        cand = pool

    # failed to find specialist
    if cand.empty:
        return None, doctors

    # ---- under capacity only ----
    cand = cand[cand["active_load"] < cand["max_active_load"]]
    if cand.empty:
        return None, doctors

    # ---- load balancing ----
    cand = cand.copy()
    cand["load_ratio"] = cand["active_load"] / cand["max_active_load"].replace({0: np.nan})
    cand["load_ratio"] = cand["load_ratio"].fillna(0)

    chosen = cand.sort_values(
        ["load_ratio", "active_load"],
        ascending=[True, True]
    ).iloc[0]

    chosen_name = chosen["name"]

    # update doctor active load
    doctors.loc[doctors["name"] == chosen_name, "active_load"] += 1

    return chosen_name, doctors


def build_assignments(alerts: pd.DataFrame, doctors: pd.DataFrame, students: pd.DataFrame) -> pd.DataFrame:
    if alerts.empty:
        return pd.DataFrame(columns=[
            "assignment_id", "alert_id", "student_id", "doctor_name",
            "status", "rationale", "created_at", "updated_at"
        ])

    doctors = doctors.copy()
    rows = []

    for _, a in alerts.iterrows():
        doctor_name, doctors = pick_doctor(
            doctors,
            students,
            a["student_id"],
            a["routed_specialty"]
        )

        rows.append({
            "assignment_id": str(uuid4()),
            "alert_id": a["alert_id"],
            "student_id": a["student_id"],
            "doctor_name": doctor_name or "",
            "status": "PENDING" if doctor_name else "HOLD",
            "rationale": (
                f"gender_concordant::{a['routed_specialty']}"
                if doctor_name else "no_same_gender_doctor_available"
            ),
            "created_at": a["created_at"],
            "updated_at": a["created_at"],
        })

    return pd.DataFrame(rows)
