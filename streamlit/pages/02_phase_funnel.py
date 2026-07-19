import plotly.express as px
import streamlit as st

import style
from db import phase_funnel_audit_metrics, phase_funnel_by_condition

st.set_page_config(page_title="Phase Funnel | PharmaPulse", page_icon="💊", layout="wide")

st.title("Phase Funnel")
st.caption("Business question: which conditions carry trials furthest through Phase 2 -> Phase 3 -> Approval?")

st.error(
    "**Read this before the chart.** These rates are directional/descriptive "
    "only, not true transition probabilities. CT.gov has no field linking a "
    "trial to its own phase-successor trial, so Phase-2/Phase-3 counts per "
    "condition are independent cross-sectional volumes -- rates **can and do "
    "exceed 100%** (e.g. Diabetes at 203%). The Approval stage compounds this "
    "with a best-effort `sponsor_name` string match between CT.gov lead-sponsor "
    "names and FDA applicant names -- different namespaces, no entity "
    "resolution applied. Grouped by `condition_name`, **not** `therapeutic_area` "
    "-- the latter is NULL for all rows as of M3 (no MeSH crosswalk yet); "
    "`condition_name` is the M4 interim proxy.",
    icon="🚨",
)

min_phase2 = st.slider("Minimum Phase-2 trials per condition", 10, 500, 100, step=10)
df = phase_funnel_by_condition(min_phase2_trials=min_phase2)
audit = phase_funnel_audit_metrics()

if df.empty:
    st.warning("No conditions meet this Phase-2 trial-count threshold. Try lowering the slider.")
else:
    over_100_p2p3 = int((df["phase2_to_phase3_rate"] > 1).sum())
    over_100_p3appr = int((df["phase3_to_approval_rate"] > 1).sum())

    m1, m2, m3 = st.columns(3)
    m1.metric("Conditions shown", len(df))
    m2.metric("Phase2->3 rate > 100%", f"{over_100_p2p3} ({over_100_p2p3 / len(df):.0%})")
    m3.metric("Phase3->Approval rate > 100%", f"{over_100_p3appr} ({over_100_p3appr / len(df):.0%})")

    top_n = st.slider("Show top N conditions by Phase-2 volume", 5, 40, 15)
    plot_df = df.nlargest(top_n, "condition_phase2_trials").sort_values("condition_phase2_trials")

    fig = px.bar(
        plot_df,
        x=["condition_phase2_trials", "condition_phase3_trials", "condition_approved_trials"],
        y="condition_name",
        orientation="h",
        barmode="group",
        height=max(400, 28 * len(plot_df)),
        color_discrete_sequence=[style.BLUE, style.AQUA, style.VIOLET],
        labels={"value": "Trial count", "condition_name": "", "variable": "Stage"},
    )
    newnames = {
        "condition_phase2_trials": "Phase 2",
        "condition_phase3_trials": "Phase 3",
        "condition_approved_trials": "Approval (best-effort match)",
    }
    fig.for_each_trace(lambda t: t.update(name=newnames.get(t.name, t.name)))
    st.subheader(f"Top {top_n} conditions by Phase-2 volume: funnel stage counts")
    st.plotly_chart(fig, width='stretch')

    st.subheader("Rate table")
    display_df = plot_df[[
        "condition_name", "condition_phase2_trials", "condition_phase3_trials", "condition_approved_trials",
        "phase2_to_phase3_rate", "phase3_to_approval_rate", "phase2_to_approval_rate",
    ]].sort_values("condition_phase2_trials", ascending=False)
    st.dataframe(
        display_df.style.format({
            "phase2_to_phase3_rate": "{:.1%}",
            "phase3_to_approval_rate": "{:.1%}",
            "phase2_to_approval_rate": "{:.1%}",
        }),
        width='stretch',
        hide_index=True,
    )

st.markdown("---")
st.caption(
    f"**Audit footnote:** `multi_condition_flag` rate across all trials in "
    f"metric_phase_transition is **{audit.iloc[0]['multi_condition_flag_rate']:.1%}** "
    f"-- the share of trials where a multi-condition tie-break "
    f"(`ROW_NUMBER() OVER (PARTITION BY nct_id ORDER BY condition_key ASC)`) "
    f"picked one condition out of several reported. `matched_to_fda` rate is "
    f"**{audit.iloc[0]['matched_to_fda_rate']:.1%}** of all trials -- the share "
    f"that even has a candidate sponsor-name match into FDA data, independent "
    f"of whether that match reflects an approval. See Dashboard 8 (Pipeline "
    f"Trust) for the full data-quality scorecard."
)
