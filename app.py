import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, inspect
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# -----------------------------
# DATABASE SETUP
# -----------------------------
engine = create_engine('sqlite:///cloudbase.db')

# Define column names
COLUMNS = [
    "Date", "Tasks", "DOS", "Status", "Audit_Status",
    "User_ID", "Comments", "Auditor_Comments",
    "Audit_Date", "Timestamp", "Time_Difference", "Source"
]

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def get_user_data(user):
    """Load a user's sheet from the database"""
    try:
        df = pd.read_sql(f"SELECT * FROM '{user}'", engine)
    except:
        df = pd.DataFrame(columns=COLUMNS)
    return df

def safe_user = user.replace(" ", "_").lower()
df.to_sql(safe_user, engine, if_exists="replace", index=False)

def get_all_data():
    """Combine all user sheets into a single DataFrame"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    all_data = []
    for t in tables:
        all_data.append(pd.read_sql(f"SELECT * FROM '{t}'", engine))
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame(columns=COLUMNS)

def calculate_time_diff(df):
    """Calculate Time Difference between consecutive Timestamp entries"""
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors='coerce')
    df["Time_Difference"] = df["Timestamp"].diff().fillna(pd.Timedelta(seconds=0))
    df["Time_Difference"] = df["Time_Difference"].apply(lambda x: str(x))
    return df

def clean_user_name(name):
    """Standardize user names to avoid duplicates"""
    return name.strip().lower()

# -----------------------------
# STREAMLIT APP
# -----------------------------
st.set_page_config(page_title="Cloud-Based Tracker", layout="wide")
st.title("☁️ Cloud-Based Productivity & Audit Tracker")

# -----------------------------
# USER SHEET SECTION
# -----------------------------
user_input = st.text_input("👤 Enter your name (this will be your personal sheet):")
if user_input:
    user = clean_user_name(user_input)
    st.subheader(f"📄 Sheet for {user}")

    df = get_user_data(user)

    # Auto fill empty Date / Timestamp
    now = datetime.now()
    if df.empty:
        df = pd.DataFrame(columns=COLUMNS)

    # Editable grid
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=True, resizable=True)
    gb.configure_grid_options(enableRangeSelection=True)
    gb.configure_selection('multiple', use_checkbox=True)
    grid_options = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        theme="alpine"
    )

    updated_df = grid_response['data']

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Changes"):
            now = datetime.now()
            # Auto-fill Date and Timestamp if missing
            updated_df["Date"] = updated_df["Date"].fillna(now.date())
            updated_df["Timestamp"] = updated_df["Timestamp"].fillna(now.isoformat())
            # Auto-fill Audit_Date if Audit_Status is True
            updated_df["Audit_Date"] = updated_df.apply(
                lambda row: now.date() if str(row.get("Audit_Status")).lower() == "true" else row.get("Audit_Date"),
                axis=1
            )
            updated_df["Source"] = user
            # Calculate Time Difference
            updated_df = calculate_time_diff(updated_df)
            save_user_data(user, updated_df)
            st.success("✅ Data saved successfully!")

    with col2:
        if st.button("➕ Add New Row"):
            new_row = pd.DataFrame([{col: "" for col in COLUMNS}])
            updated_df = pd.concat([updated_df, new_row], ignore_index=True)
            save_user_data(user, updated_df)
            st.experimental_rerun()

    st.markdown("### 📊 Your Current Data")
    st.dataframe(updated_df, use_container_width=True)

    # Combined view
    st.markdown("---")
    if st.button("📈 View Combined Data (All Users)"):
        combined_df = get_all_data()
        combined_df = calculate_time_diff(combined_df)
        st.dataframe(combined_df, use_container_width=True)

# -----------------------------
# ADMIN / CLEANUP PANEL
# -----------------------------
st.markdown("---")
st.subheader("🛠️ Admin / Cleanup Tool")

inspector = inspect(engine)
tables = inspector.get_table_names()
if tables:
    st.write("Existing user sheets:", tables)

    sheet_to_delete = st.selectbox("Select a sheet to delete", [""] + tables)
    confirm_delete = st.checkbox(f"Confirm delete '{sheet_to_delete}'")

    if sheet_to_delete and confirm_delete:
        if st.button("⚠️ Permanently Delete Selected Sheet"):
            with engine.connect() as conn:
                conn.execute(f"DROP TABLE IF EXISTS '{sheet_to_delete}'")
            st.success(f"✅ '{sheet_to_delete}' deleted successfully!")
            st.experimental_rerun()
else:
    st.info("No user sheets found in the database.")

