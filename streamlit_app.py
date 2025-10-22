# app.py
import time
import hashlib
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
st.set_page_config(page_title="Scan2Job Live Floor Tracking", layout="wide")
st.title("Scan2Job Live Floor Tracking")

# -------- Quick single-password gate (demo) --------
def _password_gate() -> None:
    # Session timeout (minutes); change via secrets if desired
    timeout_min = int(st.secrets.get("APP_PASSWORD_TIMEOUT_MIN", 30))
    now = datetime.now()

    expected = str(st.secrets.get("APP_PASSWORD", ""))
    token = hashlib.sha256(expected.encode()).hexdigest()[:16] if expected else ""

    # Check URL auth token + timestamp to persist across full page reloads
    try:
        qp = st.query_params
    except Exception:
        qp = {}
    # st.query_params behaves like a dict of strings; handle lists defensively
    def _first(val):
        if isinstance(val, list):
            return val[0] if val else ""
        return val if isinstance(val, str) else ""
    qp_auth = _first(qp.get("auth", ""))
    qp_asu = _first(qp.get("asu", ""))
    try:
        qp_asu_ts = int(qp_asu)
    except Exception:
        qp_asu_ts = 0

    if token and qp_auth == token and qp_asu_ts > 0:
        if (now - datetime.fromtimestamp(qp_asu_ts)) <= timedelta(minutes=timeout_min):
            st.session_state["__authed"] = True
            st.session_state["__auth_ts"] = now
            # refresh sliding window in URL
            try:
                st.query_params["auth"] = token
                st.query_params["asu"] = str(int(time.time()))
            except Exception:
                pass
            return

    # If already authed, enforce idle timeout using last auth timestamp
    if st.session_state.get("__authed", False) and st.session_state.get("__auth_ts") is not None:
        if (now - st.session_state["__auth_ts"]) <= timedelta(minutes=timeout_min):
            # Sliding window: refresh timestamp on activity/rerun
            st.session_state["__auth_ts"] = now
            return
        # Timed out → require login again
        st.session_state["__authed"] = False

    st.write("")
    st.info("This app is protected. Enter the access password to continue.")
    with st.form("__auth_form", clear_on_submit=False):
        pw = st.text_input("Password", type="password")
        ok = st.form_submit_button("Login")
    if ok:
        if pw and pw == expected:
            st.session_state["__authed"] = True
            st.session_state["__auth_ts"] = now
            # Persist auth in URL so full reloads don't re-prompt within timeout
            if token:
                try:
                    st.query_params["auth"] = token
                    st.query_params["asu"] = str(int(time.time()))
                except Exception:
                    pass
            st.success("Access granted")
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()

_password_gate()

