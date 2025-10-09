import os
from uuid import uuid4
from datetime import datetime

import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

# -------------------- ENV & CLIENT --------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or st.secrets["SUPABASE_ANON_KEY"]

# storage & tables (override via .env or st.secrets if needed)
BUCKET = os.getenv("SUPABASE_BUCKET", "wp_bucket")
TABLE_NAME = os.getenv("SUPABASE_TABLE", "wp_tbl")
PHOTOS_TABLE = os.getenv("SUPABASE_PHOTOS_TABLE", "photos")
BUCKET_IS_PUBLIC = (os.getenv("SUPABASE_BUCKET_PUBLIC", "true").lower() == "true")  # set to "false" for private bucket
SIGNED_URL_TTL = int(os.getenv("SUPABASE_SIGNED_TTL", "3600"))  # seconds

st.set_page_config(page_title="LECO Permit to Work", page_icon="📝", layout="centered")

@st.cache_resource
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

supabase = get_client()

# -------------------- HELPERS --------------------
def _normalize_public_url(ret):
    """Handle supabase-py v2 get_public_url return shapes."""
    if isinstance(ret, dict):
        # v2 typical shape: {"data": {"publicUrl": "..."}, "error": None}
        url = ret.get("data", {}).get("publicUrl")
        if url:
            return url
    return str(ret)

def _make_url(path: str) -> str:
    """Return a URL for the object, using public or signed URL based on config."""
    if BUCKET_IS_PUBLIC:
        return _normalize_public_url(supabase.storage.from_(BUCKET).get_public_url(path))
    else:
        signed = supabase.storage.from_(BUCKET).create_signed_url(path, expires_in=SIGNED_URL_TTL)
        # v2 returns {"data": {"signedUrl": "..."}} or {"signedURL": "..."} variants
        if isinstance(signed, dict):
            return signed.get("data", {}).get("signedUrl") or signed.get("signedURL") or signed.get("signedUrl") or ""
        return str(signed)

def upload_files(files, subfolder, max_mb=10):
    """
    Upload Streamlit UploadedFile(s) to Supabase Storage.
    Returns list[dict]: [{path, url, filename, mime_type, size_bytes, uploaded_at, id}]
    """
    results = []
    if not files:
        return results

    date_prefix = datetime.utcnow().strftime("%Y/%m/%d")

    for f in files:
        # --- validations ---
        raw = f.read()
        f.seek(0)
        size_mb = len(raw) / (1024 * 1024)
        if size_mb > max_mb:
            raise ValueError(f"File '{f.name}' is {size_mb:.1f} MB; max allowed is {max_mb} MB")

        mime = (f.type or "").lower()
        if not mime.startswith("image/"):
            raise ValueError(f"File '{f.name}' is not an image (MIME={mime})")

        # --- unique path with original extension ---
        ext = os.path.splitext(f.name)[1].lower() or ".bin"
        obj_id = uuid4().hex
        uploaded_at = datetime.utcnow()
        path = f"{subfolder}/{date_prefix}/{obj_id}{ext}"

        # --- upload ---
        supabase.storage.from_(BUCKET).upload(
            path=path,
            file=raw,
            file_options={
                "content-type": mime,  # header keys as strings for v2
                "upsert": "true"
            },
        )

        # --- url ---
        url = _make_url(path)

        results.append({
            "id": obj_id,
            "path": path,
            "url": url,
            "filename": f.name,
            "mime_type": mime,
            "size_bytes": len(raw),
            "uploaded_at": uploaded_at.isoformat() + "Z",
            "bucket": BUCKET,
        })
    return results

def insert_photo_metadata(items, extra=None):
    """
    Best-effort insert of photo metadata rows into PHOTOS_TABLE (optional).
    `extra` can include foreign keys or tags (e.g., {"source_table": "wp_tbl", "wp_row_id": "..."}).
    """
    if not items:
        return
    rows = []
    for it in items:
        row = {
            "id": it["id"],
            "file_path": it["path"],
            "bucket": it["bucket"],
            "filename": it["filename"],
            "mime_type": it["mime_type"],
            "size_bytes": it["size_bytes"],
            "url": it["url"],
            "uploaded_at": it["uploaded_at"],
        }
        if extra:
            row.update(extra)
        rows.append(row)
    try:
        supabase.table(PHOTOS_TABLE).insert(rows).execute()
    except Exception as e:
        # Don't fail the main flow if this auxiliary insert fails
        st.warning(f"Saved images, but could not write photo metadata: {e}")

