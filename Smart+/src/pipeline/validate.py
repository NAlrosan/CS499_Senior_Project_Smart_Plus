import pandas as pd
import numpy as np

def clip_ranges(df: pd.DataFrame) -> pd.DataFrame:
    # conservative physiologic limits
    clip_map = {
        "heartRate": (40, 200),
        "restingHeartRate": (40, 120),
        "heartRateVariabilitySDNN": (5, 250),
        "oxygenSaturation": (85, 100),
        "respiratoryRate": (8, 40),
        "bodyTemperature": (35.5, 40.5),
        "appleSleepingWristTemperature": (34.0, 37.5),
        "bloodPressureSystolic": (80, 220),
        "bloodPressureDiastolic": (40, 140),
        "forcedExpiratoryVolume1": (0.5, 7.0),
        "forcedVitalCapacity": (1.0, 8.0),
        "peakExpiratoryFlowRate": (100, 900),
        "bloodGlucose": (40, 400),
        "atrialFibrillationBurden": (0, 10),
    }
    for col, (lo, hi) in clip_map.items():
        if col in df.columns:
            df[col] = df[col].astype(float).clip(lo, hi)
    return df

def drop_dupes(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(subset=["_id","timestamp"]).copy()

def ensure_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cast numeric columns to numbers but DO NOT drop rows just because some
    optional fields are missing. Only require:
      - timestamp is present
      - at least one key vital sign is present.
    """
    # cast everything numeric-ish except id/time/labels
    for col in df.columns:
        if col in {"_id", "timestamp", "ecgClassification",
                   "appleWalkingSteadinessEvent", "device"}:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # keep only rows with a timestamp
    if "timestamp" in df.columns:
        df = df.dropna(subset=["timestamp"])

    # require at least one of these vitals to be present
    key_vitals = [
        "heartRate",
        "oxygenSaturation",
        "respiratoryRate",
        "bodyTemperature",
        "bloodPressureSystolic",
        "bloodGlucose",
    ]
    existing = [c for c in key_vitals if c in df.columns]
    if existing:
        df = df.dropna(subset=existing, how="all")

    return df.copy()
