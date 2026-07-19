import plotly.graph_objects as go
import streamlit as st

import style
from db import duration_trends_by_phase, duration_trends_overall

st.set_page_config(page_title="Duration Trends | PharmaPulse", page_icon="💊", layout="wide")

st.title("Duration Trends")
st.caption("Business question: how long do trials take from start to completion, and is that changing over time?")

overall = duration_trends_overall()
by_phase = duration_trends_by_phase()

CENSOR_CUTOFF = 2017

st.warning(
    f"**Right-censoring caveat:** `duration_days` requires a non-null "
    f"`completion_date`. Recent-year trials that are long-running are "
    f"disproportionately still ongoing and excluded, so only fast-completing "
    f"trials from recent years have a measured duration yet. Years after "
    f"{CENSOR_CUTOFF} (dashed below) are not comparable to earlier years -- "
    f"the apparent decline is partly a measurement artifact, not only real "
    f"speed-up.",
    icon="⚠️",
)

st.subheader("Median duration YoY, with p25/p75 bands")
reliable = overall[overall["start_year"] <= CENSOR_CUTOFF]
censored = overall[overall["start_year"] >= CENSOR_CUTOFF]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=overall["start_year"], y=overall["p75_duration_days"],
    line=dict(width=0), showlegend=False, hoverinfo="skip",
))
fig.add_trace(go.Scatter(
    x=overall["start_year"], y=overall["p25_duration_days"],
    fill="tonexty", fillcolor="rgba(42,120,214,0.15)", line=dict(width=0),
    name="p25-p75 band", hoverinfo="skip",
))
fig.add_trace(go.Scatter(
    x=reliable["start_year"], y=reliable["median_duration_days"],
    mode="lines", line=dict(color=style.BLUE, width=2), name="Median (reliable)",
))
fig.add_trace(go.Scatter(
    x=censored["start_year"], y=censored["median_duration_days"],
    mode="lines", line=dict(color=style.BLUE, width=2, dash="dash"), name="Median (right-censored)",
))
fig.add_vline(x=CENSOR_CUTOFF, line=dict(color=style.BASELINE, width=1))
fig.update_layout(xaxis_title="Start year", yaxis_title="Trial duration (days)", height=480)
st.plotly_chart(fig, width='stretch')

st.subheader("Median duration by phase")
phases = sorted(by_phase["phase"].unique().tolist())
selected_phases = st.multiselect("Phases to show", phases, default=[p for p in phases if p in ("PHASE1", "PHASE2", "PHASE3", "PHASE4")] or phases[:4])

fig2 = go.Figure()
for i, phase in enumerate(selected_phases):
    sub = by_phase[by_phase["phase"] == phase].sort_values("start_year")
    sub = sub[sub["start_year"] <= CENSOR_CUTOFF]  # same right-censoring caveat applies here
    fig2.add_trace(go.Scatter(
        x=sub["start_year"], y=sub["median_duration_days"],
        mode="lines", name=phase, line=dict(color=style.CATEGORICAL[i % len(style.CATEGORICAL)], width=2),
    ))
fig2.update_layout(xaxis_title="Start year", yaxis_title="Median trial duration (days)", height=480)
fig2.add_vline(x=CENSOR_CUTOFF, line=dict(color=style.BASELINE, width=1))
st.plotly_chart(fig2, width='stretch')
st.caption(f"By-phase view truncated at {CENSOR_CUTOFF} -- the right-censoring caveat above applies here too.")

st.markdown("---")
st.caption(
    "**Data notes:** by-phase view uses `metric_duration_trends_by_phase` "
    "(M5), a separate model from the overall YoY line (`metric_duration_trends`, "
    "M4) so M4's already-documented numbers don't shift. `phase` is the raw "
    "pipe-delimited passthrough (e.g. \"PHASE1|PHASE2\" for combined-phase "
    "trials is its own row, not split into constituent phases)."
)
