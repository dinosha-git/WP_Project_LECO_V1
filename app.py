import os
import re
import streamlit as st
from supabase import create_client, Client

import os, streamlit as st
from dotenv import load_dotenv
load_dotenv()

#SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
#SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://trcxukrdgbvtkikeetun.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyY3h1a3JkZ2J2dGtpa2VldHVuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk4MTk1NzksImV4cCI6MjA3NTM5NTU3OX0.KaS5aOHnyiOL2C1-Gy23ZsyQ1U5oqb8r4oQ5T4jie3k")

st.set_page_config(page_title="Simple Form", page_icon="📝", layout="centered")

@st.cache_resource
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

supabase = get_client()

#st.set_page_config(page_title="Simple Form", page_icon="📝", layout="centered")
st.title("📝 LECO Permit to Work")

with st.form("wp_form", clear_on_submit=False):
    csc = st.text_input("Customer Service Center", placeholder="Negombo")
    technicalOfficer = st.text_input("Technical Officer", placeholder="TO Name")
    workScope = st.text_input("Work Scope", placeholder="Mention the Work Scope")
    operatedLbs = st.text_area("Operating LBSs", placeholder="Mention the Operating LBSs")
    earthingPoints = st.text_area("Earthing Points", placeholder="Mention the Earthing Points")
    additionalSafetySteps = st.text_area("Additional Safety Steps", placeholder="Mention any Additional Safety Steps")
    wpTransfer = st.checkbox("Can transfer this Permit to Work to another authorized person ", value=False)
    additionalEarthing = st.number_input("Number of Additional Earthing", min_value=0, max_value=120, step=1)
    cssName = st.text_input("Name of the Initiator", placeholder="Mention the CSS Name")
    submitted = st.form_submit_button("Submit")


TABLE_NAME = "wp_tbl"  

if submitted:
    # minimal required fields
    missing = []
    if not csc.strip():               missing.append("Customer Service Center")
    if not technicalOfficer.strip():  missing.append("Technical Officer")
    if not workScope.strip():         missing.append("Work Scope")
    if not cssName.strip():           missing.append("Name of the Initiator")

    if missing:
        st.error("Please fill: " + ", ".join(missing))
    else:
        try:
            row = {
                "csc": csc.strip(),
                "technicalOfficer": technicalOfficer.strip(),
                "workScope": workScope.strip(),
                "operatedLbs": operatedLbs.strip() if operatedLbs else None,
                "earthingPoints": earthingPoints.strip() if earthingPoints else None,
                "additionalSafetySteps": additionalSafetySteps.strip() if additionalSafetySteps else None,
                "wpTransfer": bool(wpTransfer),                               
                "additionalEarthing": int(additionalEarthing),                
                "cssName": cssName.strip(),
            }

            resp = supabase.table(TABLE_NAME).insert(row).execute()
            st.success("✅ Submitted successfully!")
            if resp.data:
                st.json(resp.data[0])
        except Exception as e:
            st.error(f"❌ Error saving to database: {e}")

st.markdown("---")
