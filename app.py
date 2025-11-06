import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine

# 1️⃣ Database connection
engine = create_engine('sqlite:///database.db')

# 2️⃣ Define table columns
columns = [
    "Date", "Tasks", "DOS", "Status", "Audit_Status",
    "User_ID", "Comments", "Auditor_Comments",
    "Audit_Date", "Timestamp", "Time_Difference", "Source"
]

# 3️⃣ Helper function to load user data
def load_user_data(user):
    try:
        df = pd.read_sql(f"SELECT * FROM '{user}'", engine)
    except:
        df = pd.DataFrame(columns=columns)
    return df

# 4️⃣ Save entry to database
def save_entry(user, entry):
    df = load_user_data(user)
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.to_sql(user, engine, if_exists='replace', index=False)

# 5️⃣ Calculate time difference
def calculate_time_diff(user):
    df = load_user_data(user)
    if len(df) >= 2:
        last_time = datetime.fromisoformat(df.iloc[-2]["Timestamp"])
        now_time = datetime.fromisoformat(df.iloc[-1]["Timestamp"])
        diff = now_time - last_time
        df.loc[df.index[-1], "Time_Difference"] = str(diff)
        df.to_sql(user, engine, if_exists='replace', index=False)

# 6️⃣ Streamlit UI
st.title("🧮 Productivity & Audit Tracker")

user = st.text_input("Enter your User Name (Source):").strip()

if user:
    st.subheader(f"User Sheet: {user}")

    task = st.text_input("Task / Timesheet Name:")
    dos = st.text_input("DOS:")
    status = st.selectbox("Status", ["", "Uploaded", "Already Uploaded", "Only Timesheet Uploaded", "Rejected", "Audited", "Previously Processed"])
    audit_status = st.checkbox("Audit Done?")
    user_id = st.text_input("User ID:")
    comments = st.text_area("Comments:")
    auditor_comments = st.text_area("Auditor Comments:")

    if st.button("Add Entry"):
        now = datetime.now()
        entry = {
            "Date": now.date(),
            "Tasks": task,
            "DOS": dos,
            "Status": status,
            "Audit_Status": audit_status,
            "User_ID": user_id,
            "Comments": comments,
            "Auditor_Comments": auditor_comments,
            "Audit_Date": now.date() if audit_status else "",
            "Timestamp": now.isoformat(),
            "Time_Difference": "",
            "Source": user
        }
        save_entry(user, entry)
        calculate_time_diff(user)
        st.success("✅ Entry added successfully!")

    # Display user's data
    user_df = load_user_data(user)
    st.dataframe(user_df)

    # Combined data view
    if st.button("Show Combined Data"):
        tables = engine.table_names()
        all_data = pd.concat([load_user_data(u) for u in tables], ignore_index=True)
        st.subheader("📊 Combined Data (All Users)")
        st.dataframe(all_data)
