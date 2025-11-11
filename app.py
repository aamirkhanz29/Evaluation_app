import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, inspect
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import io
import re

# =====================================================
# DATABASE SETUP
# =====================================================
engine = create_engine('sqlite:///cloudbase.db')

# Define consistent columns
COLUMNS = [
    "Date", "Tasks", "DOS", "Status", "Audit_Status",
    "User_ID", "Comments", "Auditor_Comments",
    "Audit_Date", "Timestamp", "Time_Difference", "Source"
]

# =====================================================
# HELPER FUNCTIONS
# =====================================================
def clean_user_name(name: str) -> str:
    """Normalize usernames and make DB-safe table names."""
    return re.sub(r'\W+', '_', name.strip().lower())

def get_user_data(user: str) -> pd.DataFrame:
    """Load user's table from database."""
    try:
        df = pd.read_sql(f"SELECT * FROM '{user}'", engine)
    except Exception:
        df = pd.DataFrame(columns=COLUMNS)
    return df

def save_user_data(user: str, df: pd.DataFrame):
    """Save user's DataFrame to SQLite."""
    df.to_sql(user, engine, if_exists="replace", index=False)

def get_all_data() -> pd.DataFrame:
    """Combine all user tables."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    all_data = []
    for t in tables:
        try:
            df = pd.read_sql(f"SELECT * FROM '{t}'", engine)
            df["Source_Sheet"] = t
            all_data.append(df)
        except Exception:
            continue
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame(columns=COLUMNS)

def calculate_time_diff(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate sequential time difference by timestamp."""
    df = df.copy()
    if "Timestamp" not in df:
        return df
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors='coerce')
    df = df.sort_values("Timestamp", ignore_index=True)
    df["Time_Difference"] = df["Timestamp"].diff().fillna(pd.Timedelta(0))
    df["Time_Difference"] = df["Time_Difference"].astype(str)
    return df

# =====================================================
# STREAMLIT UI
# =====================================================
st.set_page_config(page_title="Cloud Tracker", layout="wide")
st.title("☁️ Cloud-Based Productivity & Audit Tracker")

user_input = st.text_input("👤 Enter your name:")

if user_input:
    user = clean_user_name(user_input)
    st.subheader(f"📄 Sheet for {user}")

    # Load or create user data
    df = get_user_data(user)
    if df.empty:
        df = pd.DataFrame(columns=COLUMNS)

    # Dropdown values
    status_options = ["Pending", "In Progress", "Completed", "Audited", "Rejected"]

    # Build grid
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=True, resizable=True)
    gb.configure_grid_options(enableRangeSelection=True, enableCellTextSelection=True, enableClipboard=True)
    gb.configure_selection('multiple', use_checkbox=True)
    gb.configure_column("Status", editable=True, cellEditor='agSelectCellEditor',
                        cellEditorParams={'values': status_options})
    gb.configure_column("Audit_Status", editable=True, cellEditor='agSelectCellEditor',
                        cellEditorParams={'values': [True, False]})

    grid_options = gb.build()
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        theme="alpine"
    )

    updated_df = grid_response["data"]

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("💾 Save Changes"):
            now = datetime.now()

            # Fill missing date/timestamp
            updated_df["Date"] = updated_df["Date"].replace("", pd.NaT)
            updated_df["Date"] = updated_df["Date"].fillna(now.date())

            updated_df["Timestamp"] = updated_df["Timestamp"].replace("", pd.NaT)
            updated_df["Timestamp"] = updated_df["Timestamp"].fillna(now.isoformat())

            # Only set Audit_Date if Audit_Status = True and Audit_Date empty
            updated_df["Audit_Date"] = updated_df.apply(
                lambda r: now.date()
                if str(r.get("Audit_Status")).lower() == "true" and pd.isna(r.get("Audit_Date"))
                else r.get("Audit_Date"),
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

            # Ensure all columns exist
            for col in COLUMNS:
                if col not in bulk_df.columns:
                    bulk_df[col] = ""

            bulk_df = bulk_df[COLUMNS]

            # Merge and clean
            merged_df = pd.concat([updated_df, bulk_df], ignore_index=True)
            merged_df = merged_df.drop_duplicates(subset=["Date", "Tasks", "DOS"], keep="last")
            merged_df["Source"] = user
            merged_df = calculate_time_diff(merged_df)
            save_user_data(user, merged_df)

            st.success(f"✅ {len(bulk_df)} rows uploaded successfully for {user}!")
            st.experimental_rerun()

# =====================================================
# ADMIN PANEL
# =====================================================
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

    # Download section
    st.markdown("### 💾 Download All User Data")
    combined_df = get_all_data()
    if not combined_df.empty:
        combined_df = calculate_time_diff(combined_df)

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
