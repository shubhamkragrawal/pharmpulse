TO: Chief Medical Officer / Head of R&D Strategy
FROM: Analytics Team
RE: Clinical Trial Portfolio Intelligence — 3 Key Findings and 1 Decision Ask
DATE: July 19, 2026

## Executive Summary

We built a warehouse and dashboard suite covering 594,309 ClinicalTrials.gov
trials and 29,218 FDA applications to answer one question: **where should a
mid-size pharma company focus R&D investment?** Three findings below show
where the trial funnel actually breaks down, which sponsors persist versus
churn, and why recent trial-duration data can't yet be trusted at face value
— each with the caveat needed to use it responsibly.

## Finding 1: Where the Trial Funnel Breaks Down

Phase 2 → Phase 3 volume ratios vary enormously by condition. The headline
number: **Diabetes shows a 203% ratio** — 100 Phase 2 trials registered
against 203 Phase 3 trials for that condition name. Read literally that's
impossible; it isn't a bug, it's a real limit of the data. CT.gov has no
field linking a trial to its own phase-successor trial, so our "transition
rate" is a ratio of two independent cross-sectional counts, not a followed
cohort's conversion — 14 of 109 conditions with ≥100 Phase-2 trials show
this same over-100% pattern. **Our data shows directional signal, not a
true cohort transition rate** — a known boundary of what CT.gov's public
data supports, not a flaw in our pipeline.

More useful is the low end of the same ratio: high Phase 2 investment with
the *weakest* apparent follow-through. **Advanced Solid Tumors** is the
clearest case — 159 Phase 2 trials versus 0 Phase 3 trials; related oncology
labels match (Solid Tumor: 223 → 5; Metastatic Melanoma: 127 → 7). Whether
that's genuine attrition or re-labeling under a different condition name at
Phase 3 is exactly what a therapeutic-area rollup (Decision Ask, below)
would let us answer with more confidence than free-text names can.

## Finding 2: Sponsor Concentration and Survivorship

Two signals here. **Raw trial volume is dominated by academic and public
institutions, not industry**: Cairo University leads all 51,173 sponsors
with 4,739 trials, followed by Assiut University, National Cancer Institute,
and Mayo Clinic — GlaxoSmithKline is the first industry sponsor by volume,
ranked third overall. But **industry sponsors dominate by completion
success rate**: Boehringer Ingelheim (87.0%), GlaxoSmithKline (85.9%), and
AstraZeneca (77.1%) post completion rates well above the academic volume
leaders (Cairo University: 39.2%; Assiut University: 18.3%). Volume
leadership and execution leadership are not the same sponsors — a real
competitive-intelligence split worth tracking separately.

On longevity: of the 310 sponsors who ran their first trial in 2000,
**64.5% were still active 20 years later**. That's a lower bar than it
sounds — 5-year survivorship for that cohort is already 83.5%, and newer
cohorts persist for shorter windows (2019's 5-year survivorship is 40.5%,
roughly half of 2000's). Sponsor durability appears to be declining.

## Finding 3: Trial Duration Trends and the Right-Censoring Caveat

Median trial duration fell from roughly 4,200 days (1990) to roughly 700
days (2020) — at face value, trials getting dramatically faster. Pre-2017
that reading is reliable; post-2017 it isn't. Our duration metric requires
a completed trial, and recent long-running trials are disproportionately
still enrolling, so only the fastest-completing recent trials have a
measurable duration yet. That segment is **right-censored, not a real
speed-up** — every dashboard renders it as a dashed line for that reason.

**Business implication:** anchor timeline expectations to the pre-2017
trend, not the apparent recent acceleration — recent numbers will keep
revising upward as today's still-running trials complete.

## Decision Ask

**Fund a MeSH tree-number crosswalk mapping `condition_name` →
`therapeutic_area`.** Every finding above is cut by free-text condition
name — hundreds of overlapping labels ("Type 2 Diabetes," "Type 2 Diabetes
Mellitus," and "Diabetes Mellitus, Type 2" are three separate buckets
today). A one-time crosswalk against the National Library of Medicine's
public MeSH hierarchy would let us re-cut every finding and dashboard by
true clinical therapeutic area (Oncology, Cardiovascular, Endocrine, etc.)
instead of free-text strings — a scoped reference-table join, not a new
data source or pipeline. Rough estimate: **1-2 weeks** for a data engineer
to build and validate the crosswalk plus one dbt model to apply it — the
highest-leverage next investment for this suite's core question.

## Data Notes

- Phase-transition and approval "rates" here are relative-volume ratios,
  not true cohort transition probabilities — they can exceed 100% by
  construction, since CT.gov has no trial-to-trial phase-lineage field.
- The Phase 3 → Approval link relies on a best-effort exact-text match
  between CT.gov and FDA sponsor names (no shared ID exists); only 5.1% of
  trials link to a matched FDA sponsor, biased toward larger sponsors.
- Trial duration figures after ~2017 are right-censored (still-enrolling
  trials excluded) and will trend shorter than reality until those trials
  complete and are re-measured.
