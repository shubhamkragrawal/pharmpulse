import plotly.express as px
import streamlit as st

import style
from db import phase_distribution_by_year

st.set_page_config(page_title="Phase Distribution | PharmaPulse", page_icon="💊", layout="wide")

st.title("Phase Distribution Over Time")
st.caption("Business question: how has the industry's trial-phase mix shifted since large-scale registration began?")

df = phase_distribution_by_year()

year_min, year_max = int(df["start_year"].min()), int(df["start_year"].max())
window = st.slider("Year range", year_min, year_max, (max(1990, year_min), min(2024, year_max)))
plot_df = df[(df["start_year"] >= window[0]) & (df["start_year"] <= window[1])]

view = st.radio("View", ["Count", "Share of year (%)"], horizontal=True)

if view == "Share of year (%)":
    totals = plot_df.groupby("start_year")["trial_count"].transform("sum")
    plot_df = plot_df.assign(value=plot_df["trial_count"] / totals)
    y_label, y_fmt = "Share of trials that year", ".0%"
else:
    plot_df = plot_df.assign(value=plot_df["trial_count"])
    y_label, y_fmt = "Trial count", None

fig = px.bar(
    plot_df, x="start_year", y="value", color="phase",
    color_discrete_sequence=style.CATEGORICAL, height=550,
)
fig.update_layout(xaxis_title="Start year", yaxis_title=y_label, legend_title="Phase")
if y_fmt:
    fig.update_layout(yaxis_tickformat=y_fmt)
if window[0] <= 2000 <= window[1]:
    fig.add_vline(x=2000, line=dict(color=style.MUTED_INK, width=1, dash="dot"))
    fig.add_annotation(x=2000, y=1.0, yref="paper", text="CT.gov launched 2000 →", showarrow=False, xanchor="left", font=dict(color=style.MUTED_INK))
st.plotly_chart(fig, width='stretch')

st.markdown("---")
st.caption(
    "**Data notes:** pre-2000 trials are sparse registry artifacts (retrospectively "
    "registered), not true historical volume -- ClinicalTrials.gov itself only "
    "launched in 2000, and mandatory registration for most drug/device trials "
    "didn't take effect until FDAAA 2007. 'NOT REPORTED' phase covers "
    "observational studies (no phase by design, ~24% of all trials) grouped "
    "into a single bucket here."
)
