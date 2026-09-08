import pandas as pd
import numpy as np
from uuid import uuid4

def robust_stats(s: pd.Series):
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) == 0:
        return np.nan, np.nan
    med = np.median(s)
    mad = np.median(np.abs(s - med)) or 1.0
    return med, mad

def build_baselines(metrics: pd.DataFrame, students: pd.DataFrame):
    METRIC_COLS = [c for c in metrics.columns if c not in {"_id","timestamp","device","female"}]
    students = students.copy()
    if "female" in students.columns:
        students["female"] = students["female"].astype(bool)
    female_map = dict(zip(students["_id"], students["female"])) if "_id" in students.columns else {}

    baselines = []
    for metric in METRIC_COLS:
        if metrics[metric].dtype.kind not in "biufc":  # numeric only
            continue
        for sid, g in metrics.groupby("_id"):
            med, mad = robust_stats(g[metric])
            if np.isnan(med):
                # cohort fallback by gender
                if "female" in students.columns and not students.empty:
                    is_female = female_map.get(
                        sid,
                        students["female"].mode(dropna=True).iloc[0]
                    )
                    cohort = metrics.loc[metrics["female"] == bool(is_female), metric] \
                             if "female" in metrics.columns else metrics[metric]
                else:
                    cohort = metrics[metric]
                med, mad = robust_stats(cohort)
            baselines.append({"_id": sid, "metric": metric, "median": med, "mad": mad})
    return pd.DataFrame(baselines)

def get_base(baselines: pd.DataFrame, sid: str, metric: str):
    row = baselines[(baselines["_id"] == sid) & (baselines["metric"] == metric)]
    if row.empty:
        return (np.nan, 1.0)
    return float(row["median"].iloc[0]), max(float(row["mad"].iloc[0]), 1.0)

# ------------------------------
# RULES
# ------------------------------

RULES = [
    # Heart rate – critical absolute tachycardia
    (
        "heartRate",
        lambda r, m, d: (
            (r["heartRate"] >= 150) and not r.get("in_workout", False),
            "critical",
            "severe_tachycardia",
            "cardiology",
        ),
    ),

    # Heart rate – moderate when absolutely high even if baseline is weird
    (
        "heartRate",
        lambda r, m, d: (
            (r["heartRate"] >= 120) and not r.get("in_workout", False),
            "moderate",
            "tachycardia_high_absolute",
            "cardiology",
        ),
    ),

    # Heart rate – moderate vs personal baseline (what you had before)
    (
        "heartRate",
        lambda r, m, d: (
            (r["heartRate"] > m + 3 * d) and not r.get("in_workout", False),
            "moderate",
            "tachycardia_at_rest",
            "cardiology",
        ),
    ),

    # Oxygen saturation
    (
        "oxygenSaturation",
        lambda r, m, d: (
            r["oxygenSaturation"] <= 85,
            "critical",
            "severe_hypoxemia",
            "pulmonology",
        ),
    ),
    (
        "oxygenSaturation",
        lambda r, m, d: (
            r["oxygenSaturation"] <= 90,
            "moderate",
            "hypoxemia",
            "pulmonology",
        ),
    ),

    # Respiratory rate
    (
        "respiratoryRate",
        lambda r, m, d: (
            r["respiratoryRate"] > 24,
            "moderate",
            "tachypnea",
            "pulmonology",
        ),
    ),

    # Body temperature
    (
        "bodyTemperature",
        lambda r, m, d: (
            r["bodyTemperature"] >= 39.0,
            "critical",
            "high_fever",
            "primary_care",
        ),
    ),
    (
        "bodyTemperature",
        lambda r, m, d: (
            r["bodyTemperature"] >= 38.0,
            "moderate",
            "fever",
            "primary_care",
        ),
    ),

    # (keep your existing BP / glucose rules below as they were)
]

