# import json
# import os
# from datetime import datetime
# from typing import Dict, Any, Tuple

# try:
#     import google.generativeai as genai
# except Exception:
#     genai = None

# DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
# API_KEY = os.getenv("GEMINI_API_KEY")
# USE_TEMPLATE = os.getenv("USE_TEMPLATE_EMAIL", "true").lower() == "true"  # default to simple template

# UNITS = {
#     "heartRate": "bpm",
#     "oxygenSaturation": "%",
#     "respiratoryRate": "brpm",
#     "bodyTemperature": "°C",
#     "bloodPressureSystolic": "mmHg",
#     "bloodPressureDiastolic": "mmHg",
# }

# # ---------- NEW: sanitize + friendly phrasing ----------

# _DASHES = ["\u2014", "\u2013", "\u2212"]  # em dash, en dash, minus
# def _sanitize(text: str) -> str:
#     for d in _DASHES:
#         text = text.replace(d, "-")
#     # strip any double spaces that might appear after replacements
#     return " ".join(text.split())

# def _metric_label(name: str) -> str:
#     return {
#         "heartRate": "heart rate",
#         "oxygenSaturation": "blood oxygen",
#         "respiratoryRate": "breathing rate",
#         "bodyTemperature": "wrist temperature",
#         "bloodPressureSystolic": "blood pressure",
#         "bloodPressureDiastolic": "blood pressure",
#     }.get(name, name.replace("_", " "))

# def _as_intish(v):
#     try:
#         return int(round(float(v)))
#     except Exception:
#         return v

# def _friendly_metric_phrase(m: Dict[str, Any]) -> str:
#     name = m.get("name")
#     value = m.get("value")
#     unit = m.get("unit", UNITS.get(name, ""))
#     v = _as_intish(value)
#     if name == "heartRate":
#         return f"your heart rate was around {v} beats per minute"
#     if name == "oxygenSaturation":
#         return f"your blood oxygen was about {v}%"
#     if name == "respiratoryRate":
#         return f"your breathing rate was about {v} breaths per minute"
#     if name == "bodyTemperature":
#         return f"your wrist temperature was about {v} °C"
#     if name in ("bloodPressureSystolic", "bloodPressureDiastolic"):
#         # If only one is present, still print nicely
#         return f"your blood pressure reading was about {v} {unit}".strip()
#     # fallback
#     label = _metric_label(name or "reading")
#     return f"{label} was about {v}{unit}".strip()

# def _build_simple_email(payload: Dict[str, Any]) -> Tuple[str, str]:
#     # Never output em/en dashes; keep it plain and warm.
#     def _sanitize(text: str) -> str:
#         for d in ["\u2014", "\u2013", "\u2212"]:
#             text = text.replace(d, "-")
#         return " ".join(text.split())

#     def _as_intish(v):
#         try:
#             return int(round(float(v)))
#         except Exception:
#             return v

#     # Friendly phrasing for the first metric (avoid raw keys and "vs baseline")
#     def _friendly_metric_phrase(m: Dict[str, Any]) -> str:
#         name = (m or {}).get("name")
#         value = _as_intish((m or {}).get("value"))
#         if name == "heartRate":
#             return f"your heart rate was around {value} beats per minute"
#         if name == "oxygenSaturation":
#             return f"your blood oxygen was about {value}%"
#         if name == "respiratoryRate":
#             return f"your breathing rate was about {value} breaths per minute"
#         if name == "bodyTemperature":
#             return f"your wrist temperature was about {value} °C"
#         return "we noticed a reading worth a quick check"

#     sname = payload.get("student", {}).get("name", "Student")
#     dname = payload.get("doctor", {}).get("name", "Campus Doctor")
#     reason = payload.get("alert", {}).get("reason") or "a reading that needs a quick in-person check"
#     metrics = payload.get("alert", {}).get("metrics") or []
#     phrase = _friendly_metric_phrase(metrics[0]) if metrics else "we noticed a reading worth a quick check"

#     steps = payload.get("next_steps") or [
#         "Please come to the campus clinic today after class.",
#         "Bring your student ID.",
#     ]

#     subject = f"Please visit the campus clinic today"
#     body = (
#         f"Hello {sname},\n\n"
#         f"A campus doctor reviewed your recent reading from class. We noticed {reason.lower()}. "
#         f"To be safe, {phrase}. The doctor would like to see you in person.\n\n"
#         f"Next steps:\n- " + "\n- ".join(steps) + "\n\n"
#         f"If you feel unwell before you arrive, tell your professor or seek immediate help.\n\n"
#         f"{dname}"
#     )
#     return _sanitize(subject), _sanitize(body)


