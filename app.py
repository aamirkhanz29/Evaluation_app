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

    # Load user data
    df = get_user_data(user)

    # Ensure all columns exist and convert to strings for editing
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype(str).replace("None", "")

    # Always keep 5 blank rows at the bottom
    for _ in range(5):
        df.loc[len(df)] = ["" for _ in COLUMNS]

    # Dropdown options
    status_options = ["Uploaded", "Already Uploaded", "Only Sheet uploaded", "Audited", "Rejected", "Previously Processed"]

    # -----------------------------
    # Configure AG-Grid
    # -----------------------------
   from st_aggrid.shared import JsCode

# build grid options
gb = GridOptionsBuilder.from_dataframe(df)

gb.configure_default_column(
    editable=True,
    resizable=True,
    sortable=True,
    filter=True,
    wrapText=True,
    autoHeight=True,
    cellStyle={'border': '1px solid #e0e0e0', 'fontSize': '13px'},
)

# dropdowns
gb.configure_column(
    "Status",
    editable=True,
    cellEditor="agSelectCellEditor",
    cellEditorParams={"values": status_options},
)
gb.configure_column(
    "Audit_Status",
    editable=True,
    cellEditor="agSelectCellEditor",
    cellEditorParams={"values": ["True", "False"]},
)

# grid options for Excel-like copy/paste
gb.configure_grid_options(
    enableRangeSelection=True,
    enableClipboard=True,
    suppressClipboardPaste=False,   # 🔑 allow multi-cell paste
    clipboardDelimiters={"row": "\n", "column": "\t"},
    stopEditingWhenCellsLoseFocus=False,
    undoRedoCellEditing=True,
    undoRedoCellEditingLimit=200,
    enableFillHandle=True,
    suppressRowClickSelection=True,
)

# Auto-fit columns when grid ready
gb.configure_grid_options(onGridReady=JsCode("""
function(params) {
    params.api.sizeColumnsToFit();
    document.addEventListener('paste', function(e) {
        // focus grid before paste
        params.api.gridBodyCtrl.focusController.focusGridView();
    });
}
"""))

grid_options = gb.build()

st.info("💡 Tip: Copy multiple cells in Excel (Ctrl+C) → click inside this grid → paste (Ctrl+V).")

# render grid
grid_response = AgGrid(
    df,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.VALUE_CHANGED,
    fit_columns_on_grid_load=False,
    allow_unsafe_jscode=True,
    theme="alpine",
    height=550,
    width='100%',
)
updated_df = grid_response["data"]

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
            st.rerun()

    st.markdown("### 💾 Download All User Data")
    combined_df = get_all_data()
    if not combined_df.empty:
        combined_df = calculate_time_diff(combined_df)

        # Prepare files
        csv_data = combined_df.to_csv(index=False).encode("utf-8")
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
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
