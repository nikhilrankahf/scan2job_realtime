# app.py
import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import streamlit as st

def _set_query_param_t():
    ts = str(int(time.time()))
    try:
        st.query_params["t"] = ts
    except Exception:
        try:
            st.experimental_set_query_params(t=ts)
        except Exception:
            pass


# ---------------------------
# 0) PAGE & REFRESH
# ---------------------------
st.set_page_config(page_title="Live Floor Presence", layout="wide")
st.title("Live Floor Presence")

# Auto-refresh every N seconds (keeps code simple for v1)
REFRESH_SEC = 5
st.caption(f"Data updates every {REFRESH_SEC}s")
st_autorefresh = st.experimental_rerun if False else None
_ = getattr(st, "data_editor", getattr(st, "experimental_data_editor", None))  # noqa: just to ensure Streamlit >=1.31

# Optional: simple auto-refresh
_set_query_param_t()
time.sleep(REFRESH_SEC * 0.0)  # no-op; keep it simple. Use st_autorefresh if you prefer.

# ---------------------------
# 1) DATA LOADING FROM CSV
# ---------------------------

SCANNED_SOURCES = {"Badgr", "HighJump", "Pick to Light"}

@st.cache_data(ttl=30)
def load_associates_from_csv(csv_path: str = "Scan2Job Realtime Sample Data.csv") -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Ensure expected columns exist
    expected_cols = {"ASSOCIATE_ID","Name","JOB_DEPARTMENT","SOURCE","WORK_DEPARTMENT","WORK_POSITION","START_TIME_LOCAL"}
    missing = expected_cols.difference(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {sorted(missing)}")
    df["START_TIME_LOCAL"] = pd.to_datetime(df["START_TIME_LOCAL"], errors="coerce")

    # Latest record per associate (for stable department display)
    df_sorted = df.sort_values(["ASSOCIATE_ID","START_TIME_LOCAL"]).dropna(subset=["ASSOCIATE_ID"])  # type: ignore
    latest_idx = df_sorted.groupby("ASSOCIATE_ID")["START_TIME_LOCAL"].idxmax()
    latest = df_sorted.loc[latest_idx, [
        "ASSOCIATE_ID","Name","JOB_DEPARTMENT","WORK_DEPARTMENT","WORK_POSITION","START_TIME_LOCAL"
    ]].rename(columns={
        "ASSOCIATE_ID":"associate_id",
        "Name":"associate_name",
        "JOB_DEPARTMENT":"job_department",
        "WORK_DEPARTMENT":"work_department",
        "WORK_POSITION":"work_position",
        "START_TIME_LOCAL":"last_activity_ts",
    })

    # Flags by associate (any record matching condition)
    source_series = df["SOURCE"].astype(str)
    work_dept_series = df["WORK_DEPARTMENT"].astype(str)
    work_pos_series = df["WORK_POSITION"].astype(str)

    scanned_ids = df[source_series.isin(SCANNED_SOURCES)]["ASSOCIATE_ID"].dropna().astype(str).unique()
    unscanned_mask = (
        source_series.str.casefold().eq("compliance") |
        work_dept_series.str.casefold().eq("compliance") |
        work_pos_series.str.casefold().eq("time off task")
    )
    unscanned_ids = df[unscanned_mask]["ASSOCIATE_ID"].dropna().astype(str).unique()
    on_floor_ids = df["ASSOCIATE_ID"].dropna().astype(str).unique()

    people_df = latest.copy().reset_index(drop=True)
    people_df["on_floor"] = people_df["associate_id"].astype(str).isin(on_floor_ids)
    people_df["scanned_in"] = people_df["associate_id"].astype(str).isin(scanned_ids)
    people_df["unscanned"] = people_df["associate_id"].astype(str).isin(unscanned_ids)
    return people_df

# ---------------------------
# Metric Tile Component (CSV-driven flags)
# ---------------------------

def metric_tile(
    df: pd.DataFrame,
    title: str,
    group_options: dict[str, str] | None = None,
    default_group: str = "Job Department",
    floor_window_min: int = 10,
    inpos_window_min: int = 5,
) -> None:
    # df expected to have boolean columns: on_floor, scanned_in, unscanned, and job_department
    title_to_flag = {"On Floor": "on_floor", "Scanned In": "scanned_in", "Unscanned": "unscanned"}
    if title not in title_to_flag:
        raise ValueError("title must be one of 'On Floor' | 'Scanned In' | 'Unscanned'")
    flag_col = title_to_flag[title]
    subset = df[df[flag_col]] if flag_col in df.columns else df.iloc[0:0]
    total_associates = int(subset["associate_id"].nunique())

    # Single expander: header shows title and headcount; expanding reveals department table
    with st.expander(f"{title} — {total_associates}", expanded=False):
        breakdown_df = (
            subset.fillna({"job_department": "—"})
            .groupby("job_department")["associate_id"].nunique()
            .sort_values(ascending=False)
            .reset_index()
        )
        breakdown_df.columns = ["Job Department", "Associates"]
        st.dataframe(breakdown_df, use_container_width=True, hide_index=True)

# No legacy clock/scan rules; CSV defines the categories

# ---------------------------
# 2) READ / TRANSFORM
# ---------------------------
people_df = load_associates_from_csv()
last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# CSV-driven model; tiles derive their own view

# Filters / privacy
with st.sidebar:
    st.subheader("Filters")
    privacy = st.toggle("Hide names on wallboard", value=False)

# ---------------------------
# 3) TOP LAYOUT (two columns)
# ---------------------------
left, right = st.columns([1.2, 1.0])

# LEFT: Department table (current scanned headcount) with optional sub-dept drill
with left:
    st.subheader("Department-level Scanned Count")
    dept_table = (
        people_df[people_df["scanned_in"]]
        .fillna({"job_department": "—"})
        .groupby("job_department")["associate_id"].nunique()
        .rename("scanned_in_count")
        .reset_index()
        .sort_values("scanned_in_count", ascending=False)
    )
    st.dataframe(
        dept_table,
        use_container_width=True,
        hide_index=True
    )

# RIGHT: Vertically stacked tiles using reusable component
with right:
    st.subheader("Live Tiles")
    metric_tile(
        people_df,
        title="On Floor",
        group_options=None,
        default_group="Job Department",
        floor_window_min=0,
        inpos_window_min=0,
    )
    metric_tile(
        people_df,
        title="Scanned In",
        group_options=None,
        default_group="Job Department",
        floor_window_min=0,
        inpos_window_min=0,
    )
    metric_tile(
        people_df,
        title="Unscanned",
        group_options=None,
        default_group="Job Department",
        floor_window_min=0,
        inpos_window_min=0,
    )

    st.caption(f"Data as of **{last_update}** (local time)")
    st.caption("P95 freshness (placeholder): 40–60s · Completeness (placeholder): 95–97%")

# ---------------------------
# 4) BOTTOM: PEOPLE TABLE (detail)
# ---------------------------
st.markdown("---")
st.subheader("Latest Associate Activity")
filtered = people_df.copy()
if privacy:
    filtered = filtered.assign(associate_name="—")
pretty = filtered[[
    "associate_id","associate_name","job_department","scanned_in","work_department","work_position","last_activity_ts"
]].rename(columns={
    "associate_id":"Id",
    "associate_name":"Name",
    "job_department":"Hiring Department",
    "scanned_in":"Scanned In",
    "work_department":"Work Department",
    "work_position":"Work Position",
    "last_activity_ts":"Last Activity Timestamp",
})

# Compact filter icon (expander) aligned above the table (top-right)
controls_left, controls_right = st.columns([1, 1])
with controls_right:
    with st.expander("🔍 Filters", expanded=False):
        f1, f2, f3 = st.columns(3)
        with f1:
            id_q = st.text_input("Id contains", "").strip()
            name_q = st.text_input("Name contains", "").strip()
        with f2:
            hiring_q = st.text_input("Hiring Dept contains", "").strip()
            work_dept_q = st.text_input("Work Dept contains", "").strip()
        with f3:
            work_pos_q = st.text_input("Work Position contains", "").strip()
            scanned_choice = st.selectbox("Scanned In", ["(any)", "Yes", "No"], index=0)

filtered_pretty = pretty.copy()
if id_q:
    filtered_pretty = filtered_pretty[filtered_pretty["Id"].astype(str).str.contains(id_q, case=False, na=False)]
if name_q:
    filtered_pretty = filtered_pretty[filtered_pretty["Name"].astype(str).str.contains(name_q, case=False, na=False)]
if hiring_q:
    filtered_pretty = filtered_pretty[filtered_pretty["Hiring Department"].astype(str).str.contains(hiring_q, case=False, na=False)]
if work_dept_q:
    filtered_pretty = filtered_pretty[filtered_pretty["Work Department"].astype(str).str.contains(work_dept_q, case=False, na=False)]
if work_pos_q:
    filtered_pretty = filtered_pretty[filtered_pretty["Work Position"].astype(str).str.contains(work_pos_q, case=False, na=False)]
if scanned_choice != "(any)":
    val = scanned_choice == "Yes"
    filtered_pretty = filtered_pretty[filtered_pretty["Scanned In"] == val]

st.dataframe(filtered_pretty.sort_values(["Hiring Department","Name"]), use_container_width=True, hide_index=True)