# # ---------- existing helpers (keep as-is or already present) ----------

# def _strip_fences(text: str) -> str:
#     t = text.strip()
#     if t.startswith("```"):
#         t = t.strip("`")
#         first_nl = t.find("\n")
#         if first_nl != -1:
#             t = t[first_nl+1:]
#     return t.strip()

# PROMPT = """You write short, student-facing emails approved by a campus doctor.
# Rules:
# - Keep it simple and friendly. No medical diagnoses or probabilities.
# - Do not use em dashes or en dashes. Use plain hyphens or commas.
# - Do not say "vs baseline". Use natural phrases like "higher than usual" if needed.
# - Refer to metrics in plain language (e.g., "heart rate", "blood oxygen"), not raw keys like "heartRate".
# - 70–120 words. Plain language.
# Return STRICT JSON with keys: "subject", "body_text".
# """

# def build_ai_payload(row: Dict[str, Any], doctor_name: str) -> Dict[str, Any]:
#     # (keep your existing implementation)
#     # ... your current code ...
#     pass  # remove this 'pass' if you already have build_ai_payload defined above

# def generate_student_message(payload: Dict[str, Any]) -> Tuple[str, str]:
#     """Prefer simple template by default; optionally use Gemini, but sanitize output and avoid em dashes."""
#     # Always allow forcing the simple template
#     if USE_TEMPLATE:
#         return _build_simple_email(payload)

#     # If AI package/key missing, template
#     if not (genai and API_KEY):
#         return _build_simple_email(payload)

#     # Call Gemini
#     try:
#         genai.configure(api_key=API_KEY)
#         model = genai.GenerativeModel(DEFAULT_MODEL)
#         prompt = f"{PROMPT}\n\nInput payload JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\nOutput:"
#         resp = model.generate_content(prompt)
#         text = (resp.text or "").strip()
#         text = _strip_fences(text)
#         data = json.loads(text)
#         subject = str(data.get("subject", "")).strip()
#         body = str(data.get("body_text", "")).strip()

#         # Sanitize and guard against unwanted patterns
#         subject = _sanitize(subject)
#         body = _sanitize(body)
#         # Avoid raw keys (e.g., heartRate: 120bpm) → if we see the pattern, rebuild with template
#         if "heartRate:" in body or "vs baseline" in body or "vs baseline" in body:
#             return _build_simple_email(payload)
#         if not subject or not body or len(body) < 40 or len(body) > 800:
#             return _build_simple_email(payload)
#         return subject, body
#     except Exception:
#         return _build_simple_email(payload)


import json
import os
from datetime import datetime
from typing import Dict, Any, Tuple

try:
    import google.generativeai as genai
except Exception:
    genai = None

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
API_KEY = os.getenv("GEMINI_API_KEY")
USE_TEMPLATE = os.getenv("USE_TEMPLATE_EMAIL", "true").lower() == "true"
LOGO_URL="https://www.psu.edu.sa/articles/2020/11/23/psu-logo_1606115014.png"

UNITS = {
    "heartRate": "bpm",
    "oxygenSaturation": "%",
    "respiratoryRate": "brpm",
    "bodyTemperature": "°C",
    "bloodPressureSystolic": "mmHg",
    "bloodPressureDiastolic": "mmHg",
}

# ---------- Sanitization & Formatting ----------

_DASHES = ["\u2014", "\u2013", "\u2212"]

def _sanitize(text: str) -> str:
    for d in _DASHES:
        text = text.replace(d, "-")
    return " ".join(text.split())

def _metric_label(name: str) -> str:
    return {
        "heartRate": "Heart Rate",
        "oxygenSaturation": "Blood Oxygen",
        "respiratoryRate": "Breathing Rate",
        "bodyTemperature": "Wrist Temperature",
        "bloodPressureSystolic": "Blood Pressure (Systolic)",
        "bloodPressureDiastolic": "Blood Pressure (Diastolic)",
    }.get(name, name.replace("_", " ").title())

def _as_intish(v):
    try:
        return int(round(float(v)))
    except Exception:
        return v