# -------------------- UI --------------------
st.title("📝 LECO Permit to Work")

with st.form("wp_form", clear_on_submit=False):
    csc = st.text_input("Customer Service Center", placeholder="Negombo")
    technicalOfficer = st.text_input("Technical Officer", placeholder="TO Name")
    workScope = st.text_input("Work Scope", placeholder="Mention the Work Scope")

    operatedLbs = st.text_area("Operating LBSs", placeholder="Mention the Operating LBSs")
    operatedLbsPhotos = st.file_uploader(
        "Attach photos for Operating LBSs", type=["jpg","jpeg","png","webp"], accept_multiple_files=True
    )

    earthingPoints = st.text_area("Earthing Points", placeholder="Mention the Earthing Points")
    earthingPointsPhotos = st.file_uploader(
        "Attach photos for Earthing Points", type=["jpg","jpeg","png","webp"], accept_multiple_files=True
    )

    additionalSafetySteps = st.text_area("Additional Safety Steps", placeholder="Mention any Additional Safety Steps")
    wpTransfer = st.checkbox("Can transfer this Permit to Work to another authorized person", value=False)
    additionalEarthing = st.number_input("Number of Additional Earthing", min_value=0, max_value=120, step=1)
    cssName = st.text_input("Name of the Initiator", placeholder="Mention the CSS Name")

    submitted = st.form_submit_button("Submit")

# -------------------- SUBMIT HANDLER --------------------
if submitted:
    missing = []
    if not csc.strip():               missing.append("Customer Service Center")
    if not technicalOfficer.strip():  missing.append("Technical Officer")
    if not workScope.strip():         missing.append("Work Scope")
    if not cssName.strip():           missing.append("Name of the Initiator")

    if missing:
        st.error("Please fill: " + ", ".join(missing))
    else:
        try:
            # 1) Upload photos (validated, unique paths)
            operated_items = upload_files(operatedLbsPhotos, "operated_lbs")
            earthing_items  = upload_files(earthingPointsPhotos, "earthing_points")

            # 2) Insert main row into wp_tbl
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

                # store just the URLs in JSONB (as you had), but you now also have rich metadata in `operated_items` / `earthing_items`
                "operatedLbsPhotos": [it["url"] for it in operated_items],
                "earthingPointsPhotos": [it["url"] for it in earthing_items],
            }

            resp = supabase.table(TABLE_NAME).insert(row).execute()
            st.success("✅ Submitted successfully!")

            # 3) Best-effort: write detailed photo metadata rows to `photos` table
            wp_row_id = None
            if resp and getattr(resp, "data", None):
                # Try to capture the inserted row id if your table returns it
                wp_row_id = resp.data[0].get("id")
                st.json(resp.data[0])

            # Tag each photo with linkage back to this submission (if your `photos` table has these columns)
            extra = {"source_table": TABLE_NAME}
            if wp_row_id is not None:
                extra["wp_row_id"] = wp_row_id

            insert_photo_metadata(operated_items, extra=extra | {"category": "operated_lbs"})
            insert_photo_metadata(earthing_items, extra=extra | {"category": "earthing_points"})

            # 4) Preview uploaded images inline
            if operated_items:
                st.subheader("Operating LBS Photos")
                for it in operated_items:
                    st.image(it["url"], caption=it["filename"], use_column_width=True)
            if earthing_items:
                st.subheader("Earthing Points Photos")
                for it in earthing_items:
                    st.image(it["url"], caption=it["filename"], use_column_width=True)

        except Exception as e:
            st.error(f"❌ Error: {e}")

st.markdown("---")
st.caption("Tip: Set SUPABASE_BUCKET_PUBLIC=false to keep the bucket private and serve signed URLs.")
