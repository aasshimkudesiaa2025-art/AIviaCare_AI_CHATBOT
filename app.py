import streamlit as st
import pandas as pd
from openai import AzureOpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import pymongo
import certifi
from bson.objectid import ObjectId
import urllib.parse
from fpdf import FPDF  # Ensure you run: pip install fpdf

# --- 0. INITIALIZE ---
load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
    api_version="2024-02-15-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
deployment_name = "gpt-4.1"

# --- 1. DATABASE SETUP ---
MONGO_URI = os.getenv("MONGO_URI")  

@st.cache_resource
def init_connection():
    return pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())

try:
    client_db = init_connection()
    db = client_db["aiviacare_db"]
    sessions_col = db["clinical_sessions"]
except Exception as e:
    st.error(f"⚠️ Connection Error: {e}")

# --- 2. PDF GENERATION LOGIC ---
# --- UPDATED PDF GENERATION LOGIC ---
def generate_prescription_pdf(record):
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "AIviaCARE - CLINICAL PRESCRIPTION", ln=True, align='C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, f"Date: {record.get('timestamp').strftime('%d-%m-%Y %H:%M')}", ln=True, align='C')
    pdf.ln(10)
    
    # Patient Details
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Patient Information:", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Name: {record.get('name')}", ln=True)
    pdf.cell(0, 8, f"Age: {record.get('age')} years", ln=True)
    pdf.ln(5)
    
    # SOAP Section
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Clinical SOAP Notes:", ln=True)
    pdf.set_font("Arial", '', 11)
    # Sanitizing text for FPDF to avoid latin-1 encoding crashes
    subj = record.get('current_complaint', 'N/A').encode('latin-1', 'replace').decode('latin-1')
    bp = record.get('bp', 'N/A')
    sugar = record.get('sugar', 'N/A')
    
    soap_text = f"Subjective: {subj}\nObjective: BP {bp}, Sugar {sugar}\nAssessment: AI Guided Analysis\nPlan: See Medications"
    pdf.multi_cell(0, 8, soap_text)
    pdf.ln(5)
    
    # Medications / AI Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "AI Summary & Advice:", ln=True)
    pdf.set_font("Arial", '', 11)
    summary = record.get('summary', 'N/A').encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 8, summary)
    
    # THE FIX: Handle the output correctly based on FPDF version
    pdf_out = pdf.output(dest='S')
    
    # If output is already bytes (fpdf2), return as bytes
    if isinstance(pdf_out, (bytes, bytearray)):
        return bytes(pdf_out)
    
    # If output is a string (older fpdf), encode it
    return pdf_out.encode('latin-1')

