
import os
import hmac
import hashlib
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

import streamlit as st

# ---------- APP SETTINGS ----------
st.set_page_config(
    page_title="SUNO | Campus Solutions",
    page_icon="📣",
    layout="wide",
)

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "suno.db"
UPLOAD_DIR = BASE_DIR / "uploads"
LOGO_PATH = BASE_DIR / "suno_logo.jpeg"

UPLOAD_DIR.mkdir(exist_ok=True)

CATEGORIES = [
    "Classroom & Infrastructure",
    "Cleanliness & Washrooms",
    "Water Supply",
    "Electricity & Lighting",
    "Wi-Fi & Internet",
    "Library",
    "Laboratory Equipment",
    "Canteen & Food",
    "Transport & Parking",
    "Sports Facilities",
    "Harassment or Safety",
    "Accessibility",
    "Other",
]

STATUSES = [
    "Submitted",
    "Under Review",
    "In Progress",
    "Resolved",
    "Rejected",
]

# ---------- DESIGN ----------

st.markdown("""
<style>
.stApp {
    background: #F4F8F7;
    color: #000000;
}
.stApp p,
.stApp span,
.stApp label,
.stApp li,
.stApp div[data-testid="stMarkdownContainer"] {
    color: #000000;
}
h1, h2, h3, h4, h5, h6 {
    color: #000000 !important;
}
[data-testid="stSidebar"] {
    background: #102D35;
}
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}
input, textarea {
    color: #000000 !important;
    background-color: #FFFFFF !important;
}
/* Upload photo button */
[data-testid="stFileUploader"] button {
    background-color: #1677FF !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
}

[data-testid="stFileUploader"] button:hover {
    background-color: #0056D6 !important;
    color: #FFFFFF !important;
}

</style>
""", unsafe_allow_html=True)



