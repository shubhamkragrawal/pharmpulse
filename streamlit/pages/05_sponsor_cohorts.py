import plotly.graph_objects as go
import streamlit as st

import style
from db import sponsor_cohort_survivorship

st.set_page_config(page_title="Sponsor Cohorts | PharmaPulse", page_icon="💊", layout="wide")

st.title("Sponsor Cohort Survivorship")
st.caption("Business question: once a sponsor runs its first trial, how long do they stay active in the trial ecosystem?")

df = sponsor_cohort_survivorship()

st.warning(
    "**NULL completion_date caveat:** a trial with no recorded `completion_date` "
    "is counted as active only in its start year, not open-ended through the "
    "present (see decisions.md, M4). This is conservative -- it undercounts "
    "survivorship for the most recent cohorts, since a sponsor's still-enrolling "
    "trial with no end date yet will look identical to one that simply stopped. "
    "Read the newest 3-5 cohort-years' curves with this in mind.",
    icon="⚠️",
)

all_cohorts = sorted(df["cohort_year"].unique().tolist())
default_cohorts = [y for y in [2000, 2005, 2010, 2015, 2020] if y in all_cohorts] or all_cohorts[:5]
selected = st.multiselect("Cohort years to compare", all_cohorts, default=default_cohorts)

metric = st.radio("Y-axis", ["Survivorship rate (%)", "Active sponsor count"], horizontal=True)

fig = go.Figure()
for i, year in enumerate(sorted(selected)):
    sub = df[df["cohort_year"] == year].sort_values("years_since_cohort")
    y = sub["survivorship_rate"] if metric.startswith("Survivorship") else sub["active_sponsor_count"]
    fig.add_trace(go.Scatter(
        x=sub["years_since_cohort"], y=y, mode="lines+markers",
        name=str(year), line=dict(color=style.CATEGORICAL[i % len(style.CATEGORICAL)], width=2),
        marker=dict(size=5),
    ))

if metric.startswith("Survivorship"):
    fig.update_layout(yaxis_tickformat=".0%")
fig.update_layout(xaxis_title="Years since cohort's first trial", yaxis_title=metric, height=520)
st.plotly_chart(fig, width='stretch')

st.markdown("---")
st.caption(
    "**Data notes:** cohort_year = year of a sponsor's earliest fct_trials.start_date. "
    "survivorship_rate = active_sponsor_count / the cohort's own launch-year count "
    "(FIRST_VALUE window function, metrics.metric_sponsor_cohorts). Sponsors with "
    "an all-NULL start_date across every trial are excluded from cohorting entirely."
)