# ---------------------------
# Helper: Header with micro info icon + popover
# ---------------------------
def render_header_with_info(title_text: str, info_md: str) -> None:
    # Minimal CSS for micro icon only (title uses native Streamlit subheader styling)
    st.markdown(
        """
        <style>
          .hdr-info {
            font-size:12px; color:#6b7280;
            display:inline-flex; align-items:center; justify-content:center;
            width:14px; height:14px; border-radius:50%;
            border:1px solid rgba(0,0,0,0.15);
            cursor:pointer; user-select:none;
          }
          .hdr-info:focus { outline:2px solid #9ca3af; outline-offset:2px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Two columns: left = native subheader, right = micro icon
    col_title, col_icon = st.columns([0.97, 0.03])
    with col_title:
        if title_text:
            st.subheader(title_text)
    with col_icon:
        with st.popover("i", use_container_width=False):  # click to open
            st.markdown(info_md)
        st.markdown("<div class='hdr-info' aria-label='How this is calculated' tabindex='0'></div>", unsafe_allow_html=True)

# ---------------------------
# Helper: On Floor header with inline micro icon
# ---------------------------
def render_on_floor_header_with_icon(title_text: str):
    # Inline heading with compact details popover to keep icon directly beside the title
    st.markdown(
        """
        <style>
          .ofh-pop { display:inline-block; margin-left:6px; }
          .ofh-pop summary {
            list-style:none; cursor:pointer; user-select:none; display:inline-flex;
            align-items:center; justify-content:center; width:16px; height:16px;
            border-radius:50%; border:1px solid rgba(0,0,0,0.18); color:#6b7280; font-size:13px;
          }
          .ofh-pop summary::-webkit-details-marker { display:none; }
          .ofh-pop .ofh-card {
            margin-top:6px; background:#fff; border:1px solid rgba(0,0,0,0.1);
            box-shadow:0 2px 10px rgba(0,0,0,0.06); border-radius:6px; padding:8px 10px;
            font-size:0.875rem; color:#374151; max-width:360px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    safe_title = title_text.replace("<","&lt;").replace(">","&gt;")
    st.markdown(
        f"""
        <h3>
          {safe_title}
          <details class='ofh-pop'>
            <summary aria-label='How is it calculated'>i</summary>
            <div class='ofh-card'>How is it calculated - count of unique associates with a clock and/or scan event</div>
          </details>
        </h3>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------
# Helper: On Floor header with custom HTML/CSS popover
# ---------------------------
def render_on_floor_header_with_popover(title_text: str, body_text: str):
    st.markdown(
        """
        <style>
          details.ofh-info-inline { position:relative; display:inline-block; margin-left:8px; }
          details.ofh-info-inline > summary {
            list-style:none; display:inline-flex; align-items:center; justify-content:center;
            width:16px; height:16px; border-radius:50%; border:1px solid rgba(0,0,0,0.18);
            font-size:11px; font-weight:600; color:#6b7280; background:#fff; cursor:pointer; user-select:none;
            padding:0; margin:0;
          }
          details.ofh-info-inline > summary::-webkit-details-marker { display:none; }
          details.ofh-info-inline .ofh-pop { position:absolute; top:22px; left:0; z-index:50; background:#fff;
            border:1px solid rgba(0,0,0,0.12); box-shadow:0 8px 24px rgba(0,0,0,0.12);
            border-radius:8px; padding:10px 12px; min-width:260px; max-width:360px; font-size:0.875rem; line-height:1.3; color:#111827; display:none; }
          details.ofh-info-inline[open] .ofh-pop { display:block; }
          details.ofh-info-inline .ofh-pop:before { content:""; position:absolute; top:-6px; left:10px; width:10px; height:10px; transform:rotate(45deg);
            background:#fff; border-left:1px solid rgba(0,0,0,0.12); border-top:1px solid rgba(0,0,0,0.12); }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Render heading and inline icon in one block. Use native h3 to match subheader size/weight.
    safe_title = title_text.replace("<","&lt;").replace(">","&gt;")
    st.markdown(
        f"""
        <h3 style='margin:0 0 6px 0;'>
          {safe_title}
          <details class='ofh-info-inline' aria-label='How this is calculated'>
            <summary aria-label='Open calculation info' title='How it’s calculated'>i</summary>
            <div class='ofh-pop'>{body_text}</div>
          </details>
        </h3>
        """,
        unsafe_allow_html=True,
    )

# Auto-refresh every N seconds (keeps code simple for v1)
REFRESH_SEC = 5
# Removed per request: top-level fixed timestamp

# ---------------------------
# TOP: DEPARTMENT CARDS (On Floor by Hiring Department)
# ---------------------------
def render_department_cards(df: pd.DataFrame) -> None:
    """Render a horizontal row of cards showing On Floor counts by hiring department.

    Uses df columns: associate_id, job_department, on_floor.
    """
    try:
        on_floor_df = df[df["on_floor"]].copy()
    except Exception:
        on_floor_df = df.copy()

    if on_floor_df.empty:
        return

    card_counts = (
        on_floor_df.fillna({"job_department": "—"})
        .groupby("job_department")["associate_id"].nunique()
        .sort_values(ascending=False)
        .reset_index()
    )

    now_time = datetime.now().strftime("%H:%M:%S")

    # Section header with total on-floor headcount in brackets (match subheader style)
    total_on_floor = int(on_floor_df["associate_id"].nunique())
    # Render dynamic title with inline micro-info icon
    _window = globals().get("FLOOR_WINDOW_MIN", None)
    _win_txt = f" within the last **{_window} minutes**" if _window else ""
    info_md = (
        "**What this shows**  \n"
        "Count of **unique associates** who have an **active clock and/or scan event**"
        f"{_win_txt}.  \n\n"
        "*Notes:* Clock = timekeeping event; Scan = area/position scan. Badge tests and events outside the window are excluded."
    )
    # Replace single header line with dynamic title + inline micro popover
    render_on_floor_header_with_popover(
        title_text=f"On Floor Headcount ({total_on_floor})",
        body_text="How is it calculated - count of unique associates with a clock and/or scan event",
    )
    st.caption("Last updated at 15 Oct, 7:32:13am")

    # Lightweight CSS for horizontal cards with scroll
    st.markdown(
        """
        <style>
        .dept-section-header { font-weight:600; font-size:1.2rem; margin:0 0 6px 0; }
        .dept-cards { display:flex; gap:12px; overflow-x:auto; padding:6px 2px 10px 2px; margin: -6px 0 6px 0; }
        .dept-card { min-width: 180px; background:#ffffff; border-radius:8px; box-shadow:0 1px 6px rgba(0,0,0,0.08); padding:12px 14px; }
        .dept-title { font-weight:600; font-size:0.95rem; margin:0 0 4px 0; }
        .dept-count { font-size:28px; font-weight:700; margin:0 0 6px 0; }
        /* per-card caption removed; timestamp shown under section header */
        </style>
        """,
        unsafe_allow_html=True,
    )

    cards_html_parts = ["<div class='dept-cards'>"]
    for _, row in card_counts.iterrows():
        dept = str(row["job_department"])  # Hiring department
        cnt = int(row["associate_id"])     # Unique associates on floor
        cards_html_parts.append(
            f"<div class='dept-card'>"
            f"<div class='dept-title'>{dept}</div>"
            f"<div class='dept-count'>{cnt}</div>"
            f"</div>"
        )
    cards_html_parts.append("</div>")
    st.markdown("".join(cards_html_parts), unsafe_allow_html=True)
st_autorefresh = st.experimental_rerun if False else None
_ = getattr(st, "data_editor", getattr(st, "experimental_data_editor", None))  # noqa: just to ensure Streamlit >=1.31

# Optional: simple auto-refresh
_set_query_param_t()
time.sleep(REFRESH_SEC * 0.0)  # no-op; keep it simple. Use st_autorefresh if you prefer.

# ---------------------------
# 1) DATA LOADING FROM CSV
# ---------------------------

SCANNED_SOURCES = {"Badgr", "HighJump", "Pick to Light"}

# Mapping of WORK_DEPARTMENT to Work Department Group for reporting
WORK_DEPT_GROUP_MAP = {
    "Admin": "Admin",
    "HR/Admin": "Admin",
    "Assembly": "Production",
    "Kitting": "Production",
    "Prep": "Production",
    "Site Support": "Production",
    "Warehouse": "Warehouse",
    "Shipping": "Shipping",
    "FSQ": "Quality",
}

@st.cache_data(ttl=30)
def load_associates_from_csv(csv_path: str = "Scan2Job Realtime Sample Data.csv") -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Ensure expected columns exist
    # New CSV schema: ASSOCIATE_ID, ASSOCIATE_NAME, SHIFT_TYPE, JOB_DEPARTMENT, SOURCE, WORK_DEPARTMENT,
    # WORK_POSITION, LINE, BAY, LOCATION, START_TIME_LOCAL
    # We only require the fields the app uses.
    expected_cols = {
        "ASSOCIATE_ID",
        "ASSOCIATE_NAME",
        "SHIFT_TYPE",
        "JOB_DEPARTMENT",
        "SOURCE",
        "WORK_DEPARTMENT",
        "WORK_POSITION",
        "START_TIME_LOCAL",
    }
    missing = expected_cols.difference(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {sorted(missing)}")
    df["START_TIME_LOCAL"] = pd.to_datetime(df["START_TIME_LOCAL"], errors="coerce")

    # Latest record per associate (for stable department display)
    df_sorted = df.sort_values(["ASSOCIATE_ID","START_TIME_LOCAL"]).dropna(subset=["ASSOCIATE_ID"])  # type: ignore
    latest_idx = df_sorted.groupby("ASSOCIATE_ID")["START_TIME_LOCAL"].idxmax()
    latest_cols = [
        "ASSOCIATE_ID","ASSOCIATE_NAME","JOB_DEPARTMENT","WORK_DEPARTMENT","WORK_POSITION","START_TIME_LOCAL","SHIFT_TYPE"
    ]
    if "LINE" in df_sorted.columns:
        latest_cols.append("LINE")
    latest = df_sorted.loc[latest_idx, latest_cols].rename(columns={
        "ASSOCIATE_ID":"associate_id",
        "ASSOCIATE_NAME":"associate_name",
        "JOB_DEPARTMENT":"job_department",
        "WORK_DEPARTMENT":"work_department",
        "WORK_POSITION":"work_position",
        "START_TIME_LOCAL":"last_activity_ts",
        "SHIFT_TYPE":"shift_type",
        "LINE":"line",
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

    # Compute 'clocked_in' using full event history: latest Workday 'Punch in' with no later 'Punch out'
    try:
        src_lower = df["SOURCE"].astype(str).str.casefold()
        pos_lower = df["WORK_POSITION"].astype(str).str.casefold()
        wd_df = df[src_lower.eq("workday")].copy()
        wd_df["START_TIME_LOCAL"] = pd.to_datetime(wd_df["START_TIME_LOCAL"], errors="coerce")
        punch_in_ts = (
            wd_df[pos_lower[wd_df.index].eq("punch in")]
            .groupby("ASSOCIATE_ID")["START_TIME_LOCAL"].max()
        )
        punch_out_ts = (
            wd_df[pos_lower[wd_df.index].eq("punch out")]
            .groupby("ASSOCIATE_ID")["START_TIME_LOCAL"].max()
        )
        union_idx = punch_in_ts.index.union(punch_out_ts.index)
        in_ts = punch_in_ts.reindex(union_idx)
        out_ts = punch_out_ts.reindex(union_idx)
        clocked_series = in_ts.notna() & (out_ts.isna() | (in_ts > out_ts))
        clocked_ids = set(clocked_series[clocked_series].index.astype(str))
        people_df["clocked_in"] = people_df["associate_id"].astype(str).isin(clocked_ids)
    except Exception:
        people_df["clocked_in"] = False
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

    # Freshness is static for this static dataset
    if title == "On Floor":
        freshness_text = "30s"
    elif title == "Scanned In":
        freshness_text = "1m"
    else:
        freshness_text = "1m"

    # Events note (no color signal; visually deemphasized later)
    if title == "On Floor":
        events = "Clock, Scan"
    elif title == "Scanned In":
        events = "Scan"
    else:
        events = "Clock, Scan"

    # Single expander header; place secondary freshness note inside the content
    header_text = f"{title} — {total_associates}"
    with st.expander(header_text, expanded=False):
        st.markdown(
            f"<div style='font-size:0.85rem; color:#6b7280; margin-bottom:6px'>Freshness {freshness_text} · Events: {events}</div>",
            unsafe_allow_html=True,
        )
        group_col = "job_department"
        if group_col in subset.columns:
            breakdown_df = (
                subset.fillna({group_col: "—"})
                .groupby(group_col)["associate_id"].nunique()
                .sort_values(ascending=False)
                .reset_index()
            )
            breakdown_df.columns = ["Hiring Department", "Associates"]
        else:
            breakdown_df = pd.DataFrame({"Hiring Department": [], "Associates": []})
        st.dataframe(breakdown_df, use_container_width=True, hide_index=True)

# No legacy clock/scan rules; CSV defines the categories

# ---------------------------
# 2) READ / TRANSFORM
# ---------------------------
people_df = load_associates_from_csv()
# NEW: Render department cards at top
render_department_cards(people_df)

# ---------------------------
# MIDDLE: SCANNED / NON-SCANNED BREAKDOWNS (NEW SECTION)
# ---------------------------
def render_mid_breakdowns(df: pd.DataFrame) -> None:
    # Ignore Compliance and Time Card punch work departments
    work_dept_series = df.get("work_department", pd.Series([None] * len(df))).astype(str)
    work_dept_clean = work_dept_series.str.strip()
    ignore_mask = work_dept_clean.str.casefold().eq("compliance") | work_dept_clean.str.lower().str.contains("time card")

    # Mapping from Work Department -> Job Department (group)
    map_work_to_job = {
        "Production": "Production",
        "Warehouse": "Warehouse",
        "Fulfillment Training": "Fulfillment Training",
        "FSQ": "Quality",
        "Sanitation": "Sanitation",
        "Shipping": "Shipping",
        # Sub-departments that belong to Production
        "Assembly": "Production",
        "Kitting": "Production",
        "Site Support": "Production",
        # Common admin sub-departments treated as Other at the job level
        "Admin": "Other",
        "HR/Admin": "Other",
    }
    # Sub-departments for expansion (by Job Department)
    subdepts_by_job = {
        "Production": ["Assembly", "Kitting", "Site Support"],
        "Other": ["Admin", "HR/Admin"],
    }

    lcol, rcol = st.columns([1, 1])

    # LEFT: Scanned-In Breakdown with per-row drilldown to sub-departments (work departments)
    with lcol:
        scanned_df = df[(df.get("scanned_in", False)) & (~ignore_mask)].copy()
        scanned_total = int(scanned_df["associate_id"].nunique()) if not scanned_df.empty else 0
        render_on_floor_header_with_popover(
            title_text=f"Scanned-in Breakdown ({scanned_total})",
            body_text="Count of associates with a scan event via Badgr, Pick2Light, HighJump",
        )
        st.caption("Last updated at 15 Oct, 7:32:13am")
        if scanned_df.empty:
            st.info("No scanned-in associates.")
        else:
            scanned_df["work_department_clean"] = scanned_df["work_department"].astype(str).str.strip()
            scanned_df["job_group"] = scanned_df["work_department_clean"].map(map_work_to_job).fillna("Other")
            # Order and ensure presence of all departments shown in On Floor Headcount
            try:
                onfloor_order = (
                    df[df["on_floor"]]
                    .fillna({"job_department": "—"})
                    .groupby("job_department")["associate_id"].nunique()
                    .sort_values(ascending=False)
                    .index
                    .tolist()
                )
            except Exception:
                onfloor_order = []

            counts_df = (
                scanned_df.groupby("job_group")["associate_id"].nunique().reset_index()
                .rename(columns={"job_group": "Department", "associate_id": "Associates"})
            )
            if onfloor_order:
                ordered_depts = list(onfloor_order)
                if "Other" not in ordered_depts:
                    ordered_depts.append("Other")
                template_df = pd.DataFrame({"Department": ordered_depts})
                by_group = template_df.merge(counts_df, on="Department", how="left").fillna({"Associates": 0})
            else:
                present = [d for d in counts_df["Department"].astype(str).unique().tolist() if d != "Other"]
                present.sort()
                ordered_depts = present + ["Other"]
                template_df = pd.DataFrame({"Department": ordered_depts})
                by_group = template_df.merge(counts_df, on="Department", how="left").fillna({"Associates": 0})

            # Render rows: Department → Sub-department (work_department) → Line
            for _, row in by_group.iterrows():
                dept = str(row["Department"]) 
                cnt = int(row["Associates"]) 
                valid_subs = subdepts_by_job.get(dept, [])
                sub = scanned_df[(scanned_df["job_group"] == dept) & (scanned_df["work_department_clean"].isin(valid_subs))]
                with st.expander(f"{dept} — {cnt}", expanded=False):
                    if sub.empty:
                        # No sub-departments: show department summary only
                        st.dataframe(pd.DataFrame({"Sub-Department": [dept], "Associates": [cnt]}), use_container_width=True, hide_index=True)
                    else:
                        # Header at the department level for the sub-department listings
                        st.markdown("**Sub-Department**")
                        sub_counts = (
                            sub.fillna({"work_department_clean": "—"})
                            .groupby("work_department_clean")["associate_id"].nunique()
                            .sort_values(ascending=False)
                            .reset_index()
                            .rename(columns={"work_department_clean": "Sub-Department", "associate_id": "Associates"})
                        )
                        # Iterate sub-departments
                        for _, srow in sub_counts.iterrows():
                            sname = str(srow["Sub-Department"]) 
                            scount = int(srow["Associates"]) 
                            sub_df = sub[sub["work_department_clean"] == sname]
                            # Determine if there are any valid line values
                            line_series = sub_df.get("line")
                            has_line = False
                            if line_series is not None:
                                ls = line_series.astype(str).str.strip()
                                if len(ls):
                                    has_line = ls.ne("") & ls.ne("None") & ls.ne("—")
                                    has_line = bool(has_line.any())
                                else:
                                    has_line = False
                            if not has_line:
                                # Flat row: no nested expander
                                st.markdown(f"**{sname}** — {scount}")
                            else:
                                with st.expander(f"{sname} — {scount}", expanded=False):
                                    line_table = (
                                        sub_df.assign(line=sub_df.get("line").astype(str).str.strip().replace({"": "—", "None": "—"}))
                                        .groupby("line")["associate_id"].nunique()
                                        .sort_values(ascending=False)
                                        .reset_index()
                                        .rename(columns={"associate_id": "Associates", "line": "Line"})
                                    )
                                    st.dataframe(line_table, use_container_width=True, hide_index=True)

    # RIGHT: Non-Scanned Breakdown (simple table by job department)
    with rcol:
        non_scanned_mask = df.get("on_floor", False) & (~df.get("scanned_in", False))
        non_scanned_df = df[non_scanned_mask].copy()
        non_scanned_total = int(non_scanned_df["associate_id"].nunique()) if not non_scanned_df.empty else 0
        render_on_floor_header_with_popover(
            title_text=f"Non-Scanned Breakdown ({non_scanned_total})",
            body_text="Count of associates with a clock-in but no active scan event. Note: Clock-data has a minimum of 15 min latency due to Workday. Expect non-scanned associates to only start populating in 20 mins from start of the shift",
        )
        st.caption("Last updated at 15 Oct, 7:32:13am")
        if non_scanned_df.empty:
            st.info("No non-scanned associates.")
        else:
            table = (
                non_scanned_df.fillna({"job_department": "—"})
                .groupby("job_department")["associate_id"].nunique()
                .sort_values(ascending=False)
                .reset_index()
                .rename(columns={"job_department": "Job Department", "associate_id": "Associates"})
            )
            st.dataframe(table, use_container_width=True, hide_index=True)

render_mid_breakdowns(people_df)
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

# LEFT and RIGHT sections intentionally left empty per request to remove previous sections

    

# ---------------------------
# 4) BOTTOM: PEOPLE TABLE (detail)
# ---------------------------
st.markdown("---")
filtered = people_df.copy()
if privacy:
    filtered = filtered.assign(associate_name="—")
pretty = filtered[[
    "associate_id","associate_name","job_department","shift_type","clocked_in","scanned_in","work_department","work_position","last_activity_ts"
]].rename(columns={
    "associate_id":"Id",
    "associate_name":"Name",
    "job_department":"Hiring Department",
    "shift_type":"Shift Type",
    "clocked_in":"Clocked In",
    "scanned_in":"Scanned In",
    "work_department":"Work Department",
    "work_position":"Work Position",
    "last_activity_ts":"Last Activity Timestamp",
})

# Title + compact filter icon (top row)
title_left, title_right = st.columns([1, 1])
title_placeholder = title_left.empty()
with title_right:
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


# Dynamic title with count inline with filters + info icon
render_on_floor_header_with_popover(
    title_text=f"Latest Associate Activity ({len(filtered_pretty)})",
    body_text="Placeholder: explanation of Latest Associate Activity.",
)
st.caption("Last updated at 15 Oct, 7:32:13am")

# New controls row: search, quick toggles, department dropdown, clear button
# If a clear was requested in the previous run, reset widget states BEFORE creating widgets
if st.session_state.get("__do_clear_filters", False):
    st.session_state["search_q"] = ""
    st.session_state["flt_not_scanned"] = False
    st.session_state["flt_not_clocked"] = False
    st.session_state["dept_pick"] = "(any)"
    st.session_state["__do_clear_filters"] = False

ctrl_search_col, ctrl_toggles_col, ctrl_dept_col, ctrl_clear_col = st.columns([3, 5, 3, 2])
with ctrl_search_col:
    search_q = st.text_input(
        "Search",
        value=st.session_state.get("search_q", ""),
        key="search_q",
        placeholder="Search ID, Name, or keyword…",
    )
with ctrl_toggles_col:
    tg1, tg2 = st.columns(2)
    with tg1:
        flt_not_scanned = st.toggle("Not Scanned-In", value=st.session_state.get("flt_not_scanned", False), key="flt_not_scanned")
    with tg2:
        flt_not_clocked = st.toggle("Not Clocked-In", value=st.session_state.get("flt_not_clocked", False), key="flt_not_clocked")
with ctrl_dept_col:
    dept_options = ["(any)"] + sorted(pretty["Hiring Department"].dropna().astype(str).unique().tolist())
    dept_pick = st.selectbox("Department", options=dept_options, index=0, key="dept_pick")
with ctrl_clear_col:
    if st.button("Clear All Filters"):
        # Defer clearing to the next run to avoid Streamlit state write errors
        st.session_state["__do_clear_filters"] = True
        st.rerun()

# Apply new controls to the table
if search_q:
    mask_any = filtered_pretty.astype(str).apply(lambda c: c.str.contains(search_q, case=False, na=False))
    filtered_pretty = filtered_pretty[mask_any.any(axis=1)]

if flt_not_scanned:
    filtered_pretty = filtered_pretty[filtered_pretty["Scanned In"] == False]

if flt_not_clocked:
    filtered_pretty = filtered_pretty[filtered_pretty["Clocked In"] == False]

if dept_pick != "(any)":
    filtered_pretty = filtered_pretty[filtered_pretty["Hiring Department"] == dept_pick]

st.dataframe(filtered_pretty.sort_values(["Hiring Department","Name"]), use_container_width=True, hide_index=True)

