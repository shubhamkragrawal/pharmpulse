import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import style
from db import approvals_by_sponsor_class_year, top_sponsors_by_approval_count

st.set_page_config(page_title="Approval Landscape | PharmaPulse", page_icon="💊", layout="wide")

st.title("Approval Landscape")
st.caption("Business question: how has FDA approval volume moved over time, and who are the biggest approval-holders?")

st.info(
    "**Grain note:** `fct_approvals` is one row per submission event "
    "(application_number, submission_type, submission_number), not one row "
    "per application. Every query on this page first collapses to "
    "one row per application (`bool_or(submission_status = 'AP')`) before "
    "counting an approval, per the M3 as-built correction -- a raw `COUNT(*)` "
    "on `fct_approvals` would overcount.",
    icon="ℹ️",
)

by_year = approvals_by_sponsor_class_year()
top_sponsors = top_sponsors_by_approval_count(20)

if by_year.empty:
    st.warning("No approved applications with a recorded approval date were found.")
else:
    yearly_total = by_year.groupby("approval_year", as_index=False)["approval_count"].sum()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Approvals over time")
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=yearly_total["approval_year"],
                y=yearly_total["approval_count"],
                mode="lines+markers",
                line=dict(color=style.BLUE, width=2),
                marker=dict(size=6),
                name="Approvals",
            )
        )
        fig.update_layout(xaxis_title="Approval year", yaxis_title="Approved applications", height=420)
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.subheader("Approval volume, top 10 applicants")
        st.warning(
            "sponsor_name here is the FDA applicant, not a sponsor_class category -- "
            "openFDA's applicant field isn't classified into sponsor_class the way "
            "CT.gov's is (see dim_sponsor). Shown by top individual applicants instead; "
            "a true sponsor_class cut isn't available for FDA data as of M5.",
            icon="⚠️",
        )
        top_names = by_year.groupby("sponsor_name")["approval_count"].sum().nlargest(10).index
        fig2 = px.bar(
            by_year[by_year["sponsor_name"].isin(top_names)],
            x="approval_year",
            y="approval_count",
            color="sponsor_name",
            height=380,
            color_discrete_sequence=style.CATEGORICAL,
        )
        fig2.update_layout(xaxis_title="Approval year", yaxis_title="Approved applications", legend_title="Applicant")
        st.plotly_chart(fig2, width='stretch')

    st.subheader("Top 20 sponsors by approval count")
    fig3 = px.bar(
        top_sponsors.sort_values("approval_count"),
        x="approval_count",
        y="sponsor_name",
        orientation="h",
        height=500,
        color_discrete_sequence=[style.BLUE],
    )
    fig3.update_layout(xaxis_title="Approved applications", yaxis_title="")
    st.plotly_chart(fig3, width='stretch')

st.markdown("---")
st.caption(
    "**Data notes:** approval_date is `submission_status_date` for the submission "
    "that reached AP status; applications with no AP submission on record are "
    "excluded. `sponsor_name` here is the FDA applicant name (openFDA), a "
    "different namespace from CT.gov's `dim_sponsor.sponsor_name` -- these two "
    "are never joined on this page."
)
