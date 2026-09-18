"""
CDTA Route 12 — Automatic Passenger Counter Dashboard
CIVL 6962 · Homework 1 — what counts

Data: stop-level Automatic Passenger Counter (APC) records for CDTA Route 12
(Albany <-> Crossgates Mall, Guilderland NY, via Washington Ave / UAlbany).
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="CDTA Route 12 — What Counts", layout="wide")

# Custom CSS to increase sidebar font size
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        font-size: 1.15rem;
    }
    [data-testid="stSidebar"] .stRadio label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
        font-size: 1.1rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DATA_DIR = Path(__file__).parent / "data"

METRIC_OPTIONS = {
    "Boardings": ("psngr_in", "passengers boarding", False),
    "Alightings": ("psngr_out", "passengers alighting", False),
    "Onboard load": ("psngr_load", "passengers onboard", False),
    "Departure delay": ("delay_sec", "seconds late (actual \u2212 scheduled)", True),
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# ----------------------------------------------------------------------------
# Cached loaders
# ----------------------------------------------------------------------------

@st.cache_data
def load_raw_data(data_dir: str) -> pd.DataFrame:
    """Read and concatenate every apc4rpi_*.csv in data/.
    
    Caching this is worth it because every extra day of service adds another
    file to parse and concatenate; without caching, Streamlit would re-read
    and re-parse the entire multi-file dataset on every slider tick even
    though the files on disk never change while the app is running.
    """
    files = sorted(Path(data_dir).glob("apc4rpi_*.csv"))
    if not files:
        return pd.DataFrame()

    frames = [pd.read_csv(f) for f in files]
    df = pd.concat(frames, ignore_index=True)

    df["service_date"] = pd.to_datetime(df["opd_date"], format="%m/%d/%Y")
    df["stop_hour"] = df["act_arr_time_hhmmss"].str.slice(0, 2).astype(int)
    df["doors_opened"] = df["doors"].eq("doors opened")
    df["weekday_name"] = df["service_date"].dt.day_name()
    df["implied_schedule"] = df["weekday_name"].apply(
        lambda d: "Weekday" if d in WEEKDAYS else d
    )
    df["schedule_mismatch"] = df["implied_schedule"] != df["schedule"]

    # Normalize stop position so every trip reads left-to-right on a chart,
    # regardless of which way pattern_idx happens to count for that direction.
    max_idx_by_dir = df.groupby("direction")["pattern_idx"].transform("max")
    df["stop_order"] = max_idx_by_dir - df["pattern_idx"]

    # Departure delay (actual minus scheduled), only defined at the ~30% of
    # stops that are official timepoints (where nom_dep_time is recorded).
    df["delay_sec"] = df["act_dep_time"] - df["nom_dep_time"]
    df["dep_datetime"] = df["service_date"] + pd.to_timedelta(df["act_dep_time"], unit="s")

    # t=0 is the earliest actual departure in the whole loaded dataset, not
    # midnight — service starts well after midnight, so anchoring to
    # midnight would waste most of the axis on hours nothing runs.
    t0 = df["dep_datetime"].min()
    t0_seconds_of_day = t0.hour * 3600 + t0.minute * 60 + t0.second

    # "Hour of day": cyclical, wraps every 24h, relative to t0's time-of-day —
    # bucket 0 covers the hour service actually starts each day.
    df["hour_of_day_bucket"] = (
        (df["act_dep_time"] - t0_seconds_of_day) % 86400 // 3600
    ).astype(int)

    # "Hour of week": cyclical, wraps every 168h, relative to the single
    # global t0 — bucket 0 covers the hour service first started in the
    # whole loaded dataset, and buckets keep counting across days so
    # weekday-to-weekday differences stay visible.
    elapsed_hours = (df["dep_datetime"] - t0).dt.total_seconds() / 3600
    df["hour_of_week_bucket"] = (elapsed_hours % 168).astype(int)

    return df


@st.cache_data
def schedule_calendar(data_dir: str) -> pd.DataFrame:
    """One row per service day: calendar weekday vs. the schedule CDTA
    actually ran that day. Cached separately from load_raw_data because it
    only needs to change when new files are added, never when a control
    (date range, direction, metric) changes.
    """
    df = load_raw_data(data_dir)
    if df.empty:
        return df
    cols = ["service_date", "weekday_name", "schedule", "schedule_mismatch"]
    return df[cols].drop_duplicates().sort_values("service_date").reset_index(drop=True)


# ----------------------------------------------------------------------------
# Load data & setup title
# ----------------------------------------------------------------------------

df = load_raw_data(str(DATA_DIR))

st.title("CDTA Route 12 — Automatic Passenger Counter Dashboard")
st.caption(
    "Stop-level boarding, alighting and load counts from CDTA's onboard "
    "Automatic Passenger Counters, Route 12 (downtown Albany \u2194 Crossgates "
    "Mall, Guilderland NY, via Washington Ave and the University at Albany)."
)

if df.empty:
    st.error(
        f"No data files found in `{DATA_DIR}`. Add one or more "
        "`apc4rpi_*.csv` extracts to the `data/` folder and rerun."
    )
    st.stop()

cal = schedule_calendar(str(DATA_DIR))

# ----------------------------------------------------------------------------
# Sidebar Navigation
# ----------------------------------------------------------------------------

st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Charts", "Dataset & provenance", "Blind spots"],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.caption(
    f"Loaded {df['service_date'].nunique()} service day(s), "
    f"{len(df):,} stop-events, {df['trip_id'].nunique()} trips."
)

# ----------------------------------------------------------------------------
# Main Page Controls & Filtering (Active when Charts page is selected)
# ----------------------------------------------------------------------------

min_date = df["service_date"].min().date()
max_date = df["service_date"].max().date()
direction_options = sorted(df["direction"].unique())

if page == "Charts":
    st.subheader("Dashboard Controls")
    control_col1, control_col2, control_col3 = st.columns(3)

    with control_col1:
        if min_date == max_date:
            date_range = (min_date, max_date)
            st.info(f"Only one service day loaded ({min_date}).")
        else:
            date_range = st.slider(
                "Service date range",
                min_value=min_date,
                max_value=max_date,
                value=(min_date, max_date),
                help="Filters which service days' stop-events go into every chart.",
            )

    with control_col2:
        directions = st.multiselect(
            "Direction",
            options=direction_options,
            default=direction_options,
            help="East and West are different, mostly non-overlapping sets of stops.",
        )

    with control_col3:
        metric_label = st.selectbox(
            "Metric",
            list(METRIC_OPTIONS.keys()),
            help="Changes which column — and which of the two top charts — is plotted.",
        )

    metric_col, metric_unit, is_delay = METRIC_OPTIONS[metric_label]

    if is_delay:
        delay_agg_label = st.selectbox(
            "Delay aggregation",
            ["Hour of day", "Hour of week"],
            help=(
                "'Hour of day' averages every day in the selection onto one 24h "
                "cycle; 'Hour of week' keeps a 168h cycle so different days "
                "stay distinguishable. Both start counting at t=0 = the "
                "earliest actual departure in the loaded data."
            ),
        )
        delay_bucket_col = "hour_of_day_bucket" if delay_agg_label == "Hour of day" else "hour_of_week_bucket"
    else:
        delay_agg_label = "Hour of day"
        delay_bucket_col = "hour_of_day_bucket"

    st.divider()
else:
    date_range = (min_date, max_date)
    directions = direction_options
    metric_label = list(METRIC_OPTIONS.keys())[0]
    metric_col, metric_unit, is_delay = METRIC_OPTIONS[metric_label]
    delay_agg_label = "Hour of day"
    delay_bucket_col = "hour_of_day_bucket"

# Apply filters (cheap — plain pandas, no need to cache)
mask = (
    (df["service_date"].dt.date >= date_range[0])
    & (df["service_date"].dt.date <= date_range[1])
    & (df["direction"].isin(directions))
)
fdf = df[mask]

if page == "Charts" and fdf.empty:
    st.warning("No stop-events match the current filters. Widen the date range or pick a direction.")
    st.stop()

# ----------------------------------------------------------------------------
# Page views (driven by sidebar navigation radio)
# ----------------------------------------------------------------------------

if page == "Charts":
    st.caption(
        f"Showing {len(fdf):,} stop-events \u00b7 {date_range[0]} to {date_range[1]} \u00b7 "
        f"direction(s): {', '.join(directions) if directions else 'none'}"
    )

    col1, col2 = st.columns(2)

    with col1:
        # .mean() skips NaNs automatically, so this works unchanged for
        # Departure delay too (only timepoint stops have a value).
        profile = (
            fdf.groupby(["stop_order", "direction"], as_index=False)[metric_col]
            .mean()
        )
        y_label = (
            f"Average delay per stop ({metric_unit})" if is_delay
            else f"Average {metric_unit} per stop"
        )
        fig1 = px.line(
            profile,
            x="stop_order",
            y=metric_col,
            color="direction",
            markers=True,
            labels={"stop_order": "Stop position along trip (0 = first stop)", metric_col: y_label},
            title=f"Average {metric_label.lower()} by stop position",
        )
        st.plotly_chart(fig1, width='stretch')

    with col2:
        if is_delay:
            # Delay isn't meaningfully "summed" by hour the way a passenger
            # count is, and it only exists at timepoints, so this chart
            # swaps to a stop x time-bucket heatmap instead of the bar
            # chart the other three metrics use.
            delay_df = fdf[fdf[metric_col].notna()]
            if delay_df.empty:
                st.info(
                    "None of the stops in the current selection are official "
                    "timepoints, so there's no scheduled time to measure "
                    "delay against. Widen the date range or direction filter."
                )
            else:
                max_stop = int(delay_df["stop_order"].max()) + 1
                max_bucket = int(delay_df[delay_bucket_col].max()) + 1
                bucket_axis_title = (
                    "Hours since first departure of the day (t=0)"
                    if delay_bucket_col == "hour_of_day_bucket"
                    else "Hours since first departure of the week (t=0)"
                )
                fig2 = px.density_heatmap(
                    delay_df,
                    x="stop_order",
                    y=delay_bucket_col,
                    z=metric_col,
                    histfunc="avg",
                    facet_col="direction",
                    nbinsx=max_stop,
                    nbinsy=max_bucket,
                    color_continuous_scale="RdBu_r",
                    color_continuous_midpoint=0,
                    labels={
                        "stop_order": "Stop position along trip (0 = first stop)",
                        delay_bucket_col: bucket_axis_title,
                        metric_col: "Average delay (sec)",
                    },
                    title=f"Average delay by stop, aggregated by {delay_agg_label.lower()}",
                )
                fig2.update_coloraxes(colorbar_title="Delay (sec)")
                # Plotly's default facet titles read "direction=East" /
                # "direction=West" — strip the column-name prefix so each
                # panel just says "East" / "West".
                fig2.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                # With two directions selected, faceting also repeats the
                # x-axis title under every panel — keep it on the first
                # (leftmost) panel only so it doesn't print twice.
                xaxis_keys = sorted(k for k in fig2.layout if k.startswith("xaxis"))
                for k in xaxis_keys[1:]:
                    fig2.layout[k].title.text = None
                st.plotly_chart(fig2, width='stretch')
                st.caption(
                    "Red = running late, blue = running early, relative to "
                    f"t=0. Built from only the {len(delay_df):,} of "
                    f"{len(fdf):,} stop-events in the current selection "
                    "that are official timepoints — see the missingness "
                    "blind spot below."
                )
        else:
            hourly = (
                fdf.groupby(["stop_hour", "direction"], as_index=False)[metric_col]
                .sum()
            )
            fig2 = px.bar(
                hourly,
                x="stop_hour",
                y=metric_col,
                color="direction",
                barmode="group",
                labels={
                    "stop_hour": "Hour of day (24h, local time)",
                    metric_col: f"Total {metric_unit}",
                },
                title=f"Total {metric_label.lower()} by hour of day",
            )
            st.plotly_chart(fig2, width='stretch')

    # Render dwell time distribution only when Departure delay is selected
    if is_delay:
        dwell = fdf[fdf["doors_opened"]]
        fig3 = px.histogram(
            dwell,
            x="act_dwelltime",
            nbins=40,
            labels={"act_dwelltime": "Dwell time at stop (seconds)"},
            title="Distribution of dwell time at stops where doors opened",
        )
        fig3.update_yaxes(title_text="Number of stop-events")
        st.plotly_chart(fig3, width='stretch')

elif page == "Dataset & provenance":
    st.subheader("Where this data comes from")
    st.markdown(
        f"""
