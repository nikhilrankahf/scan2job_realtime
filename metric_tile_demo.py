from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import pandas as pd
import streamlit as st


def _inject_metric_tile_css() -> None:
    """Inject minimal CSS for card-like tiles and large totals."""
    st.markdown(
        """
        <style>
        .metric-card { background: #ffffff; border-radius: 10px; box-shadow: 0 1px 8px rgba(0,0,0,0.08); padding: 16px; margin-bottom: 16px; }
        .metric-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
        .metric-title { font-weight: 700; font-size: 1rem; margin: 0; }
        .big-total { font-size: 48px; font-weight: 600; line-height: 1.1; margin: 6px 0 10px 0; }
        .metric-updated { text-align: right; color: #6b7280; font-size: 0.8rem; margin-top: 6px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _compute_flags(
    df: pd.DataFrame,
    floor_window_min: int,
    inpos_window_min: int,
) -> pd.DataFrame:
    """Return a copy of df with boolean flags for the three metrics.

    Expects columns: associate_id, has_clock, has_scan, last_activity_ts (UTC), scanned_department (optional).
    """
    now = datetime.now(timezone.utc)
    out = df.copy()

    if "scanned_department" not in out.columns:
        out["scanned_department"] = pd.Series([None] * len(out))

    out["last_activity_ts"] = pd.to_datetime(out["last_activity_ts"], utc=True)

    on_floor = (
        (out["has_clock"].fillna(False) | out["has_scan"].fillna(False))
        & ((now - out["last_activity_ts"]) <= timedelta(minutes=floor_window_min))
    )
    in_position = (
        out["scanned_department"].notna()
        & ((now - out["last_activity_ts"]) <= timedelta(minutes=inpos_window_min))
    )

    out["on_floor"] = on_floor
    out["in_position"] = in_position
    out["unscanned"] = on_floor & (~in_position)
    return out


def metric_tile(
    df: pd.DataFrame,
    title: str,
    group_options: Optional[Dict[str, str]] = None,
    default_group: str = "Job Department",
    floor_window_min: int = 10,
    inpos_window_min: int = 5,
) -> None:
    """Render a reusable metric tile card.

    - title: one of "On Floor" | "Scanned In" | "Unscanned"
    - group_options: mapping of display label -> column name in df
      default: {"Job Department": "job_department", "Sub-Department": "sub_department"}
    """
    _inject_metric_tile_css()

    if group_options is None:
        group_options = {"Job Department": "job_department", "Sub-Department": "sub_department"}

    filtered = _compute_flags(df, floor_window_min=floor_window_min, inpos_window_min=inpos_window_min)

    title_to_flag = {
        "On Floor": "on_floor",
        "Scanned In": "in_position",
        "Unscanned": "unscanned",
    }
    if title not in title_to_flag:
        raise ValueError("title must be one of 'On Floor' | 'Scanned In' | 'Unscanned'")

    flag_col = title_to_flag[title]
    subset = filtered[filtered[flag_col]] if flag_col in filtered.columns else filtered.iloc[0:0]

    # Unique associates for the total
    total_associates = int(subset["associate_id"].nunique())

    # Card begin
    st.markdown("<div class='metric-card'>", unsafe_allow_html=True)

    # Header row: title (left), breakdown selector (right)
    header_cols = st.columns([1, 1])
    with header_cols[0]:
        st.markdown(f"<div class='metric-header'><div class='metric-title'>{title}</div></div>", unsafe_allow_html=True)
    with header_cols[1]:
        group_display_names = list(group_options.keys())
        default_index = group_display_names.index(default_group) if default_group in group_display_names else 0
        chosen_display = st.selectbox(
            "Breakdown",
            options=group_display_names,
            index=default_index,
            key=f"metric_tile_breakdown_{title}",
        )

    # Big total number
    st.markdown(f"<div class='big-total'>{total_associates}</div>", unsafe_allow_html=True)

    # Breakdown table
    group_col = group_options[chosen_display]
    if group_col not in subset.columns:
        breakdown_df = pd.DataFrame({chosen_display: [], "Associates": []})
    else:
        breakdown_df = (
            subset.groupby(group_col)["associate_id"].nunique().sort_values(ascending=False).reset_index()
        )
        breakdown_df.columns = [chosen_display, "Associates"]

    with st.expander("Breakdown details"):
        st.dataframe(breakdown_df, use_container_width=True, hide_index=True)

    # Last updated caption
    now_local = datetime.now().strftime("%H:%M:%S")
    st.markdown(f"<div class='metric-updated'>Last updated {now_local}</div>", unsafe_allow_html=True)

    # Card end
    st.markdown("</div>", unsafe_allow_html=True)


def _build_sample_df() -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    rows = [
        # id, name, job_dept, sub_dept, has_clock, has_scan, last_ts, scanned_dept
        ("A100", "Jane Doe", "Production", "Kitting", True, True,  now - timedelta(minutes=2),  "Kitting"),
        ("A101", "Sam Lee",  "Production", "Assembly", True, False, now - timedelta(minutes=4),  None),
        ("A102", "Li Wang",  "Warehouse",  "Inventory", True, True,  now - timedelta(minutes=3),  "Inventory"),
        ("A103", "Alex Kim",  "Shipping",   "Loading",  True, True,  now - timedelta(minutes=6),  "Loading"),
        ("A104", "Mia K",    "Shipping",   "Loading",  True, False, now - timedelta(minutes=12), None),
        ("A105", "Ola I",    "Warehouse",  "Putaway",  True, False, now - timedelta(minutes=1),  None),
        ("A106", "Nina T",   "Production", "Labeling", True, True,  now - timedelta(minutes=4),  "Labeling"),
        ("A107", "Raj P",    "Production", "Prep",     False, True, now - timedelta(minutes=2),  "Prep"),
        ("A108", "Ana S",    "Warehouse",  "Replenishment", True, False, now - timedelta(minutes=7), None),
        ("A109", "Tim R",    "Production", "Assembly", True, True,  now - timedelta(minutes=15), "Assembly"),
    ]
    df = pd.DataFrame(rows, columns=[
        "associate_id","associate_name","job_department","sub_department",
        "has_clock","has_scan","last_activity_ts","scanned_department"
    ])
    return df


def _demo() -> None:
    st.set_page_config(page_title="Metric Tile Demo", layout="wide")
    st.title("Metric Tile Demo")
    st.caption("Reusable tiles with per-metric filtering and breakdowns")

    df = _build_sample_df()

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_tile(df, title="On Floor")
    with col2:
        metric_tile(df, title="Scanned In")
    with col3:
        metric_tile(df, title="Unscanned")


if __name__ == "__main__":
    _demo()


