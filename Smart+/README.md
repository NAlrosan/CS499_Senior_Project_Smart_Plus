# Smart+ — Campus Health Monitoring & Alert Routing System

Smart+ is a full-stack health monitoring platform built as a senior capstone project. It ingests continuous wearable/device health data (heart rate, SpO2, ECG, blood pressure, respiratory rate, and more), detects clinically meaningful anomalies against each student's own baseline, and routes alerts to the right on-campus doctor — closing the loop with automated, AI-assisted notifications and a doctor-facing triage dashboard.

## ✨ Key Features

- **Continuous ingestion pipeline** — background workers (HTTP + MongoDB variants) poll a device data source on a schedule, validate and clean incoming readings, and persist them.
- **Personalized anomaly detection** — robust per-student baselines (median/MAD) computed from historical data, with cohort fallback (by gender) for students with insufficient history, so alerts reflect deviation from *that individual's* norm rather than a single global threshold.
- **Rule-based clinical triage** — configurable physiologic range clipping and rule engine (`src/pipeline/rules.py`) classifies alerts by severity and routes them to the appropriate specialty (cardiology, sleep medicine, etc.).
- **Automated assignment & routing** — `src/pipeline/assign.py` matches alerts to available doctors using specialty and gender-concordance logic, then tracks assignment status (pending/accepted/rejected) end-to-end.
- **Doctor dashboard (Streamlit)** — a multi-page app (`app.py`) for doctors to authenticate, review a live alert queue, drill into a student's history and vitals charts, and accept/reject/route cases.
- **AI-assisted messaging** — integrates Google's Gemini API to draft patient-friendly explanations of clinical alerts, with a template-based fallback so the system degrades gracefully without an API key.
- **Email notifications** — SMTP-based outbox system with delivery logging and an auditable event log.
- **Dual persistence** — MongoDB as the primary data store, with CSV compatibility mode for local development/demo, and automatic fallback if Mongo is unavailable.
- **Data validation with Pydantic** — strict schema validation (`src/pipeline/schema.py`) on incoming metric rows, including cross-field checks (e.g. FVC must exceed FEV1).

## 🏗️ Architecture

```
Device / Health API
        │
        ▼
 worker_http.py / worker_mongo.py  ──▶  validate → clip_ranges → detect_alerts → build_assignments
        │                                                                              │
        ▼                                                                              ▼
   MongoDB (raw/clean/alerts/assignments)  ◀───────────────────────────────  CSV compat layer (data/)
        │
        ▼
   app.py (Streamlit doctor dashboard) ──▶ accept/reject ──▶ ai_messaging.py ──▶ email_worker.py (SMTP)
```

- **`src/config.py`** — centralized configuration loaded from environment variables (`.env`).
- **`src/pipeline/`** — the core data pipeline: validation, rule-based alert detection, and doctor assignment logic.
- **`src/io/`** — persistence layer (MongoDB + CSV compatibility).
- **`src/services/`** — scheduler, AI messaging, and worker state management.
- **`workers/` / `worker_http.py` / `worker_mongo.py`** — standalone background polling processes.
- **`app.py`** — the doctor-facing Streamlit dashboard (queue, active cases, student detail views).
- **`student_signup.py`** — a separate Streamlit page for student registration and device linking.
- **`tools/`, `populate_*.py`, `src/scripts/`** — seeding, demo-reset, and migration utilities.

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend / dashboard | Streamlit, Altair |
| Backend / pipeline | Python, Pandas, NumPy |
| Data validation | Pydantic |
| Database | MongoDB (PyMongo) |
| Scheduling | APScheduler |
| AI messaging | Google Generative AI (Gemini) |
| Notifications | SMTP (smtplib) |
| Config | python-dotenv |

## 🚀 Getting Started

```bash
# 1. Clone and enter the project
git clone https://github.com/<your-username>/Smart+.git
cd Smart+

# 2. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# then fill in your own MongoDB URI, SMTP credentials, and Gemini API key

# 4. Seed demo data (optional)
python tools/reset_and_seed_demo.py

# 5. Run the ingestion worker (in one terminal)
python worker_mongo.py      # or worker_http.py

# 6. Launch the dashboard (in another terminal)
streamlit run app.py
```

## 🔒 Security Note

This repository ships **no real credentials**. `.env` is git-ignored — copy `.env.example` and provide your own MongoDB URI, SMTP credentials, and Gemini API key. Sample/demo data (`data/*.csv`) is also git-ignored since it can contain real student and health information generated during local testing; regenerate it locally with `tools/reset_and_seed_demo.py`.

## 📌 About

Built as a senior capstone project to demonstrate an end-to-end health-tech data pipeline: ingestion, validation, personalized anomaly detection, human-in-the-loop triage, and automated patient communication.
