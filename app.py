import os
import re
import streamlit as st
from supabase import create_client, Client
from uuid import uuid4
from datetime import datetime
#from streamlit_geolocation import st_geolocation

import os, streamlit as st
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or st.secrets["SUPABASE_ANON_KEY"]


st.set_page_config(page_title="LECO Permit to Work", page_icon="📝", layout="centered")

BG_URL = "https://images.pexels.com/photos/6803793/pexels-photo-6803793.jpeg"

st.markdown(
    f"""<style>
    .stApp {{
        background: url('{BG_URL}') no-repeat center center fixed;
        background-size: cover;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_resource
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

supabase = get_client()

BUCKET = "wp_bucket"

def upload_files(files, subfolder):
    """Upload Streamlit UploadedFile(s) to Supabase Storage and return public URL strings."""
    urls = []
    if not files:
        return urls

    date_prefix = datetime.utcnow().strftime("%Y/%m/%d")
    for f in files:
        ext = os.path.splitext(f.name)[1].lower() or ".bin"
        key = f"{subfolder}/{date_prefix}/{uuid4().hex}{ext}"

        data = f.read()
        f.seek(0)

        # IMPORTANT: make header values strings, not booleans
        supabase.storage.from_(BUCKET).upload(
            path=key,
            file=data,
            file_options={
                "contentType": f.type or "application/octet-stream",
                "upsert": "true"   # 👈 avoid bool→encode crash in headers
            },
        )

        # Get a plain string URL (supabase-py returns a dict)
        pub = supabase.storage.from_(BUCKET).get_public_url(key)
        if isinstance(pub, dict) and "data" in pub and "publicUrl" in pub["data"]:
            urls.append(pub["data"]["publicUrl"])
        else:
            urls.append(str(pub))
    return urls

TABLE_NAME = "wp_tbl"


st.title("📝 LECO Permit to Work")

st.subheader("**01. Issuing Clearance**")

CSC_OPTIONS = ["Negombo", "Kelaniya", "Kotte", "Nugegoda", "Moratuwa", "Kaluthara", "Galle"]

with st.form("wp_form", clear_on_submit=False):
    csc = st.selectbox("Customer Service Center", CSC_OPTIONS, index=0)
    technicalOfficer = st.text_input("Technical Officer", placeholder="TO Name")
    workScope = st.text_input("Work Scope", placeholder="Mention the Work Scope")
    operatedLbs = st.text_area("Operating LBSs", placeholder="Mention the Operating LBSs")
    operatedLbsPhotos = st.file_uploader(
        "Attach photos for Operating LBSs", type=["jpg","jpeg","png"], accept_multiple_files=True
    )
    earthingPoints = st.text_area("Earthing Points", placeholder="Mention the Earthing Points")
    earthingPointsPhotos = st.file_uploader(
        "Attach photos for Earthing Points", type=["jpg","jpeg","png"], accept_multiple_files=True
    )
    additionalSafetySteps = st.text_area("Additional Safety Steps", placeholder="Mention any Additional Safety Steps")
    wpTransfer = st.checkbox("Can transfer this Permit to Work to another authorized person ", value=False)
    additionalEarthing = st.number_input("Number of Additional Earthing", min_value=0, max_value=120, step=1)
    cssName = st.text_input("Name of the Initiator", placeholder="Mention the CSS Name")
    safetyConfirmation = st.checkbox("I hereby declare the isolated section is completely safe to access and carry out the operations by the relevant personnel and release this Permit to Work with the awareness of the Distribution Control Center...", value=False)
    submitted = st.form_submit_button("Submit")


if submitted:
    # Mandatory fields
    missing = []
    if not csc.strip():               missing.append("Customer Service Center")
    if not technicalOfficer.strip():  missing.append("Technical Officer")
    if not workScope.strip():         missing.append("Work Scope")
    if not cssName.strip():           missing.append("Name of the Initiator")

    if missing:
        st.error("Please fill: " + ", ".join(missing))
    else:
        try:
            operated_urls = upload_files(operatedLbsPhotos, "operated_lbs")
            earthing_urls  = upload_files(earthingPointsPhotos, "earthing_points")

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
                "operatedLbsPhotos": operated_urls,         
                "earthingPointsPhotos": earthing_urls,
                "safetyConfirmation" : bool(safetyConfirmation),     
            }

            resp = supabase.table(TABLE_NAME).insert(row).execute()
            st.success("✅ Submitted successfully!")
            if resp.data:
                st.json(resp.data[0])
        except Exception as e:
            st.error(f"❌ Error saving to database: {e}")




st.markdown("---")
