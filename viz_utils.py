"""
Visualization helpers for the Streamlit radar dashboard:
dark-themed Altair charts, period deltas, sparklines, and timeline logic.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

CHART_BG = "#0f172a"
CHART_PANEL = "#1e293b"
ACCENT_BAR = "#38bdf8"
ACCENT_MUTED = "#64748b"


def apply_dark_theme(chart: alt.Chart) -> alt.Chart:
    """Apply a cohesive dark theme to an Altair chart (no white plot area)."""
    return (
        chart.configure_view(strokeWidth=0, fill=CHART_PANEL, cornerRadius=8)
        .configure(background=CHART_BG)
        .configure_axis(
            labelColor="#94a3b8",
            titleColor="#cbd5e1",
            gridColor="#334155",
            domainColor="#475569",
        )
        .configure_axisX(grid=False)
        .configure_axisY(grid=True)
        .configure_legend(labelColor="#cbd5e1", titleColor="#94a3b8")
        .configure_title(color="#f1f5f9", fontSize=14)
    )


def _with_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "date_detected" not in out.columns:
        return out.assign(_dt=pd.NaT)
    out["_dt"] = pd.to_datetime(out["date_detected"], errors="coerce")
    return out


def compute_week_over_week_deltas(df: pd.DataFrame) -> dict[str, tuple[float, float | None]]:
    """
    Compare last 7 days vs previous 7 days (by max date in frame).
    Returns dict metric_name -> (current_value, delta_vs_prior) for st.metric.
    """
    d = _with_dates(df).dropna(subset=["_dt"])
    empty = {
        "total": (0.0, None),
        "high_conf": (0.0, None),
        "new": (0.0, None),
        "competitors": (0.0, None),
    }
    if d.empty:
        return empty

    end = d["_dt"].max()
    if pd.isna(end):
        return empty

    last_start = end - pd.Timedelta(days=7)
    prior_start = end - pd.Timedelta(days=14)
    prior_end = last_start

    last = d[d["_dt"] > last_start]
    prior = d[(d["_dt"] > prior_start) & (d["_dt"] <= prior_end)]

    high_last = len(last[last["confidence_score"] > 0.7]) if "confidence_score" in last else 0
    high_prior = len(prior[prior["confidence_score"] > 0.7]) if "confidence_score" in prior else 0

    new_last = int(last["is_new"].sum()) if "is_new" in last.columns else 0
    new_prior = int(prior["is_new"].sum()) if "is_new" in prior.columns else 0

    comp_last = last["competitor"].nunique() if "competitor" in last.columns and len(last) else 0
    comp_prior = prior["competitor"].nunique() if "competitor" in prior.columns and len(prior) else 0

    return {
        "total": (float(len(last)), float(len(last) - len(prior))),
        "high_conf": (float(high_last), float(high_last - high_prior)),
        "new": (float(new_last), float(new_last - new_prior)),
        "competitors": (float(comp_last), float(comp_last - comp_prior)),
    }


def daily_series(
    df: pd.DataFrame,
    *,
    end_days: int = 30,
    predicate=None,
) -> pd.DataFrame:
    """Aggregate count per calendar day over the last `end_days` from max date."""
    d = _with_dates(df).dropna(subset=["_dt"])
    if d.empty:
        return pd.DataFrame(columns=["date", "count"])

    end = d["_dt"].max().normalize()
    start = end - pd.Timedelta(days=end_days)
    sub = d[d["_dt"] >= start]
    if predicate is not None:
        sub = sub[sub.apply(predicate, axis=1)]

    sub = sub.assign(day=sub["_dt"].dt.normalize())
    g = sub.groupby("day", as_index=False).size()
    g = g.rename(columns={"size": "count", "day": "date"})
    # Full date range fill for smooth sparkline
    idx = pd.date_range(start=start, end=end, freq="D")
    full = pd.DataFrame({"date": idx.normalize()})
    full = full.merge(g, on="date", how="left").fillna({"count": 0})
    return full


def daily_competitor_nunique(df: pd.DataFrame, *, end_days: int = 30) -> pd.DataFrame:
    """Count distinct competitors per day (last `end_days` from max date)."""
    d = _with_dates(df).dropna(subset=["_dt"])
    if d.empty or "competitor" not in d.columns:
        return pd.DataFrame(columns=["date", "count"])

    end = d["_dt"].max().normalize()
    start = end - pd.Timedelta(days=end_days)
    sub = d[d["_dt"] >= start].copy()
    sub["day"] = sub["_dt"].dt.normalize()
    g = sub.groupby("day", as_index=False)["competitor"].nunique()
    g = g.rename(columns={"competitor": "count", "day": "date"})
    idx = pd.date_range(start=start, end=end, freq="D")
    full = pd.DataFrame({"date": idx.normalize()})
    full = full.merge(g, on="date", how="left").fillna({"count": 0})
    return full


def sparkline_chart(series: pd.DataFrame, *, height: int = 72) -> alt.Chart:
    """Tiny area/line chart for KPI row."""
    if series.empty or series["count"].sum() == 0:
        placeholder = pd.DataFrame({"x": [0], "y": [0], "t": ["No trend in window"]})
        base = (
            alt.Chart(placeholder)
            .mark_text(color="#64748b", fontSize=11)
            .encode(x="x:Q", y="y:Q", text="t:N")
        )
        return apply_dark_theme(base.properties(height=height, width="container"))

    return apply_dark_theme(
        alt.Chart(series)
        .mark_area(
            line={"color": ACCENT_BAR},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="#0ea5e966", offset=0),
                    alt.GradientStop(color="#0ea5e900", offset=1),
                ],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ),
        )
        .encode(
            x=alt.X("date:T", title=None, axis=None),
            y=alt.Y("count:Q", title=None, axis=None, stack=None),
        )
        .properties(height=height, width="container")
    )


def build_run_history_df(full_df: pd.DataFrame, *, limit: int = 10) -> pd.DataFrame:
    """Compact run history for sidebar dataframe."""
    if "run_id" not in full_df.columns:
        return pd.DataFrame()

    g = full_df.dropna(subset=["run_id"]).copy()
    if g.empty:
        return pd.DataFrame()

    if "event_id" in g.columns:
        agg = g.groupby("run_id", as_index=False).agg(
            events=("event_id", "count"),
            latest_date=("date_detected", lambda s: pd.to_datetime(s, errors="coerce").max()),
        )
    else:
        agg = g.groupby("run_id", as_index=False).agg(
            events=("competitor", "size"),
            latest_date=("date_detected", lambda s: pd.to_datetime(s, errors="coerce").max()),
        )

    agg = agg.sort_values("latest_date", ascending=False, na_position="last").head(limit)
    agg["run"] = agg["run_id"].astype(str).str[:10]
    agg["latest"] = agg["latest_date"].apply(
        lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "—"
    )
    return agg[["run", "events", "latest"]].rename(
        columns={"run": "Run", "events": "Events", "latest": "Latest"}
    )


def timeline_chart_for_df(df_chart: pd.DataFrame) -> tuple[alt.Chart, str]:
    """
    Return (chart, mode_description).
    Uses tight date domain for bars, or strip/dot plot when sparse / few distinct days.
    """
    n_events = len(df_chart)
    n_days = df_chart["date"].nunique()
    min_d = df_chart["date"].min()
    max_d = df_chart["date"].max()
    span = (pd.Timestamp(max_d) - pd.Timestamp(min_d)).days if pd.notna(min_d) and pd.notna(max_d) else 0

    sparse = n_events < 20 and span > 60
    few_days = n_days <= 12 and n_events > 0

    if few_days or sparse:
        plot_df = df_chart.copy()
        if "competitor" not in plot_df.columns:
            plot_df["competitor"] = "—"
        base = alt.Chart(plot_df)
        enc = dict(
            x=alt.X(
                "date:T",
                title="Date",
                scale=alt.Scale(domain=[str(min_d), str(max_d)], nice=False),
            ),
            y=alt.Y("competitor:N", title=None, axis=alt.Axis(labelLimit=120)),
            color=alt.Color(
                "competitor:N",
                legend=alt.Legend(orient="bottom", columns=3),
                scale=alt.Scale(scheme="blues"),
            ),
        )
        if "title" in plot_df.columns:
            chart = (
                base.mark_circle(size=80, opacity=0.85)
                .encode(**enc, tooltip=["competitor", "date:T", "title:N"])
                .properties(height=280)
            )
        else:
            chart = (
                base.mark_circle(size=80, opacity=0.85)
                .encode(**enc, tooltip=["competitor", "date:T"])
                .properties(height=280)
            )
        note = "Event markers (compact view for sparse or few-day data)."
        return apply_dark_theme(chart), note

    chart = (
        alt.Chart(df_chart)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X(
                "date:T",
                title="Date",
                scale=alt.Scale(domain=[str(min_d), str(max_d)], nice=False, padding=0.02),
            ),
            y=alt.Y("count():Q", title="Events"),
            color=alt.Color(
                "competitor:N",
                legend=alt.Legend(orient="bottom", columns=3),
                scale=alt.Scale(scheme="blues"),
            ),
            tooltip=["competitor", "count()"],
        )
    )
    chart = chart.properties(height=280)
    return apply_dark_theme(chart), "Daily event counts (axis trimmed to data range)."


def confidence_chart(
    df: pd.DataFrame,
    mode: str,
) -> alt.Chart | None:
    """Histogram, strip plot, or decile table chart for confidence scores."""
    if df.empty or "confidence_score" not in df.columns:
        return None

    scores = df["confidence_score"].dropna()
    if scores.empty:
        return None

    if mode == "Strip plot":
        samp = df[["confidence_score"]].copy()
        samp["competitor"] = df["competitor"] if "competitor" in df.columns else "—"
        samp = samp.dropna(subset=["confidence_score"])
        chart = (
            alt.Chart(samp)
            .mark_tick(color=ACCENT_BAR, thickness=2)
            .encode(
                x=alt.X("confidence_score:Q", title="Confidence", scale=alt.Scale(domain=[0, 1])),
                y=alt.Y("competitor:N", title=None),
                tooltip=["competitor", "confidence_score"],
            )
            .properties(height=280)
        )
        return apply_dark_theme(chart)

    if mode == "Decile table":
        # Bar chart of counts per decile bucket (readable as table-like bars)
        dec = pd.cut(scores, bins=[i / 10 for i in range(11)], include_lowest=True, right=True)
        tbl = dec.value_counts().sort_index().reset_index()
        tbl.columns = ["bucket", "count"]
        tbl["label"] = tbl["bucket"].astype(str)
        chart = (
            alt.Chart(tbl)
            .mark_bar(color=ACCENT_BAR, cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
            .encode(
                x=alt.X("label:N", title="Decile bucket", sort=None, axis=alt.Axis(labelAngle=-45)),
                y=alt.Y("count:Q", title="Count"),
                tooltip=["label", "count"],
            )
            .properties(height=280)
        )
        return apply_dark_theme(chart)

    # Histogram (default)
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color=ACCENT_BAR)
        .encode(
            x=alt.X(
                "confidence_score:Q",
                bin=alt.Bin(maxbins=12, extent=[0, 1]),
                title="Confidence score",
            ),
            y=alt.Y("count():Q", title="Count"),
            tooltip=["count()"],
        )
        .properties(height=280)
    )
    return apply_dark_theme(chart)


def confidence_summary_stats(df: pd.DataFrame) -> str:
    """One-line summary under confidence chart."""
    if df.empty or "confidence_score" not in df.columns:
        return ""
    s = df["confidence_score"].dropna()
    if s.empty:
        return ""
    p50 = s.quantile(0.5)
    hi = (s > 0.7).mean() * 100
    return f"Median {p50:.2f} · {hi:.0f}% above 0.7 · mean {s.mean():.2f}"


def timeline_summary_stats(df_chart: pd.DataFrame) -> str:
    """One-line summary under timeline."""
    if df_chart.empty:
        return ""
    n = len(df_chart)
    nd = df_chart["date"].nunique()
    return f"{n} events across {nd} distinct days in view."
