
import csv, os, json, random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.paths import data_path, data_dir

FILES_TO_WIPE = [
    "alerts.csv", "assignments.csv", "audit_log.csv", "email_outbox.csv", ".state.json"
]

STUDENTS_CSV = data_path("students.csv")
METRICS_CSV  = data_path("metrics.csv")

def wipe_files():
    for name in FILES_TO_WIPE:
        p = data_path(name)
        if p.exists():
            p.unlink()
            print(f"Deleted {p}")
        root_p = Path(name)
        if root_p.exists():
            root_p.unlink()
            print(f"Deleted {root_p}")

def pick_student():
    with STUDENTS_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("students.csv is empty.")
    for r in rows:
        if r.get("email") and "@" in r["email"] and not r["email"].endswith("example.edu"):
            return r
    return rows[0]

def seed_metrics_for(student, minutes=20):
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)
    sid = student.get("student_id") or student.get("id") or "S001"

    fields = ["timestamp","student_id","metric","value","unit","features"]
    with METRICS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        t = start
        while t <= now:
            hr = random.randint(72, 86)
            spo2 = random.randint(96, 99)
            rr = random.randint(12, 18)

            if now - timedelta(minutes=8) <= t <= now - timedelta(minutes=5):
                hr = random.randint(110, 124)
                spo2 = random.randint(90, 93)

            def row(metric, value, unit):
                feat = {"value": value, "source": "seed_demo"}
                return {
                    "timestamp": t.isoformat(),
                    "student_id": sid,
                    "metric": metric,
                    "value": value,
                    "unit": unit,
                    "features": json.dumps(feat, ensure_ascii=False),
                }

            w.writerow(row("heartRate", hr, "bpm"))
            w.writerow(row("oxygenSaturation", spo2, "%"))
            w.writerow(row("respiratoryRate", rr, "brpm"))
            t += timedelta(minutes=1)

    print(f"Seeded demo readings for {sid} -> {METRICS_CSV}")

def main():
    print("Resetting demo state...")
    data_dir().mkdir(exist_ok=True)
    wipe_files()
    student = pick_student()
    print(f"Using student: {student.get('name')} <{student.get('email','n/a')}>")
    seed_metrics_for(student, minutes=20)
    print("Done. Start the app to see fresh alerts soon.")

if __name__ == "__main__":
    main()
