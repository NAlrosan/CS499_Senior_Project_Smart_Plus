import streamlit as st
from datetime import date

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))

import db_students

st.set_page_config(page_title="Student Registration", layout="centered")

st.title("Student Registration")

st.markdown(
    "Fill this form to register a student and link their **device ID** "
    "so incoming health data can be mapped to them."
)

with st.form("student_signup"):
    name = st.text_input("Full name")
    email = st.text_input("Email")
    gender = st.selectbox("Gender", ["Male", "Female"])
    dob = st.date_input("Date of birth", value=date(2005, 1, 1))
    device = st.text_input("Device ID (exactly as seen in health_data.device)")

    submitted = st.form_submit_button("Register student")

if submitted:
    if not name or not email or not device:
        st.error("Name, email, and device ID are required.")
    else:
        female = (gender == "Female")
        doc = db_students.create_student(
            name=name,
            email=email,
            female=female,
            dob=dob.isoformat(),
            device_id=device,
        )
        st.success(f"Registered student {doc['name']} ✅")
        st.write("Saved document:")
        st.code(doc, language="python")
