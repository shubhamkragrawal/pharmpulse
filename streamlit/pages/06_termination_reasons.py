import plotly.express as px
import streamlit as st

import style
from db import (
    termination_rate_by_phase,
    termination_rate_by_sponsor_class,
    why_stopped_breakdown,
    why_stopped_coverage,
)

st.set_page_config(page_title="Why Trials Fail | PharmaPulse", page_icon="💊", layout="wide")

st.title("Why Trials Fail")
st.caption("Business question: where in the pipeline, and for what stated reasons, do trials stop early?")

by_phase = termination_rate_by_phase()
by_class = termination_rate_by_sponsor_class()
reasons = why_stopped_breakdown(15)
coverage = why_stopped_coverage()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Termination rate by phase")
    fig = px.bar(
        by_phase.sort_values("termination_rate"),
        x="termination_rate", y="phase", orientation="h",
        color_discrete_sequence=[style.RED], height=420,
    )
    fig.update_layout(xaxis_title="Termination rate", xaxis_tickformat=".0%", yaxis_title="")
    st.plotly_chart(fig, width='stretch')

with col2:
    st.subheader("Termination rate by sponsor class")
    fig2 = px.bar(
        by_class.sort_values("termination_rate"),
        x="termination_rate", y="sponsor_class", orientation="h",
        color_discrete_sequence=[style.ORANGE], height=420,
    )
    fig2.update_layout(xaxis_title="Termination rate", xaxis_tickformat=".0%", yaxis_title="")
    st.plotly_chart(fig2, width='stretch')

st.subheader("Stated reasons, where reported")
terminated = int(coverage.iloc[0]["terminated_trials"])
with_reason = int(coverage.iloc[0]["terminated_with_reason"])
st.caption(
    f"why_stopped is populated for {with_reason:,} of {terminated:,} terminated "
    f"trials ({with_reason / terminated:.1%}) -- plus some WITHDRAWN/SUSPENDED "
    f"trials not counted here. The chart below covers only the trials where a "
    f"reason was actually recorded; it is not a full breakdown of all terminations."
)
fig3 = px.bar(
    reasons.sort_values("trial_count"),
    x="trial_count", y="why_stopped", orientation="h",
    color_discrete_sequence=[style.VIOLET], height=520,
)
fig3.update_layout(xaxis_title="Trial count", yaxis_title="")
st.plotly_chart(fig3, width='stretch')

st.markdown("---")
st.caption(
    "**Data notes:** `why_stopped` is free text (CT.gov `statusModule.whyStopped`), "
    "grouped verbatim here with no normalization -- semantically similar reasons "
    "(e.g. \"Low enrollment\" vs \"Insufficient accrual\") are not merged, so this "
    "undercounts the true concentration of any one root cause. Added to the marts "
    "layer in M5 specifically to support this dashboard (see decisions.md)."
)