# ---------- DATABASE ----------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                complaint_id TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                location TEXT,
                description TEXT,
                status TEXT DEFAULT 'Submitted',
                created_at TEXT,
                photo_path TEXT DEFAULT ''
            )
        """)

        # Upgrade an older SUNO database safely.
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(complaints)"
            ).fetchall()
        }

        if "photo_path" not in columns:
            conn.execute("""
                ALTER TABLE complaints
                ADD COLUMN photo_path TEXT DEFAULT ''
            """)


def create_id():
    return "SUNO-" + uuid.uuid4().hex[:8].upper()


def get_complaints():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM complaints ORDER BY created_at DESC"
            ).fetchall()
        ]


def verify_staff(username, password):
    # Credentials are configured in .streamlit/secrets.toml.
    users = st.secrets.get("staff_users", {})
    user = users.get(username)

    if not user:
        return False

    entered_hash = hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()

    return hmac.compare_digest(
        entered_hash, user["password_hash"]
    )


init_db()

# ---------- HEADER ----------
left, right = st.columns([1, 5])

with left:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=115)
    else:
        st.markdown("# 📣")

with right:
    st.title("SUNO")
    st.caption("Your Campus. Your Voice. Our Solution.")
    st.write("Together, let's make our campus better.")
st.divider()

# ---------- NAVIGATION ----------
page = st.sidebar.radio(
    "NAVIGATION",
    [
        "Home",
        "Report a Problem",
        "Track Complaint",
        "Staff Login",
    ],
)

st.sidebar.divider()
st.sidebar.caption("Listen. Act. Resolve.")

# ---------- HOME ----------
if page == "Home":
    complaints = get_complaints()
    total = len(complaints)
    resolved = sum(
        c["status"] == "Resolved" for c in complaints
    )
    pending = sum(
        c["status"] in [
            "Submitted", "Under Review", "In Progress"
        ]
        for c in complaints
    )

    st.subheader("Your voice matters 💚")
    st.write(
        "Found a broken facility, a cleanliness issue, "
        "or another campus problem? Report it through SUNO "
        "and follow its progress."
    )

    a, b, c = st.columns(3)
    a.metric("Total Reports", total)
    b.metric("Awaiting Resolution", pending)
    c.metric("Resolved", resolved)

    st.info(
        "Choose **Report a Problem** in the sidebar "
        "to submit a complaint."
    )

# ---------- SUBMIT COMPLAINT ----------
elif page == "Report a Problem":
    st.header("📝 Report a Campus Problem")
    st.write("Tell us what happened. A photo is optional.")

    with st.form("report_form", clear_on_submit=True):
        name = st.text_input(
            "Your name (optional)",
            placeholder="Leave blank if you prefer not to provide it",
        )

        category = st.selectbox(
            "Complaint category", CATEGORIES
        )

        location = st.text_input(
            "Problem location *",
            placeholder="e.g. Block A, first-floor washroom",
        )

        description = st.text_area(
            "Describe the problem *",
            placeholder=(
                "What happened? When did you notice it? "
                "What needs to be fixed?"
            ),
        )

        photo = st.file_uploader(
            "Upload a photo (optional)",
            type=["jpg", "jpeg", "png"],
            help="Maximum 5 MB. Avoid faces or private information.",
        )

        consent = st.checkbox(
            "I have avoided including unnecessary personal "
            "or sensitive information in this report."
        )

        submit = st.form_submit_button(
            "Submit Complaint", type="primary"
        )

    if submit:
        if not location.strip() or not description.strip():
            st.error("Please complete the location and description.")
        elif not consent:
            st.warning("Please confirm the privacy statement.")
        elif photo and photo.size > 5 * 1024 * 1024:
            st.error("Please upload a photo smaller than 5 MB.")
        else:
            complaint_id = create_id()
            photo_path = ""

            if photo:
                extension = Path(photo.name).suffix.lower()
                safe_name = f"{complaint_id}{extension}"
                destination = UPLOAD_DIR / safe_name
                destination.write_bytes(photo.getvalue())
                photo_path = safe_name

            now = datetime.now().astimezone().isoformat(
                timespec="seconds"
            )

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO complaints (
                        complaint_id, name, category, location,
                        description, status, created_at, photo_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    complaint_id,
                    name.strip() or "Not provided",
                    category,
                    location.strip(),
                    description.strip(),
                    "Submitted",
                    now,
                    photo_path,
                ))

            st.success("Your complaint was submitted!")
            st.write("Save this complaint ID to track progress:")
            st.code(complaint_id)

# ---------- TRACK COMPLAINT ----------
elif page == "Track Complaint":
    st.header("🔎 Track Your Complaint")

    complaint_id = st.text_input(
        "Complaint ID",
        placeholder="SUNO-XXXXXXXX",
    )

    if st.button("Check Status", type="primary"):
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("""
                SELECT complaint_id, category, location,
                       status, created_at
                FROM complaints
                WHERE complaint_id = ?
            """, (complaint_id.strip().upper(),)).fetchone()

        if row:
            st.success(f"Current status: {row[3]}")
            st.write(f"**Category:** {row[1]}")
            st.write(f"**Location:** {row[2]}")
            st.write(f"**Submitted:** {row[4]}")
        else:
            st.error("Complaint not found. Check your ID.")

# ---------- STAFF LOGIN ----------
elif page == "Staff Login":
    st.header("🔐 Authorised Staff Portal")

    if not st.session_state.get("staff_logged_in", False):
        with st.form("staff_login"):
            username = st.text_input("Staff username")
            password = st.text_input(
                "Staff password", type="password"
            )
            login = st.form_submit_button(
                "Log In", type="primary"
            )

        if login:
            if verify_staff(username.strip(), password):
                st.session_state.staff_logged_in = True
                st.session_state.staff_username = username.strip()
                st.rerun()
            else:
                st.error("Invalid username or password.")

        st.caption("For authorised college staff only.")

    else:
        st.success(
            f"Logged in as {st.session_state.staff_username}"
        )

        if st.button("Log Out"):
            st.session_state.staff_logged_in = False
            st.session_state.pop("staff_username", None)
            st.rerun()

        complaints = get_complaints()
        st.subheader("Complaint Management")

        if not complaints:
            st.info("No complaints have been submitted yet.")

        for item in complaints:
            with st.expander(
                f"{item['complaint_id']} · {item['category']} · "
                f"{item['status']}"
            ):
                st.write("**Reporter:**", item["name"])
                st.write("**Location:**", item["location"])
                st.write("**Description:**", item["description"])
                st.write("**Submitted:**", item["created_at"])

                photo_path = item.get("photo_path", "")
                if photo_path:
                    image_file = UPLOAD_DIR / Path(photo_path).name
                    if image_file.is_file():
                        st.image(
                            str(image_file),
                            caption="Complaint evidence",
                            width=400,
                        )

                new_status = st.selectbox(
                    "Update status",
                    STATUSES,
                    index=STATUSES.index(item["status"]),
                    key=f"status_{item['complaint_id']}",
                )

                if st.button(
                    "Save Update",
                    key=f"save_{item['complaint_id']}",
                    type="primary",
                ):
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute("""
                            UPDATE complaints
                            SET status = ?
                            WHERE complaint_id = ?
                        """, (
                            new_status,
                            item["complaint_id"],
                        ))

                    st.success("Complaint status updated.")
                    st.rerun()
