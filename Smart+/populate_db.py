import os
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import random

# Load env vars
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "healthdb")
COLL_NAME = os.getenv("RAW_COLL", "health_data")

client = MongoClient(MONGO_URI)
collection = client[DB_NAME][COLL_NAME]

devices = [
    "com.apple.health.DEVICE5",
    "com.apple.health.DEVICE6",
    "com.apple.health.DEVICE7",
    "com.apple.health.DEVICE8"
]

anomalies = [
    "irregular_heart_rhythm",   # Cardiology
    "low_respiratory_rate",     # Pulmonology
    "poor_sleep_quality",       # Sleep Medicine
    "irregular_sleep",           # Sleep Medicine
    "insomnia",                  # Sleep Medicine
    "low_sleep_quality",         # Sleep Medicine
    "delayed_onset",
    "frequent_falls",            # Sports Medicine
]

def generate_record(ts, device, anomaly):
    heart_rate = random.uniform(60, 70)
    oxygen = random.uniform(99, 99)
    glucose = random.uniform(100, 110)
    resp_rate = random.uniform(13.5, 15)
    falls = 0
    irregular = 0
    sleep_value = 2

    if anomaly == "irregular_heart_rhythm":
        irregular = 1
    elif anomaly == "low_respiratory_rate":
        resp_rate = random.uniform(9.0, 11.5)
    elif anomaly == "poor_sleep_quality":
        sleep = 0
    elif anomaly == "frequent_falls":
        falls = random.randint(2, 4)
    elif anomaly == "irregular_sleep":
        sleep_value = 2  # Light sleep tag
    elif anomaly == "insomnia":
        sleep_value = 1  # Awake tag
    elif anomaly == "low_sleep_quality":
        sleep_value = 3  # REM
    elif anomaly == "delayed_onset":
        sleep_value = 4  # Interrupted
    elif anomaly == "frequent_falls":
        falls = random.randint(2, 4)

    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "restingHeartRate": round(random.uniform(55, 60), 2),
        "heartRateVariabilitySDNN": round(random.uniform(30, 60), 2),
        "heartRate": round(heart_rate, 2),
        "oxygenSaturation": round(oxygen, 2),
        "respiratoryRate": round(resp_rate, 2),
        "bodyTemperature": round(random.uniform(35.5, 36.5), 2),
        "sleepAnalysisValue": sleep_value,
        "appleSleepingWristTemperature": round(random.uniform(34.0, 36.0), 2),
        "irregularHeartRhythmEvent": 0,
        "highHeartRateEvent": 0,
        "lowHeartRateEvent": 0,
        "ecgClassification": "sinus",
        "ecgAverageHeartRate": round(random.uniform(60, 70), 2),
        "numberOfTimesFallen": falls,
        "atrialFibrillationBurden": None,
        "bloodPressureSystolic": round(random.uniform(110, 125), 2),
        "bloodPressureDiastolic": round(random.uniform(70, 80), 2),
        "appleWalkingSteadiness": 2,
        "appleWalkingSteadinessEvent": 0,
        "forcedExpiratoryVolume1": None,
        "forcedVitalCapacity": None,
        "peakExpiratoryFlowRate": None,
        "insulinDelivery": None,
        "bloodGlucose": random.uniform(85, 105),
        "device": device,
    }

start_time = datetime(2025, 11, 4, 17, 27, 21)
records = []
for i, device in enumerate(devices):
    for j in range(6):
        ts = start_time + timedelta(days=j, hours=random.randint(0, 3), minutes=random.randint(0, 59))
        anomaly_type = anomalies[i]
        records.append(generate_record(ts, device, anomaly_type))

# Insert new records (keep existing)
result = collection.insert_many(records)
print(f"Inserted {len(result.inserted_ids)} health records.")