- **Who collected it:** the Capital District Transportation Authority (CDTA),
  the public bus operator for the Albany–Schenectady–Troy, NY region.
- **Where:** CDTA Route 12, running between downtown Albany and Crossgates
  Mall in Guilderland, NY, via Washington Avenue and the University at
  Albany campus. Stop-level records exist for {df['point_code'].nunique()}
  distinct stops across both directions.
- **When:** this deployment has {df['service_date'].nunique()} service day(s)
  loaded, {min_date} through {max_date}. CDTA/RPI extracts cover more days
  than are bundled in this repository — this is a subset chosen for size,
  not the full available record.
- **With what instrument:** onboard Automatic Passenger Counters (APC) —
  door-mounted sensors (typically infrared beam-break or optical counters)
  that register each boarding and alighting event and tie it to the
  vehicle's GPS/AVL position, producing a stop-by-stop `psngr_in` /
  `psngr_out` / `psngr_load` record for every trip. The exact APC hardware
  model is not stated in the extract itself. The filename prefix
  (`apc4rpi`) suggests this particular file was pulled for an RPI course/
  research use; the underlying counts are CDTA's operational APC data.
        """
    )

    st.subheader("Columns used in this dashboard")
    st.markdown(
        """
| Column | Meaning |
|---|---|
| `opd_date` / `day_of_week` | Calendar date and weekday of service |
| `schedule` | Service pattern actually operated (Weekday / Saturday / Sunday) |
| `direction` | East or West along Route 12 |
| `trip_id` | Unique identifier for one bus trip |
| `point_code` / `point_name` | Stop identifier and name |
| `psngr_in` / `psngr_out` | Boardings / alightings recorded at that stop |
| `psngr_load` | Passengers onboard after that stop |
| `act_arr_time_hhmmss` | Actual arrival time (clock time) at that stop |
| `act_dwelltime` | Seconds the bus was stopped there |
| `doors` | Whether the doors opened at that stop |
        """
    )

    st.subheader("Current selection (first 200 rows)")
    st.dataframe(
        fdf[
            [
                "service_date", "direction", "trip_id", "point_name",
                "psngr_in", "psngr_out", "psngr_load",
                "act_arr_time_hhmmss", "act_dwelltime", "doors",
            ]
        ].head(200),
        width='stretch',
    )

elif page == "Blind spots":
    st.subheader("Three ways this dashboard could mislead you")

    mismatched = cal[cal["schedule_mismatch"]]
    missing_pct = df["nom_arr_time"].isna().mean() * 100
    max_load = int(df["psngr_load"].max())

    st.markdown("**1. Provenance — the weekday name is not the schedule that ran**")
    if not mismatched.empty:
        rows = ", ".join(
            f"{r.service_date.date()} ({r.weekday_name} calendar day, "
            f"{r.schedule} schedule)"
            for r in mismatched.itertuples()
        )
        st.markdown(
            f"In the currently loaded data, {len(mismatched)} service day(s) ran a "
            f"schedule that does not match their calendar weekday: {rows}. "
            "July 4, 2025 fell on a Friday but CDTA ran Sunday-level service "
            "for the holiday. A viewer who filters by weekday name expecting "
            "'a typical Friday' would silently get holiday ridership instead, "
            "and every chart above would look normal while describing the "
            "wrong kind of day."
        )
    else:
        st.markdown(
            "No mismatches appear in the currently loaded days, but they exist "
            "in the full CDTA record (e.g. July 4, 2025 ran a Sunday schedule "
            "despite being a Friday). Filtering by calendar weekday name alone "
            "is not the same as filtering by the schedule actually operated — "
            "add a holiday date to `data/` and this panel will flag it."
        )

    st.markdown("**2. Missingness — scheduled times exist for a minority of stops**")
    st.markdown(
        f"`nom_arr_time` (the scheduled arrival time) is blank for "
        f"{missing_pct:.0f}% of stop-events in the loaded data — it is only "
        "recorded at official timepoints, not at every stop along the route. "
        "Any chart of schedule adherence or lateness built from this field "
        "necessarily describes only those timepoint stops. A viewer could "
        "easily read 'the bus runs on time' as a claim about the whole route, "
        "when most stops never had a scheduled time to compare against in "
        "the first place."
    )

    st.markdown("**3. Resolution — a load count is not a crowding measure**")
    st.markdown(
        f"The highest `psngr_load` observed in the loaded data is {max_load} "
        "passengers onboard. This dataset has no seated or standing capacity "
        "field for the vehicle running each trip, so a load number alone "
        "cannot tell you whether a bus was crowded, comfortable, or nearly "
        "empty for its size — a viewer looking at the load-profile chart "
        "could easily mistake a raw count for a crowding percentage, which "
        "this dashboard cannot compute."
    )

    st.info(
        "None of these are 'the data is noisy' or 'more charts would help' — "
        "each is a specific conclusion the charts above could lead someone "
        "to reach that would not actually be true.",
        icon="⚠️",
    )