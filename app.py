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

#SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
#SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://trcxukrdgbvtkikeetun.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRyY3h1a3JkZ2J2dGtpa2VldHVuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk4MTk1NzksImV4cCI6MjA3NTM5NTU3OX0.KaS5aOHnyiOL2C1-Gy23ZsyQ1U5oqb8r4oQ5T4jie3k")

st.set_page_config(page_title="LECO Permit to Work", page_icon="📝", layout="centered")

@st.cache_resource
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

supabase = get_client()


#st.subheader("📍 Location")
#loc = st_geolocation()  # prompts the browser for GPS permission
#if loc and "latitude" in loc and "longitude" in loc:
#    st.caption(f"Location captured: {loc['latitude']:.5f}, {loc['longitude']:.5f}")
#else:
#    st.warning("Click 'Allow' in the browser prompt to share your location.")

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



#st.set_page_config(page_title="Simple Form", page_icon="📝", layout="centered")
st.title("📝 LECO Permit to Work")

with st.form("wp_form", clear_on_submit=False):
    csc = st.text_input("Customer Service Center", placeholder="Negombo")
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
            # Upload photos first
            operated_urls = upload_files(operatedLbsPhotos, "operated_lbs")
            earthing_urls  = upload_files(earthingPointsPhotos, "earthing_points")

            # Build location field (None if user didn't allow)
#            gpsLoc = None
#            if loc and "latitude" in loc and "longitude" in loc:
#                gpsLoc = {"lat": loc["latitude"], "lon": loc["longitude"], "acc": loc.get("accuracy")}


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
                
#                "gpsLoc": gpsLoc,  # if your column is camelCase; see SQL below
                "operatedLbsPhotos": operated_urls,         # JSONB column
                "earthingPointsPhotos": earthing_urls,      # JSONB column
            }

            resp = supabase.table(TABLE_NAME).insert(row).execute()
            st.success("✅ Submitted successfully!")
            if resp.data:
                st.json(resp.data[0])
        except Exception as e:
            st.error(f"❌ Error saving to database: {e}")

st.markdown("---")
