import streamlit as st

from db import pipeline_trust_scorecard
from style import traffic_light

st.set_page_config(page_title="Pipeline Trust | PharmaPulse", page_icon="💊", layout="wide")

st.title("Pipeline Trust")
st.caption(
    "How much should you trust each dashboard in this app? This page answers "
    "that directly, with numbers, rather than leaving caveats scattered across "
    "individual pages."
)
st.markdown(
    "Every metric below is a **known, measured limitation** in the underlying "
    "data or linkage logic -- not a bug to be fixed before you can use this "
    "app, but a boundary you should know about before you act on a number from "
    "it. Green means the limitation is small or well-controlled; amber means "
    "read the affected dashboard's caveat before quoting a number; red means "
    "treat the affected figure as directional only."
)

scorecard = pipeline_trust_scorecard()

st.markdown("---")

c1, c2, c3 = st.columns(3)

with c1:
    rate = scorecard["multi_condition_flag_rate"]
    light = traffic_light(rate, good_max=0.15, warning_max=0.35)
    st.metric(f"{light} Multi-condition tie-break rate", f"{rate:.1%}")
    st.caption(
        "Share of trials in metric_phase_transition where a trial reported "
        ">1 condition and a tie-break (first-listed by condition_key) picked "
        "one. **Affects:** Dashboard 2 (Phase Funnel) -- condition_name "
        "groupings undercount trials whose relevant condition wasn't picked."
    )

with c2:
    rate = scorecard["matched_to_fda_rate"]
    # inverted vs. c1/c5: here HIGH is good (more Approval-stage coverage) --
    # a low match rate means most trials have zero visibility into the
    # Approval stage, which is the caution signal, not the reassurance.
    light = traffic_light(1 - rate, good_max=0.15, warning_max=0.35)
    st.metric(f"{light} Trial -> FDA sponsor match rate", f"{rate:.1%}")
    st.caption(
        "Share of trials whose CT.gov sponsor_name string-matched an FDA "
        "applicant name. Low by construction -- most trials never reach an "
        "FDA submission, and the match itself is best-effort (different "
        "namespaces, no entity resolution). **Affects:** Dashboard 1 (Approval "
        "Landscape, indirectly) and Dashboard 2 (Phase Funnel) -- the Approval "
        "stage of the funnel."
    )

with c3:
    grouping = scorecard["grouping_by_condition_name"]
    light = "🟡" if grouping else "🟢"
    st.metric(f"{light} Phase funnel grouped by condition_name", "TRUE" if grouping else "FALSE")
    st.caption(
        "Always TRUE until a MeSH crosswalk is built -- `therapeutic_area` "
        "has no CT.gov source field and is NULL for every row (see next "
        "metric). condition_name is a real but high-cardinality proxy. "
        "**Affects:** Dashboard 2 (Phase Funnel) -- cannot be sliced by "
        "clinical therapeutic area today, only by free-text condition."
    )

c4, c5 = st.columns(2)

with c4:
    rate = scorecard["therapeutic_area_null_rate"]
    # Fixed amber, not computed: this rate is expected to be ~100% by design
    # (no source field exists yet), not a value that should ever trend
    # toward green -- a traffic light computed off of it would be noise.
    st.metric("🟡 dim_condition.therapeutic_area NULL rate", f"{rate:.1%}")
    st.caption(
        "Expected to be ~100% as of M5 -- there is no CT.gov source field for "
        "therapeutic area, and no MeSH crosswalk has been built. This is not a "
        "data-quality defect to chase down; it's a documented, permanent gap "
        "until a crosswalk is scoped as its own milestone. **Affects:** "
        "Dashboard 2 (Phase Funnel) -- the reason it's grouped by "
        "condition_name instead."
    )

with c5:
    rate = scorecard["completion_date_null_rate"]
    light = traffic_light(rate, good_max=0.15, warning_max=0.35)
    st.metric(f"{light} fct_trials.completion_date NULL rate", f"{rate:.1%}")
    st.caption(
        "Trials with no recorded completion date -- currently-enrolling trials "
        "and a small share of genuinely missing dates. **Affects:** Dashboard 4 "
        "(Duration Trends, right-censoring in recent years) and Dashboard 5 "
        "(Sponsor Cohorts, NULL completion_date treated as active in start "
        "year only, not open-ended)."
    )

st.markdown("---")
st.subheader("Summary")
st.markdown(
    """
| Dashboard | Trust level | Why |
|---|---|---|
| 1. Approval Landscape | 🟢 High | fct_approvals is correctly collapsed from submission-event grain; only caveat is the FDA-applicant vs. CT.gov sponsor namespace split (not mixed on this page). |
| 2. Phase Funnel | 🔴 Directional only | Rates are relative-volume ratios (can exceed 100%), grouped by condition_name proxy, Approval stage is a noisy best-effort match. Read the in-page caveat banner. |
| 3. Sponsor League Table | 🟢 High | Numbers are direct dim_sponsor aggregates, no cross-source linkage involved. |
| 4. Duration Trends | 🟡 Caveat in recent years | Right-censoring biases the last several years' medians downward -- see dashed line on the chart. |
| 5. Sponsor Cohorts | 🟡 Caveat in recent cohorts | NULL completion_date undercounts survivorship for the newest cohorts. |
| 6. Termination Reasons | 🟡 Partial coverage | why_stopped is only populated for a minority of terminated/withdrawn/suspended trials; free text, not normalized. |
| 7. Phase Distribution | 🟡 Caveat pre-2000 | Pre-2000 volume is a registry-coverage artifact, not real historical trial volume. |
| 8. Pipeline Trust (this page) | — | Meta -- this page's own numbers are live queries against marts/metrics, refreshed hourly (`st.cache_data(ttl=3600)`) same as every other page. |
"""
)
