import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ---------- DATABASE SETUP ----------
engine = create_engine('sqlite:///cloudbase.db')

# Define columns
COLUMNS = [
    "Date", "Tasks", "DOS", "Status", "Audit_Status",
    "User_ID", "Comments", "Auditor_Comments", "Audit_Date",
    "Timestamp", "Time_Difference", "Source"
]

# ---------- HELPER FUNCTIONS ----------
def get_user_data(user):
    try:
        df = pd.read_sql(f"SELECT * FROM '{user}'", engine)
    except:
        df = pd.DataFrame(columns=COLUMNS)
    return df

def save_user_data(user, df):
    df.to_sql(user, engine, if_exists="replace", index=False)

def get_all_data():
    from sqlalchemy import create_engine, inspect

def get_all_data():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    all_data = []
    for t in tables:
        all_data.append(pd.read_sql(f"SELECT * FROM '{t}'", engine))
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame(columns=COLUMNS)


# ---------- APP UI ----------
st.set_page_config(page_title="Cloud Database", layout="wide")
st.title("☁️ Cloud-Based Productivity Tracker")

user = st.text_input("👤 Enter your name (used as your personal sheet):").strip()

if user:
    st.subheader(f"📄 Sheet for {user}")

    df = get_user_data(user)

    # If no data yet, create empty DataFrame
    if df.empty:
        df = pd.DataFrame(columns=COLUMNS)

    # Display editable grid (Excel-like)
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
            # Add timestamps and date auto-fill
            now = datetime.now()
            updated_df["Timestamp"] = updated_df["Timestamp"].fillna(now.isoformat())
            updated_df["Date"] = updated_df["Date"].fillna(now.date().isoformat())
            updated_df["Source"] = user
            save_user_data(user, updated_df)
            st.success("✅ Data saved successfully!")

    with col2:
        if st.button("➕ Add New Row"):
            new_row = pd.DataFrame([{col: "" for col in COLUMNS}])
            df = pd.concat([updated_df, new_row], ignore_index=True)
            save_user_data(user, df)
            st.experimental_rerun()

    st.markdown("### 📊 Your Current Data")
    st.dataframe(updated_df, use_container_width=True)

    st.markdown("---")
    if st.button("📈 View Combined Data (All Users)"):
        combined_df = get_all_data()
        st.dataframe(combined_df, use_container_width=True)

# 🧹 Temporary cleanup tool (run once)
if st.button("🗑️ Delete a User Sheet"):
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    st.write("Existing user sheets:", tables)
    sheet_to_delete = st.selectbox("Select a sheet to delete", tables)
    confirm = st.checkbox(f"Confirm delete '{sheet_to_delete}'")

    if confirm and st.button("⚠️ Permanently Delete"):
        with engine.connect() as conn:
            conn.execute(f"DROP TABLE IF EXISTS '{sheet_to_delete}'")
        st.success(f"✅ '{sheet_to_delete}' deleted successfully!")
        st.experimental_rerun()
