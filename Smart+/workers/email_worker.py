# import os, csv, smtplib, ssl, tempfile, shutil
# from datetime import datetime, timezone
# from email.message import EmailMessage
# from pathlib import Path
# from dotenv import load_dotenv
# from src.paths import data_path
# load_dotenv()  # loads variables from a .env file in the current folder

# OUTBOX = data_path("email_outbox.csv")
# FIELDS = [
#     "id","status","queued_at","to","subject","body","send_at",
#     "student_id","doctor_name","severity","reason"
# ]

# def _utcnow():
#     return datetime.now(timezone.utc)

# def _parse_dt(x: str):
#     # tolerate 'Z' or naive ISO
#     if not x:
#         return _utcnow()
#     try:
#         if x.endswith("Z"):
#             return datetime.fromisoformat(x.replace("Z","+00:00"))
#         return datetime.fromisoformat(x if "+" in x else x + "+00:00")
#     except Exception:
#         return _utcnow()

# def _send_smtp(to_addr: str, subject: str, body: str):
#     host = os.getenv("SMTP_HOST")
#     port = int(os.getenv("SMTP_PORT", "587"))
#     user = os.getenv("SMTP_USER")
#     pwd  = os.getenv("SMTP_PASS")
#     from_addr = os.getenv("SMTP_FROM", user or "no-reply@example.com")
#     use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

#     if not host:
#         raise RuntimeError("SMTP_HOST not set")

#     msg = EmailMessage()
#     msg["From"] = from_addr
#     msg["To"] = to_addr
#     msg["Subject"] = subject
#     msg.set_content(body)

#     if use_tls:
#         context = ssl.create_default_context()
#         with smtplib.SMTP(host, port) as s:
#             s.starttls(context=context)
#             if user and pwd:
#                 s.login(user, pwd)
#             s.send_message(msg)
#     else:
#         with smtplib.SMTP(host, port) as s:
#             if user and pwd:
#                 s.login(user, pwd)
#             s.send_message(msg)

# def _rewrite(rows):
#     tmp = OUTBOX.with_suffix(".tmp")
#     with tmp.open("w", newline="", encoding="utf-8") as f:
#         w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
#         w.writeheader()
#         for r in rows:
#             row = {k: r.get(k, "") for k in FIELDS}
#             w.writerow(row)
#     shutil.move(tmp, OUTBOX)

# def run_once():
#     if not OUTBOX.exists():
#         print("Outbox is empty.")
#         return

#     with OUTBOX.open(newline="", encoding="utf-8") as f:
#         rows = list(csv.DictReader(f))

#     now = _utcnow()
#     changed = False

#     for r in rows:
#         status = (r.get("status") or "QUEUED").upper()
#         if status not in ("QUEUED","FAILED"):
#             continue

#         send_at = _parse_dt(r.get("send_at",""))
#         if send_at > now:
#             continue  # scheduled for later

#         try:
#             _send_smtp(r["to"], r["subject"], r["body"])
#             r["status"] = "SENT"
#             changed = True
#             rid = r.get("id", "(no-id)")
#             print(f"Sent: {rid} → {r.get('to')}")
#         except Exception as e:
#             r["status"] = "FAILED"
#             r["reason"] = (r.get("reason") or "")[:180] + f" | send_error: {e}"
#             changed = True
#             rid = r.get("id", "(no-id)")
#             print(f"FAILED: {rid} → {r.get('to')} :: {e}")

#     if changed:
#         _rewrite(rows)

# if __name__ == "__main__":
#     run_once()

import os, csv, smtplib, ssl, tempfile, shutil
from datetime import datetime, timezone
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv
from src.paths import data_path
load_dotenv()

OUTBOX = data_path("email_outbox.csv")
FIELDS = [
    "id","status","queued_at","to","subject","body","send_at",
    "student_id","doctor_name","severity","reason","is_html"
]

def _utcnow():
    return datetime.now(timezone.utc)

def _parse_dt(x: str):
    if not x:
        return _utcnow()
    try:
        if x.endswith("Z"):
            return datetime.fromisoformat(x.replace("Z","+00:00"))
        return datetime.fromisoformat(x if "+" in x else x + "+00:00")
    except Exception:
        return _utcnow()

def _send_smtp(to_addr: str, subject: str, body: str, is_html: bool = False):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM", user or "no-reply@example.com")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    if not host:
        raise RuntimeError("SMTP_HOST not set")

    if is_html:
        # Use MIMEMultipart for HTML emails
        msg = MIMEMultipart('alternative')
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        
        # Attach HTML content
        msg.attach(MIMEText(body, 'html'))
    else:
        # Use simple EmailMessage for plain text
        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(body)

    if use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port) as s:
            s.starttls(context=context)
            if user and pwd:
                s.login(user, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            if user and pwd:
                s.login(user, pwd)
            s.send_message(msg)

def _rewrite(rows):
    tmp = OUTBOX.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            row = {k: r.get(k, "") for k in FIELDS}
            w.writerow(row)
    shutil.move(tmp, OUTBOX)

def run_once():
    if not OUTBOX.exists():
        print("Outbox is empty.")
        return

    with OUTBOX.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    now = _utcnow()
    changed = False

    for r in rows:
        status = (r.get("status") or "QUEUED").upper()
        if status not in ("QUEUED","FAILED"):
            continue

        send_at = _parse_dt(r.get("send_at",""))
        if send_at > now:
            continue

        try:
            is_html = r.get("is_html", "false").lower() == "true"
            _send_smtp(r["to"], r["subject"], r["body"], is_html=is_html)
            r["status"] = "SENT"
            changed = True
            rid = r.get("id", "(no-id)")
            print(f"Sent: {rid} → {r.get('to')}")
        except Exception as e:
            r["status"] = "FAILED"
            r["reason"] = (r.get("reason") or "")[:180] + f" | send_error: {e}"
            changed = True
            rid = r.get("id", "(no-id)")
            print(f"FAILED: {rid} → {r.get('to')} :: {e}")

    if changed:
        _rewrite(rows)

if __name__ == "__main__":
    run_once()