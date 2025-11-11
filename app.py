# app_dash.py
import dash
from dash import Dash, html, dcc, Input, Output, State
import dash_ag_grid as dag
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import io
import base64

# -----------------------------
# DATABASE SETUP
# -----------------------------
engine = create_engine('sqlite:///cloudbase.db')
TABLE_NAME = "main_table"
COLUMNS = [
    "Date", "Tasks", "DOS", "Status", "Audit_Status",
    "User_ID", "Comments", "Auditor_Comments",
    "Audit_Date", "Timestamp", "Time_Difference", "Source"
]
status_options = ["Uploaded", "Already Uploaded", "Only Sheet uploaded", "Audited", "Rejected", "Previously Processed"]

# Ensure table exists
with engine.connect() as conn:
    conn.exec_driver_sql(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            Date TEXT, Tasks TEXT, DOS TEXT, Status TEXT, Audit_Status TEXT,
            User_ID TEXT, Comments TEXT, Auditor_Comments TEXT,
            Audit_Date TEXT, Timestamp TEXT, Time_Difference TEXT, Source TEXT
        )
    """)

# Load initial data
try:
    df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", engine)
except:
    df = pd.DataFrame(columns=COLUMNS)

# Always have 10 blank rows for pasting
if df.empty:
    df = pd.DataFrame([{col: "" for col in COLUMNS} for _ in range(10)])
else:
    for _ in range(10):
        df.loc[len(df)] = ["" for _ in COLUMNS]

# -----------------------------
# DASH APP
# -----------------------------
app = Dash(__name__)
app.title = "Cloud-Based Productivity Tracker"

app.layout = html.Div([
    html.H2("☁️ Cloud-Based Productivity Tracker"),
    html.Div([
        html.Label("User Name:"),
        dcc.Input(id="user-input", type="text", placeholder="Enter your name"),
        html.Button("Load Sheet", id="load-btn")
    ], style={"margin-bottom": "20px"}),

    html.Div([
        dag.AgGrid(
            id="excel-grid",
            columnDefs=[{"headerName": c, "field": c, "editable": True} for c in COLUMNS],
            rowData=df.to_dict("records"),
            defaultColDef={"resizable": True, "sortable": True, "filter": True},
            columnSize="sizeToFit",
            dashGridOptions={
                "enableRangeSelection": True,
                "enableFillHandle": True,
                "clipboardPaste": True,   # multi-cell paste
                "suppressColumnVirtualisation": True, # show all columns
                "suppressRowVirtualisation": False,
                "rowSelection": "multiple",
                "domLayout": "normal",
            },
            style={"height": "500px", "width": "100%"}
        )
    ]),

    html.Div([
        html.Button("💾 Save Changes", id="save-btn", n_clicks=0),
        html.Div(id="save-output", style={"margin-top": "10px", "color": "green"}),
    ], style={"margin-top": "20px"}),

    html.Hr(),
    html.H4("📥 Download Combined Data"),
    html.Div([
        html.Button("Download CSV", id="download-csv-btn"),
        dcc.Download(id="download-csv")
    ])
])

# -----------------------------
# CALLBACKS
# -----------------------------
@app.callback(
    Output("excel-grid", "rowData"),
    Input("load-btn", "n_clicks"),
    State("user-input", "value")
)
def load_user_data(n_clicks, user):
    if not user:
        return df.to_dict("records")
    user_clean = user.strip().lower()
    try:
        df_user = pd.read_sql(f"SELECT * FROM '{user_clean}'", engine)
    except:
        df_user = pd.DataFrame(columns=COLUMNS)
    # Add 10 blank rows
    for _ in range(10):
        df_user.loc[len(df_user)] = ["" for _ in COLUMNS]
    return df_user.to_dict("records")

@app.callback(
    Output("save-output", "children"),
    Input("save-btn", "n_clicks"),
    State("user-input", "value"),
    State("excel-grid", "rowData")
)
def save_data(n_clicks, user, rows):
    if n_clicks == 0 or not user:
        return ""
    df_save = pd.DataFrame(rows)
    df_save["Source"] = user.strip().lower()
    df_save.to_sql(user.strip().lower(), engine, if_exists="replace", index=False)
    # also save to main_table
    df_save.to_sql(TABLE_NAME, engine, if_exists="replace", index=False)
    return f"✅ Saved {len(df_save)} rows for {user}!"

@app.callback(
    Output("download-csv", "data"),
    Input("download-csv-btn", "n_clicks")
)
def download_csv(n_clicks):
    if n_clicks is None or n_clicks == 0:
        return dash.no_update
    df_all = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", engine)
    return dcc.send_data_frame(df_all.to_csv, "combined_data.csv", index=False)

# -----------------------------
# RUN SERVER
# -----------------------------
if __name__ == "__main__":
    app.run_server(debug=True)
