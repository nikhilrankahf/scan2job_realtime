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
# 1) SOURCE FUNCTIONS (replace with your real pipelines)
# ---------------------------

# Map sub-dept -> process (edit to your taxonomy)
SUBDEPT_TO_PROCESS = {
    "Assembly": "PRODUCTION", "Kitting": "PRODUCTION", "Prep": "PRODUCTION",
    "Labeling": "PRODUCTION",
    "Inventory": "WAREHOUSE", "Replenishment": "WAREHOUSE",
    "Loading": "SHIPPING", "Putaway": "SHIPPING",
}

# Simulated "live" rows; replace with your DB/Kafka view.
# Columns you said you need: id, name, latest activity, WD dept, scanned dept/position, clock/scan flags.
def get_live_associate_rows() -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    data = [
        # id, name, WD dept, scanned_dept, work_pos, last_activity_ts, has_clock, has_scan
        ("A12345", "Jane Doe",  "Shipping",   "Assembly", "Bay-2", now - timedelta(seconds=90),  True,  True),
        ("A11772", "Sam Patel", "Production",   None,        None,    now - timedelta(seconds=120), True,  False),
        ("A10998", "Li Wang",   "Production",    "Kitting",  "Line-1", now - timedelta(seconds=40),  True,  True),
        ("A20111", "Alex Ross", "Repack",     "Repack",   "Bay-1",  now - timedelta(seconds=61),  False, True),
        ("A55555", "Mia Khan",  "Quality",    "Dock",     "Dock-3", now - timedelta(seconds=25),  True,  True),
        ("A77777", "Ola Ibe",   "Warehouse",  "Inventory",        None,    now - timedelta(minutes=7),   True,  False),
        ("A88888", "Nina T",    "Returns",    "Labeling", "Tbl-2",  now - timedelta(seconds=55),  True,  True),
    ]
    df = pd.DataFrame(data, columns=[
        "associate_id","associate_name","wd_department","scanned_department",
        "work_position","last_activity_ts","has_clock","has_scan"
    ])
    # Derived columns
    df["actual_process"] = df["scanned_department"].map(SUBDEPT_TO_PROCESS)
    df["staleness_s"] = (datetime.now(timezone.utc) - df["last_activity_ts"]).dt.total_seconds().round().astype(int)
    return df

# ---------------------------
# Metric Tile Component (minimal: title + headcount)
# ---------------------------
def _compute_flags_for_tile(df: pd.DataFrame, floor_window_min: int, inpos_window_min: int) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    out = df.copy()
    if "scanned_department" not in out.columns:
        out["scanned_department"] = pd.Series([None] * len(out))
    out["last_activity_ts"] = pd.to_datetime(out["last_activity_ts"], utc=True)
    on_floor = (
        (out["has_clock"].fillna(False) | out["has_scan"].fillna(False)) &
        ((now - out["last_activity_ts"]) <= timedelta(minutes=floor_window_min))
    )
    in_position = (
        out["scanned_department"].notna() &
        ((now - out["last_activity_ts"]) <= timedelta(minutes=inpos_window_min))
    )
    out["on_floor"] = on_floor
    out["in_position"] = in_position
    out["unscanned"] = on_floor & (~in_position)
    return out

def metric_tile(
    df: pd.DataFrame,
    title: str,
    group_options: dict[str, str] | None = None,  # unused in minimal view
    default_group: str = "Job Department",        # unused in minimal view
    floor_window_min: int = 10,
    inpos_window_min: int = 5,
) -> None:
    filtered = _compute_flags_for_tile(df, floor_window_min=floor_window_min, inpos_window_min=inpos_window_min)
    title_to_flag = {"On Floor": "on_floor", "Scanned In": "in_position", "Unscanned": "unscanned"}
    if title not in title_to_flag:
        raise ValueError("title must be one of 'On Floor' | 'Scanned In' | 'Unscanned'")
    flag_col = title_to_flag[title]
    subset = filtered[filtered[flag_col]] if flag_col in filtered.columns else filtered.iloc[0:0]
    total_associates = int(subset["associate_id"].nunique())
    st.markdown(
        f"<div style='font-size:1.25rem; font-weight:700; margin:0 0 6px 0'>{title}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='font-size:48px; font-weight:600; line-height:1.1; margin:0 0 12px 0'>{total_associates}</div>",
        unsafe_allow_html=True,
    )

# Rules (edit thresholds to your SLOs)
FLOOR_WINDOW_MIN = 10   # "On floor" if clock OR scan event seen in last X minutes
IN_POSITION_WINDOW_MIN = 5  # "In-position" if scanned into a valid position in last Y minutes

def compute_presence_flags(df: pd.DataFrame) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    df = df.copy()
    df["on_floor"] = (
        (df["has_clock"] | df["has_scan"]) &
        ((now - df["last_activity_ts"]) <= timedelta(minutes=FLOOR_WINDOW_MIN))
    )
    df["in_position"] = (
        df["scanned_department"].notna() &
        ((now - df["last_activity_ts"]) <= timedelta(minutes=IN_POSITION_WINDOW_MIN))
    )
    df["unscanned"] = df["on_floor"] & ~df["in_position"]
    return df

# ---------------------------
# 2) READ / TRANSFORM
# ---------------------------
people_df = compute_presence_flags(get_live_associate_rows())
last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# (Cleaned) No global cached summaries; tile derives its own view