def extra_event_rules(row):
    outs = []
    if "irregularHeartRhythmEvent" in row and bool(row["irregularHeartRhythmEvent"]):
        outs.append(("critical", "irregular_heart_rhythm_event", "cardiology"))
    if "ecgClassification" in row and str(row["ecgClassification"]).lower() in {"afib","atrial_fibrillation"}:
        outs.append(("critical", "ecg_afib", "cardiology"))
    if "numberOfTimesFallen" in row and row["numberOfTimesFallen"] > 0:
        outs.append(("critical", "fall_detected", "sports_medicine"))
    if "appleWalkingSteadinessEvent" in row and str(row["appleWalkingSteadinessEvent"]).lower() in {"good","bad"}:
        outs.append(("moderate", "walking_steadiness_event", "sports_medicine"))
    return outs

def sleep_rules(row):
    """
    Detect sleep-related anomalies for sleep_medicine routing.
    """
    outs = []

    val = row.get("sleepAnalysisValue", None)
    if val is None:
        return outs

    # Example mapping:
    # 0 = normal sleep
    # 1 = insomnia / awake
    # 2 = light sleep
    # 3 = REM disturbance
    # 4 = interrupted sleep

    if val in [1]:  
        outs.append(("moderate", "insomnia", "sleep_medicine"))

    if val in [2, 4]:
        outs.append(("moderate", "sleep_fragmentation", "sleep_medicine"))

    if val in [3]:
        outs.append(("moderate", "poor_sleep_quality", "sleep_medicine"))

    return outs

def detect_alerts(metrics: pd.DataFrame, students: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame(
            columns=[
                "alert_id",
                "student_id",
                "metric",
                "window_start",
                "window_end",
                "severity",
                "reason",
                "features",
                "routed_specialty",
                "created_at",
            ]
        )

    baselines = build_baselines(metrics, students)
    alerts = []
    last_fired = {}
    def k(sid, metric, reason): return f"{sid}|{metric}|{reason}"
    cooldown = pd.Timedelta(minutes=60)

    ms = metrics.sort_values(["_id", "timestamp"])
    for _, r in ms.iterrows():
        sid = r["_id"]
        ts = r["timestamp"]
        row = r.to_dict()

        # numeric rules
        for metric, fn in RULES:
            if metric not in row:
                continue
            med, mad = get_base(baselines, sid, metric)
            fired, severity, reason, specialty = fn(row, med, mad)
            if fired:
                key = k(sid, metric, reason)
                if key in last_fired and (ts - last_fired[key]) < cooldown:
                    continue
                last_fired[key] = ts
                alerts.append({
                    "alert_id": str(uuid4()),
                    "student_id": sid,
                    "metric": metric,
                    "window_start": ts.isoformat(),
                    "window_end": ts.isoformat(),
                    "severity": severity,
                    "reason": reason,
                    "features": {
                        "value": row[metric],
                        "baseline_median": med,
                        "baseline_mad": mad,
                    },
                    "routed_specialty": specialty,
                    "created_at": ts.isoformat(),
                })

        # event rules
        for severity, reason, specialty in extra_event_rules(row):
            key = k(sid, "event", reason)
            if key in last_fired and (ts - last_fired[key]) < cooldown:
                continue
            last_fired[key] = ts
            alerts.append({
                "alert_id": str(uuid4()),
                "student_id": sid,
                "metric": "event",
                "window_start": ts.isoformat(),
                "window_end": ts.isoformat(),
                "severity": severity,
                "reason": reason,
                "features": {},
                "routed_specialty": specialty,
                "created_at": ts.isoformat(),
            })
        
        # sleep anomaly rules -------------------------
        for severity, reason, specialty in sleep_rules(row):
            key = k(sid, "sleep", reason)
            if key in last_fired and (ts - last_fired[key]) < cooldown:
                continue
            last_fired[key] = ts
            alerts.append({
                "alert_id": str(uuid4()),
                "student_id": sid,
                "metric": "sleepAnalysisValue",
                "window_start": ts.isoformat(),
                "window_end": ts.isoformat(),
                "severity": severity,
                "reason": reason,
                "features": {"value": row.get("sleepAnalysisValue")},
                "routed_specialty": specialty,
                "created_at": ts.isoformat(),
            })


    return pd.DataFrame(alerts)