def _format_metric_row(m: Dict[str, Any]) -> str:
    """Format a single metric as HTML table row"""
    name = m.get("name", "")
    value = _as_intish(m.get("value", ""))
    unit = m.get("unit", UNITS.get(name, ""))
    baseline = m.get("baseline_median")
    
    label = _metric_label(name)
    value_str = f"{value} {unit}".strip()
    
    baseline_str = ""
    if baseline:
        baseline_str = f"<span style='color: #666; font-size: 13px;'>(Normal: {_as_intish(baseline)} {unit})</span>"
    
    return f"""
        <tr>
            <td style='padding: 12px 16px; border-bottom: 1px solid #eee;'>
                <strong style='color: #2c3e50;'>{label}</strong>
            </td>
            <td style='padding: 12px 16px; border-bottom: 1px solid #eee; text-align: right;'>
                <span style='color: #e74c3c; font-size: 18px; font-weight: 600;'>{value_str}</span>
                {baseline_str}
            </td>
        </tr>
    """

# ---------- HTML Email Template ----------

def _build_html_email(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    """Build styled HTML email with branding"""
    
    sname = payload.get("student", {}).get("name", "Student")
    dname = payload.get("doctor", {}).get("name", "Campus Doctor")
    reason = payload.get("alert", {}).get("reason") or "a reading that needs attention"
    severity = payload.get("alert", {}).get("severity", "moderate").title()
    metrics = payload.get("alert", {}).get("metrics") or []
    timestamp = payload.get("alert", {}).get("created_at", datetime.now().isoformat())
    
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        formatted_time = dt.strftime("%B %d, %Y at %I:%M %p")
    except:
        formatted_time = "recently"
    
    steps = payload.get("next_steps") or [
        "Visit the campus clinic today after class",
        "Bring your student ID and health card",
        "Call ahead if you have questions: (555) 123-4567"
    ]
    
    # Build metrics table
    metrics_html = ""
    if metrics:
        rows = "".join(_format_metric_row(m) for m in metrics)
        metrics_html = f"""
        <div style='margin: 24px 0;'>
            <h3 style='color: #2c3e50; margin-bottom: 16px;'>Your Recent Readings</h3>
            <table style='width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
                {rows}
            </table>
            <p style='color: #7f8c8d; font-size: 13px; margin-top: 8px; font-style: italic;'>
                Recorded: {formatted_time}
            </p>
        </div>
        """
    
    # Build next steps list
    steps_html = "".join(f"<li style='margin: 8px 0; color: #2c3e50;'>{step}</li>" for step in steps)
    
    # Severity badge color
    severity_color = {
        "Critical": "#c0392b",
        "High": "#e74c3c",
        "Moderate": "#f39c12",
        "Low": "#3498db"
    }.get(severity, "#95a5a6")
    
    subject = f"Campus Health Alert - Please Visit Clinic Today"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style='margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background-color: #f5f7fa;'>
        <div style='max-width: 600px; margin: 0 auto; background: white;'>
            <!-- Header with logo background -->
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 32px; text-align: center; position: relative;'>
                <div style='background: rgba(255,255,255,0.15); padding: 16px; border-radius: 12px; display: inline-block;'>
                    <img src='{LOGO_URL}' alt='Campus Health' style='max-width: 200px; height: auto;'>
                </div>
                <h1 style='color: white; margin: 20px 0 0 0; font-size: 24px; font-weight: 600;'>Health Alert</h1>
            </div>
            
            <!-- Main content -->
            <div style='padding: 32px;'>
                <!-- Severity badge -->
                <div style='margin-bottom: 24px;'>
                    <span style='background: {severity_color}; color: white; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>
                        {severity} Priority
                    </span>
                </div>
                
                <!-- Greeting -->
                <p style='font-size: 16px; color: #2c3e50; line-height: 1.6; margin: 0 0 16px 0;'>
                    Hello <strong>{sname}</strong>,
                </p>
                
                <p style='font-size: 16px; color: #2c3e50; line-height: 1.6; margin: 0 0 16px 0;'>
                    A campus doctor has reviewed your recent health monitoring data and noticed <strong>{reason.lower()}</strong>. 
                    As a precaution, we'd like you to come in for a quick in-person check.
                </p>
                
                {metrics_html}
                
                <!-- Next steps -->
                <div style='background: #f8f9fa; padding: 24px; border-radius: 8px; border-left: 4px solid #667eea; margin: 24px 0;'>
                    <h3 style='color: #2c3e50; margin: 0 0 16px 0;'>What to do next:</h3>
                    <ul style='margin: 0; padding-left: 24px;'>
                        {steps_html}
                    </ul>
                </div>
                
                <!-- Important notice -->
                <div style='background: #fff3cd; border: 1px solid #ffc107; padding: 16px; border-radius: 8px; margin: 24px 0;'>
                    <p style='margin: 0; color: #856404; font-size: 14px;'>
                        <strong>⚠️ Important:</strong> If you feel unwell or experience any concerning symptoms before your visit, 
                        please tell your professor or seek immediate medical help.
                    </p>
                </div>
                
                <!-- Footer signature -->
                <div style='margin-top: 32px; padding-top: 24px; border-top: 1px solid #ecf0f1;'>
                    <p style='color: #2c3e50; margin: 0 0 8px 0;'>Take care,</p>
                    <p style='color: #667eea; font-weight: 600; margin: 0;'>{dname}</p>
                    <p style='color: #7f8c8d; font-size: 13px; margin: 8px 0 0 0;'>Campus Health Services</p>
                </div>
            </div>
            
            <!-- Footer -->
            <div style='background: #2c3e50; padding: 24px 32px; text-align: center;'>
                <p style='color: #95a5a6; font-size: 12px; margin: 0 0 8px 0;'>
                    This is an automated health alert from your campus health monitoring system.
                </p>
                <p style='color: #95a5a6; font-size: 12px; margin: 0;'>
                    Campus Health Services | health@campus.edu | (555) 123-4567
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version for email clients that don't support HTML
    text_body = f"""
Hello {sname},

A campus doctor has reviewed your recent health monitoring data and noticed {reason.lower()}.

YOUR RECENT READINGS ({formatted_time}):
{chr(10).join(f"- {_metric_label(m.get('name', ''))}: {_as_intish(m.get('value', ''))} {m.get('unit', UNITS.get(m.get('name', ''), ''))}" for m in metrics)}

WHAT TO DO NEXT:
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(steps))}

IMPORTANT: If you feel unwell before your visit, tell your professor or seek immediate medical help.

Take care,
{dname}
Campus Health Services

---
This is an automated health alert from your campus health monitoring system.
Campus Health Services | health@campus.edu | (555) 123-4567
    """
    
    return _sanitize(subject), html_body, text_body.strip()


# ---------- Existing helpers ----------

def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl+1:]
    return t.strip()