# --- 3. DYNAMIC COLOR & THEME LOGIC ---
def apply_dynamic_theme():
    bg_color = "#FFFFFF"
    text_color = "#31333F"
    
    if st.session_state.get("emergency_mode"):
        bg_color = "#FF0000"
        text_color = "#FFFFFF"
    elif st.session_state.get("calm_mode"):
        bg_color = "#E0F2F1"  
        text_color = "#004D40"
            
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {bg_color} !important; color: {text_color} !important; transition: background-color 0.3s ease; }}
        [data-testid="stSidebar"] {{ background-color: #F0F2F6; }}
        .stMarkdown, p, span, label, h1, h2, h3 {{ color: {text_color} !important; }}
        </style>
    """, unsafe_allow_html=True)

# --- 4. LANGUAGE SUPPORT ---
LANG_DATA = {
    "English": {
        "consent_header": "📜 Digital Consent & Disclaimer",
        "consent_body": "I understand that Dr. Rishi is an AI assistant and NOT a replacement for a real doctor.",
        "consent_check": "I agree and understand the terms.",
        "intake_header": "🏥 Patient Intake Form",
        "symptoms_label": "Describe your symptoms",
        "btn_start": "Start Consultation",
        "chat_placeholder": "How can Dr. Rishi help you today?",
    },
    "Hindi (हिन्दी)": {
        "consent_header": "📜 डिजिटल सहमति और अस्वीकरण",
        "consent_body": "मैं समझता हूँ कि डॉ. ऋषि एक एआई सहायक हैं।",
        "consent_check": "मैं शर्तों को स्वीकार करता हूँ।",
        "intake_header": "🏥 रोगी जानकारी फॉर्म",
        "symptoms_label": "अपने लक्षणों का वर्णन करें",
        "btn_start": "परामर्श शुरू करें",
        "chat_placeholder": "डॉ. ऋषि आज आपकी कैसे मदद कर सकते हैं?",
    }
}

@st.dialog("📄 Clinical Perception", width="large")
def perception_modal(r):
    rec_id = str(r['_id'])
    st.subheader(f"Patient: {r.get('name', 'Unknown')}")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("BMI", r.get('bmi', 'N/A'))
    v2.metric("Sugar", f"{r.get('sugar', 'N/A')} mg/dL")
    v3.metric("BP", r.get('bp', 'N/A'))
    v4.metric("Age", f"{r.get('age', 'N/A')}")
    st.divider()
    if st.button("✨ Generate AI Patient Handoff", key=f"handoff_{rec_id}"):
        with st.spinner("Summarizing..."):
            prompt = f"Summarize this case for a medical handoff: {r.get('current_complaint')}"
            res = client.chat.completions.create(model=deployment_name, messages=[{"role":"user","content":prompt}])
            st.info(res.choices[0].message.content)
    if st.button("Close View", key=f"close_{rec_id}"): 
        st.rerun()

st.set_page_config(page_title="Dr. Rishi Saxena | AIviaCARE", layout="wide")
apply_dynamic_theme()

specialties = ["General Physician", "Cardiologist", "Dermatologist", "Psychiatrist", "Pediatrician", "Dietitian", "Endocrinologist"]

# --- SIDEBAR ---
with st.sidebar:
    st.title("👨‍⚕️ Dr. Rishi Saxena")
    lang_choice = st.radio("🌐 Language / भाषा चुनें", ["English", "Hindi (हिन्दी)"])
    L = LANG_DATA[lang_choice]
    st.divider()
    st.session_state.calm_mode = st.toggle("🌿 Healthy Calm Mode", value=False)
    
    portal = st.selectbox("Navigation", ["Patient Portal", "Doctor Dashboard"])
    active_specialty = st.selectbox("Switch AI Specialty", specialties)
    
    if st.button("🔄 Reset / Normal Mode", key="sidebar_reset_btn"):
        st.session_state.emergency_mode = False
        st.session_state.clear()
        st.rerun()

# --- 5. PORTAL LOGIC ---
if portal == "Patient Portal":
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # EMERGENCY SECTION
    st.markdown("""
        <div style="background-color: #b91d1d; padding: 15px; border-radius: 10px; text-align: center; border: 2px solid white;">
            <h2 style="color: white !important; margin: 0;">🚨 EMERGENCY ASSISTANCE 🚨</h2>
            <p style="color: white !important; font-size: 20px; font-weight: bold; margin: 5px;">Ambulance: 102 | Emergency: 112</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([3, 3, 4])
    with col1:
        if st.button("🚑 Call Ambulance", type="primary", use_container_width=True):
            st.session_state.emergency_mode = True
            st.markdown('<meta http-equiv="refresh" content="0; url=tel:102">', unsafe_allow_html=True)
            st.rerun()
    with col2:
        if st.button("🏥 Nearby Hospitals", use_container_width=True):
            st.session_state.emergency_mode = True
            st.markdown('<meta http-equiv="refresh" content="0; url=http://google.com/maps/search/hospitals+near+me">', unsafe_allow_html=True)
            st.rerun()
    with col3:
        p_info = st.session_state.get('p_info', {})
        e_name = p_info.get('e_name', 'Emergency Contact')
        e_phone = p_info.get('e_phone', '')
        
        if e_phone:
            loc_msg = urllib.parse.quote(f"EMERGENCY! {p_info.get('name')} needs help. Contact Name: {e_name}. Location: http://maps.google.com/maps?q=my+location")
            st.link_button(f"📲 Send Location to {e_name}", f"sms:{e_phone}?body={loc_msg}", use_container_width=True)
        else:
            st.button("📲 Send Location (Fill Form Below)", disabled=True, use_container_width=True)

    st.title(f"👨‍⚕️ Consulting: {active_specialty}")

    if "consent_signed" not in st.session_state:
        st.subheader(L['consent_header'])
        with st.container(border=True):
            st.write(L['consent_body'])
            agree = st.checkbox(L['consent_check'])
            if st.button("Proceed") and agree:
                st.session_state.consent_signed = True
                st.rerun()

    elif "p_info" not in st.session_state:
        with st.form("intake_form"):
            st.subheader(L['intake_header'])
            
            c_p1, c_p2, c_p3 = st.columns(3)
            name = c_p1.text_input("Patient Full Name")
            age = c_p2.number_input("Age", min_value=0, max_value=120, value=25) # ADDED AGE
            p_phone = c_p3.text_input("Patient Phone Number")
            
            st.markdown("---")
            st.info("🚑 **Emergency Contact Information**")
            ce1, ce2, ce3 = st.columns(3)
            e_name = ce1.text_input("Contact Person Name")
            e_phone = ce2.text_input("Contact Phone Number")
            e_relation = ce3.text_input("Relation")
            st.markdown("---")
            
            c3, c4 = st.columns(2)
            weight = c3.number_input("Weight (kg)", 1.0, 300.0, 70.0)
            height = c4.number_input("Height (cm)", 50.0, 250.0, 170.0)
            sugar = c3.number_input("Sugar (mg/dL)", 40, 500, 100)
            bp = c4.text_input("BP (e.g. 120/80)", "120/80")
            
            meds = st.text_area("Current Medications")
            surgeries = st.text_area("Past Medical History")
            allergies = st.text_input("Known Allergies")
            
            if st.form_submit_button(L['btn_start']):
                st.session_state.p_info = {
                    "name": name, "age": age, "phone": p_phone,
                    "e_name": e_name, "e_phone": e_phone, "e_relation": e_relation,
                    "bmi": round(weight / ((height/100)**2), 1),
                    "sugar": sugar, "bp": bp, "med_history": meds,
                    "surgeries": surgeries, "allergies": allergies,
                    "specialty": active_specialty, "language": lang_choice
                }
                st.rerun()

    else:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input(L['chat_placeholder']):
            st.chat_message("user").markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

            with st.chat_message("assistant"):
                with st.spinner("Dr. Rishi is analyzing..."):
                    p = st.session_state.p_info
                    system_prompt = (
                        f"You are Dr. Rishi, an expert {active_specialty}. "
                        f"Patient Context: Name: {p['name']}, Age: {p['age']}, BMI: {p['bmi']}, "
                        f"Sugar: {p['sugar']}, BP: {p['bp']}, History: {p['med_history']}. "
                        "Provide professional guidance."
                    )
                    
                    try:
                        response = client.chat.completions.create(
                            model=deployment_name,
                            messages=[{"role": "system", "content": system_prompt}] + st.session_state.messages
                        )
                        answer = response.choices[0].message.content
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})

                        sessions_col.insert_one({
                            **st.session_state.p_info,
                            "current_complaint": prompt,
                            "summary": answer,
                            "timestamp": datetime.now()
                        })
                    except Exception as e:
                        st.error(f"Chat Error: {e}")

