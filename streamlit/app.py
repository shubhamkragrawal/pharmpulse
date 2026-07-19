import streamlit as st

import style  # noqa: F401 -- registers the shared Plotly theme on import

st.set_page_config(
    page_title="PharmaPulse Explorer",
    page_icon="💊",
    layout="wide",
)

st.title("PharmaPulse Explorer")
st.caption(
    "Interactive read-only dashboard over 594K+ ClinicalTrials.gov trials and "
    "29K+ FDA applications, sourced from the marts/metrics layer built in "
    "domains/pharma/dbt/."
)

st.markdown(
    """
Use the sidebar to open any of the 8 dashboards. Each page states the business
question it answers and lists data caveats below its charts, not just in
tooltips.

**Access control:** this app connects via a read-only Postgres role
(`pharmapulse_readonly`) scoped to the `marts` and `metrics` schemas only --
no `raw` or `staging` access. This is a portfolio-appropriate simplification,
not production access control (no SSO, no row-level security) -- see the
README for the full disclosure.

**Start with Dashboard 8 (Pipeline Trust)** if you want the short version of
every data-quality caveat that affects the other 7 dashboards, in one place.
"""
)

st.divider()

dashboards = [
    ("1. Approval Landscape", "FDA approval counts over time, by sponsor class and top sponsors."),
    ("2. Phase Funnel", "Phase 2 -> Phase 3 -> Approval funnel by condition (directional, not literal)."),
    ("3. Sponsor League Table", "Sortable, filterable table of every sponsor's trial volume and success rate."),
    ("4. Duration Trends", "Median trial duration YoY, with percentile bands and a by-phase cut."),
    ("5. Sponsor Cohorts", "Survivorship curves: how long sponsors stay active after their first trial."),
    ("6. Termination Reasons", "Why trials stop early -- by phase, by sponsor class, and by stated reason."),
    ("7. Phase Distribution", "How the industry's trial-phase mix has shifted since 2000."),
    ("8. Pipeline Trust", "Scorecard: how much to trust each of the other 7 dashboards, and why."),
]
for name, desc in dashboards:
    st.markdown(f"**{name}** — {desc}")