# Filters / privacy
with st.sidebar:
    st.subheader("Filters")
    privacy = st.toggle("Hide names on wallboard", value=False)
    process_choices = ["ALL", "PRODUCTION", "WAREHOUSE", "SHIPPING"]
    process_filter = st.selectbox("Process", process_choices, index=0)
    subdept_filter = st.text_input("Filter: Scanned Department contains", "")
    show_outliers = st.multiselect(
        "Outliers",
        ["Clock-only (on floor, no scan)", "Scan-only (no clock)", "Stale > X min", "Hiring≠Actual"],
        []
    )
    stale_minutes = st.slider("Stale threshold (minutes)", 1, 15, 6)

# ---------------------------
# 3) TOP LAYOUT (two columns)
# ---------------------------
left, right = st.columns([1.2, 1.0])

# LEFT: Department table (current scanned headcount) with optional sub-dept drill
with left:
    st.subheader("Department-level Scanned Count")
    # dept = scanned_department; fall back to WD dept when no scan
    dept_series = people_df["scanned_department"].fillna("—")
    dept_table = (
        people_df.assign(department=dept_series)
        .groupby("department", dropna=False)["in_position"]
        .sum()
        .rename("scanned_in_count")
        .reset_index()
        .sort_values("scanned_in_count", ascending=False)
    )
    st.dataframe(
        dept_table,
        use_container_width=True,
        hide_index=True
    )
    # Simple “dropdown” drill: pick a department and show its sub-rows
    picked_dept = st.selectbox("Drill into sub-department", ["(none)"] + dept_table["department"].tolist())
    if picked_dept != "(none)":
        st.caption(f"Associates scanned in {picked_dept}")
        drill = people_df[people_df["scanned_department"].fillna("—") == picked_dept]
        st.dataframe(
            drill[["associate_id","associate_name","wd_department","scanned_department",
                   "work_position","staleness_s"]].rename(columns={
                "associate_id":"ID","associate_name":"Name","wd_department":"Hiring Dept",
                "scanned_department":"Scanned Dept","work_position":"Work Position","staleness_s":"Stale (s)"
            }),
            use_container_width=True, hide_index=True
        )

# RIGHT: Vertically stacked tiles using reusable component
with right:
    st.subheader("Live Tiles")
    metric_tile(
        people_df,
        title="On Floor",
        group_options={"Job Department": "wd_department", "Sub-Department": "scanned_department"},
        default_group="Job Department",
        floor_window_min=FLOOR_WINDOW_MIN,
        inpos_window_min=IN_POSITION_WINDOW_MIN,
    )
    metric_tile(
        people_df,
        title="Scanned In",
        group_options={"Job Department": "wd_department", "Sub-Department": "scanned_department"},
        default_group="Job Department",
        floor_window_min=FLOOR_WINDOW_MIN,
        inpos_window_min=IN_POSITION_WINDOW_MIN,
    )
    metric_tile(
        people_df,
        title="Unscanned",
        group_options={"Job Department": "wd_department", "Sub-Department": "scanned_department"},
        default_group="Job Department",
        floor_window_min=FLOOR_WINDOW_MIN,
        inpos_window_min=IN_POSITION_WINDOW_MIN,
    )

    st.caption(f"Data as of **{last_update}** (local time)")
    st.caption("P95 freshness (placeholder): 40–60s · Completeness (placeholder): 95–97%")

# ---------------------------
# 4) BOTTOM: PEOPLE TABLE (detail)
# ---------------------------
st.markdown("---")
st.subheader("People — Latest Activity")

# Apply filters
filtered = people_df.copy()

if process_filter != "ALL":
    filtered = filtered[filtered["actual_process"] == process_filter]

if subdept_filter.strip():
    filtered = filtered[filtered["scanned_department"].fillna("").str.contains(subdept_filter, case=False)]

# Outliers
if "Clock-only (on floor, no scan)" in show_outliers:
    filtered = filtered[filtered["on_floor"] & ~filtered["in_position"] & filtered["has_clock"] & ~filtered["has_scan"]]
if "Scan-only (no clock)" in show_outliers:
    filtered = filtered[filtered["has_scan"] & ~filtered["has_clock"]]
if "Stale > X min" in show_outliers:
    filtered = filtered[(datetime.now(timezone.utc) - filtered["last_activity_ts"]) > timedelta(minutes=stale_minutes)]
if "Hiring≠Actual" in show_outliers:
    # If no scan (actual_process NaN) we treat as mismatch off the bat
    mism = filtered["actual_process"].fillna("UNKNOWN") != filtered["wd_department"].map(lambda d: SUBDEPT_TO_PROCESS.get(d, d))
    filtered = filtered[mism]

# Privacy mask
if privacy:
    filtered = filtered.assign(associate_name="—")

# Friendly columns
pretty = filtered[[
    "associate_id","associate_name","wd_department","actual_process",
    "scanned_department","work_position","last_activity_ts","staleness_s",
    "has_clock","has_scan","on_floor","in_position","unscanned"
]].rename(columns={
    "associate_id":"ID","associate_name":"Name","wd_department":"Hiring Dept",
    "actual_process":"Actual Process","scanned_department":"Scanned Dept",
    "work_position":"Work Position","last_activity_ts":"Last Activity (UTC)",
    "staleness_s":"Stale (s)","has_clock":"Clock","has_scan":"Scan",
    "on_floor":"On Floor","in_position":"In Position"
})

st.dataframe(pretty.sort_values("Stale (s)"), use_container_width=True, hide_index=True)