def build_ai_payload(row: Dict[str, Any], doctor_name: str) -> Dict[str, Any]:
    """Build the payload structure for AI message generation"""
    student_info = {
        "name": row.get("name", "Student"),
        "age": row.get("age"),
        "gender": row.get("gender")
    }
    
    alert_info = {
        "reason": row.get("reason", "a reading that needs attention"),
        "severity": row.get("severity", "moderate"),
        "created_at": row.get("created_at", datetime.now().isoformat()),
        "metrics": []
    }
    
    # Extract metrics from the row
    metric_fields = ["heartRate", "oxygenSaturation", "respiratoryRate", 
                     "bodyTemperature", "bloodPressureSystolic", "bloodPressureDiastolic"]
    
    for field in metric_fields:
        if field in row and row[field] is not None:
            metric = {
                "name": field,
                "value": row[field],
                "unit": UNITS.get(field, "")
            }
            # Add baseline if available
            baseline_key = f"{field}_baseline_median"
            if baseline_key in row:
                metric["baseline_median"] = row[baseline_key]
            
            alert_info["metrics"].append(metric)
    
    return {
        "student": student_info,
        "doctor": {"name": doctor_name},
        "alert": alert_info,
        "next_steps": [
            "Visit the campus clinic today after class",
            "Bring your student ID and health card",
            "Call ahead if you have questions: (555) 123-4567"
        ]
    }


def generate_student_message(payload: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Generate student notification email.
    Returns: (subject, html_body, text_body)
    """
    # For now, always use the enhanced HTML template
    # You can add AI generation logic here later if needed
    return _build_html_email(payload)


# Example usage
if __name__ == "__main__":
    sample_payload = {
        "student": {"name": "Alex Johnson"},
        "doctor": {"name": "Dr. Sarah Mitchell"},
        "alert": {
            "reason": "elevated heart rate",
            "severity": "moderate",
            "created_at": "2025-11-20T14:30:00Z",
            "metrics": [
                {"name": "heartRate", "value": 125, "unit": "bpm", "baseline_median": 75},
                {"name": "oxygenSaturation", "value": 88, "unit": "%", "baseline_median": 97}
            ]
        },
        "next_steps": [
            "Visit the campus clinic today after class",
            "Bring your student ID and health card",
            "Call ahead if you have questions: (555) 123-4567"
        ]
    }
    
    subject, html, text = generate_student_message(sample_payload)
    print("SUBJECT:", subject)
    print("\nHTML VERSION:")
    print(html)
    print("\nTEXT VERSION:")
    print(text)