# --- 6. DOCTOR DASHBOARD ---
# --- 6. DOCTOR DASHBOARD ---
else:
    st.title("👨‍⚕️ Doctor Dashboard")
    try:
        all_recs = list(sessions_col.find().sort("timestamp", -1))
        
        if not all_recs:
            st.info("No clinical sessions found.")
        else:
            tab_all, tab_cardio, tab_derma, tab_psych = st.tabs(["All Cases", "Cardiology", "Dermatology", "Psychiatry"])

            def render_list(data, tag):
                st.markdown(f"### 🏥 Patient Waiting Room ({tag.title()})")
                if not data:
                    st.write("No cases in this department.")
                    return

                for r in data:
                    rec_id = str(r['_id'])
                    with st.expander(f"📋 {r.get('name', 'Unknown')} (Age: {r.get('age', 'N/A')}) - {r.get('timestamp').strftime('%H:%M')}"):
                        
                        # SOAP Section
                        st.markdown("### 📝 SOAP Notes")
                        col_s1, col_s2 = st.columns(2)
                        with col_s1:
                            st.write("**Subjective (Complaint):**")
                            st.info(r.get('current_complaint', 'No complaint recorded.'))
                        with col_s2:
                            st.write("**Objective (Vitals):**")
                            st.write(f"- **BP:** {r.get('bp', 'N/A')}")
                            st.write(f"- **Sugar:** {r.get('sugar', 'N/A')} mg/dL")
                            st.write(f"- **BMI:** {r.get('bmi', 'N/A')}")

                        st.markdown("### ✨ AI Clinical Summary")
                        st.success(r.get('summary', 'Summary not available.'))
                        
                        st.divider()
                        b1, b2, b3 = st.columns([1, 1, 1])
                        
                        if b1.button("👁️ Full Profile", key=f"v_{tag}_{rec_id}"):
                            perception_modal(r)
                        
                        # --- CORRECTED DOWNLOAD SECTION ---
                        try:
                            # 1. Generate bytes directly
                            pdf_data = generate_prescription_pdf(r) 
                            
                            # 2. Pass to button. DO NOT call .encode() here!
                            b2.download_button(
                                label="📄 Download Rx",
                                data=pdf_data,
                                file_name=f"Prescription_{r.get('name')}.pdf",
                                mime="application/pdf",
                                key=f"p_{tag}_{rec_id}"
                            )
                        except Exception as pdf_err:
                            b2.error(f"PDF Error: {pdf_err}")
                            
                        with b3.popover("🗑️ Archive Case"):
                            if st.button("Confirm Delete", key=f"d_{tag}_{rec_id}"):
                                sessions_col.delete_one({"_id": ObjectId(rec_id)})
                                st.rerun()

            # Assign data to tabs
            with tab_all: render_list(all_recs, "all")
            with tab_cardio: render_list([r for r in all_recs if r.get('specialty') == 'Cardiologist'], "cardio")
            with tab_derma: render_list([r for r in all_recs if r.get('specialty') == 'Dermatologist'], "derma")
            with tab_psych: render_list([r for r in all_recs if r.get('specialty') == 'Psychiatrist'], "psych")

    except Exception as e:
        # This catch is what you see in the screenshot. 
        # By fixing the .encode() error inside render_list, this will go away.
        st.error(f"Dashboard Error: {e}")