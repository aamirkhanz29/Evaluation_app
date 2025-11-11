import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, inspect
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import io

# -----------------------------
# DATABASE SETUP
# -----------------------------
engine = create_engine('sqlite:///cloudbase.db')

# Define columns
COLUMNS = [
    "Date", "Tasks", "DOS", "Status", "Audit_Status",
    "User_ID", "Comments", "Auditor_Comments",
    "Audit_Date", "Timestamp", "Time_Difference", "Source"
]

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def get_user_data(user):
    """Load user's sheet from the database"""
    try:
        df = pd.read_sql(f"SELECT * FROM '{user}'", engine)
    except:
        df = pd.DataFrame(columns=COLUMNS)
    return df

def save_user_data(user, df):
    """Save user's data back to the database"""
    df.to_sql(user, engine, if_exists="replace", index=False)

def get_all_data():
    """Combine all sheets"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    all_data = []
    for t in tables:
        try:
            df = pd.read_sql(f"SELECT * FROM '{t}'", engine)
            df["Source_Sheet"] = t
            all_data.append(df)
        except:
            continue
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame(columns=COLUMNS)

def calculate_time_diff(df):
    """Calculate time difference between timestamps"""
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors='coerce')
    df["Time_Difference"] = df["Timestamp"].diff().fillna(pd.Timedelta(seconds=0))
    df["Time_Difference"] = df["Time_Difference"].astype(str)
    return df

def clean_user_name(name):
    """Normalize usernames to prevent duplicates"""
    return name.strip().lower()

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.set_page_config(page_title="Cloud Tracker", layout="wide")
st.title("☁️ Cloud-Based Productivity & Audit Tracker")

user_input = st.text_input("👤 Enter your name:")
if user_input:
    user = clean_user_name(user_input)
    st.subheader(f"📄 Sheet for {user}")

    df = get_user_data(user)
    if df.empty:
        df = pd.DataFrame(columns=COLUMNS)

    # Dropdown values
    status_options = ["Pending", "In Progress", "Completed", "Audited", "Rejected"]
    audit_options = [True, False]

    # Build grid options
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=True, resizable=True)
    gb.configure_grid_options(enableRangeSelection=True, enableCellTextSelection=True, enableClipboard=True)
    gb.configure_selection('multiple', use_checkbox=True)

    # Configure dropdowns
    gb.configure_column("Status", editable=True, cellEditor='agSelectCellEditor',
                        cellEditorParams={'values': status_options})
    gb.configure_column("Audit_Status", editable=True, cellEditor='agSelectCellEditor',
                        cellEditorParams={'values': ['True', 'False']})
    
    grid_options = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        theme="alpine"
    )

    updated_df = grid_response["data"]

    # Buttons
    col1, col2, col3 = st.columns(3)

with col1:
    if st.button("💾 Save Changes"):
        now = datetime.now()

        # Auto-fill missing Date & Timestamp
        updated_df["Date"] = updated_df["Date"].replace("", pd.NaT)
        updated_df["Date"] = updated_df["Date"].fillna(now.date())

        updated_df["Timestamp"] = updated_df["Timestamp"].replace("", pd.NaT)
        updated_df["Timestamp"] = updated_df["Timestamp"].fillna(now.isoformat())

        # Auto-fill Audit Date if Audit_Status == True
        updated_df["Audit_Date"] = updated_df.apply(
            lambda r: now.date() if str(r.get("Audit_Status")).lower() == "true" else r.get("Audit_Date"),
            axis=1
        )

        updated_df["Source"] = user
        updated_df = calculate_time_diff(updated_df)

        save_user_data(user, updated_df)
        st.success("✅ Changes saved successfully!")

with col2:
    if st.button("➕ Add New Row"):
        new_row = pd.DataFrame([{col: "" for col in COLUMNS}])
        updated_df = pd.concat([updated_df, new_row], ignore_index=True)
        save_user_data(user, updated_df)
        st.experimental_rerun()

with col3:
    uploaded_file = st.file_uploader("📤 Upload CSV/Excel for Bulk Entry", type=["csv", "xlsx"])
    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            bulk_df = pd.read_csv(uploaded_file)
        else:
            bulk_df = pd.read_excel(uploaded_file)

        # Ensure all expected columns exist
        for col in COLUMNS:
            if col not in bulk_df.columns:
                bulk_df[col] = ""

        bulk_df = bulk_df[COLUMNS]

        # Merge and clean
        merged_df = pd.concat([updated_df, bulk_df], ignore_index=True).drop_duplicates()
        merged_df["Source"] = user
        merged_df = calculate_time_diff(merged_df)
        save_user_data(user, merged_df)

        st.success(f"✅ {len(bulk_df)} rows uploaded successfully for {user}!")
        st.experimental_rerun()
# -----------------------------
# ADMIN PANEL
# -----------------------------
st.markdown("---")
st.subheader("🛠️ Admin Panel")

inspector = inspect(engine)
tables = inspector.get_table_names()

if tables:
    st.write("Existing user sheets:", tables)
    sheet_to_delete = st.selectbox("Select a sheet to delete", [""] + tables)
    confirm_delete = st.checkbox(f"Confirm delete '{sheet_to_delete}'")

    if sheet_to_delete and confirm_delete:
        if st.button("⚠️ Delete Selected Sheet"):
            with engine.connect() as conn:
                conn.execute(f"DROP TABLE IF EXISTS '{sheet_to_delete}'")
            st.success(f"✅ Sheet '{sheet_to_delete}' deleted!")
            st.experimental_rerun()

    st.markdown("### 💾 Download All User Data")
    combined_df = get_all_data()
    if not combined_df.empty:
        combined_df = calculate_time_diff(combined_df)

        # Prepare Excel and CSV for download
        csv_data = combined_df.to_csv(index=False).encode('utf-8')

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            combined_df.to_excel(writer, index=False, sheet_name="All_Data")

        st.download_button(
            label="⬇️ Download Combined Data as CSV",
            data=csv_data,
            file_name="combined_data.csv",
            mime="text/csv"
        )

        st.download_button(
            label="⬇️ Download Combined Data as Excel",
            data=excel_buffer.getvalue(),
            file_name="combined_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No data available to download.")
else:
    st.info("No user sheets found.")
