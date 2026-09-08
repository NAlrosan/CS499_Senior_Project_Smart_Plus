# tools/peek_outbox.py
import csv, sys
from pathlib import Path
from src.paths import data_path

path = data_path("email_outbox.csv")
if not path.exists():
    print("email_outbox.csv not found")
    sys.exit(0)

with path.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader, 1):
        print(f"\n--- Message #{i} ---")
        print("queued_at:", row.get("queued_at"))
        print("to:", row.get("to"))
        print("subject:", row.get("subject"))
        print("send_at:", row.get("send_at"))
        print("student_id:", row.get("student_id"))
        print("doctor_name:", row.get("doctor_name"))
        print("severity:", row.get("severity"))
        print("reason:", row.get("reason"))
        print("\nBODY:\n", row.get("body", "(empty)"))