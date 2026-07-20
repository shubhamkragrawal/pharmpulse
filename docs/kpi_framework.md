# PharmaPulse — KPI Framework

## Purpose

This is a portfolio BA artifact: for each metric surfaced in the Streamlit
explorer / Tableau dashboards, it pins down the chain **business question →
exact formula → source model → owner → refresh cadence → known caveat**. The
goal is that no metric in this project is "just a number on a chart" — every
one traces back to a real SQL definition in `domains/pharma/dbt/models/`
and a named owner, so the dashboards don't go stale the moment they ship
(a flag raised by the BA persona in `REVIEW_REPORT.md`: an unowned metric is
how dashboards go stale).

**The business question the whole dashboard suite answers:**
*Where should a mid-size pharma company focus R&D investment?*

Every KPI below is a lens on that one question — trial funnel efficiency,
sponsor competitive positioning, or timeline planning.

**A note on `therapeutic_area`:** the ideal cut for all of these KPIs is
clinical therapeutic area (e.g. Oncology, Cardiovascular, Endocrine). That
column exists on `dim_condition` but is NULL for every row — CT.gov has no
source field for it, and building it requires an external MeSH tree-number
crosswalk, which was explicitly scoped out of M3 (see `decisions.md`,
"`dim_condition.mesh_term` and `.therapeutic_area` are always NULL for M3").
Every KPI below that would ideally group by therapeutic area instead groups
by `condition_name` — CT.gov's free-text condition field — as an interim,
more-granular proxy. This is the single limitation the "Decision Ask" in
`docs/executive_memo.md` proposes fixing.

---

### KPI 1: Phase 2 → Phase 3 Transition Rate (by condition)
- **Business question:** For which conditions does the largest share of
  Phase 2 trial volume carry through to Phase 3 — a directional signal for
  where the pipeline is thinning out earliest?
- **Formula:**
  ```sql
  SELECT DISTINCT condition_name, phase2_to_phase3_rate
  FROM metrics.metric_phase_transition
  -- phase2_to_phase3_rate = condition_phase3_trials / condition_phase2_trials,
  -- rounded to 4 decimal places (window aggregates, repeated per row within
  -- a condition_name group -- DISTINCT to get one row per condition)
  ```
- **Source model:** `metrics.metric_phase_transition`
- **Grain:** one row per `condition_name` (deduped from the model's native
  one-row-per-`nct_id` grain)
- **Owner:** Clinical Analytics Manager
- **Refresh cadence:** on every `dbt build`. Extraction is currently manual
  (`make extract`), not orchestrated — cadence becomes daily/scheduled once
  Airflow orchestration (README "To-Do") is built.
- **Known caveats:**
  - Grouped by `condition_name`, not `therapeutic_area` — the latter is
    NULL for all rows as of M3; `condition_name` is real but far more
    granular (hundreds of buckets), so dashboards filter to top-N by volume
    (`decisions.md`, "`metric_phase_transition` groups by `condition_name`,
    not `therapeutic_area`").
  - This is a **relative-volume ratio, not a true cohort transition
    probability** — CT.gov has no field linking a trial to its own
    phase-successor trial, so Phase 2 and Phase 3 counts per condition are
    independent cross-sectional volumes and can exceed 100% (verified: 14 of
    109 conditions with ≥100 Phase-2 trials do, e.g. Diabetes at 203%; see
    `decisions.md`).
  - Trials with >1 reported condition are tie-broken to a single
    representative condition (first-listed by `condition_key`); the
    `multi_condition_flag` column marks every row this affected, so the
    tie-break is auditable, not silent.

### KPI 2: Phase 3 → Approval Rate
- **Business question:** Of trials that reach Phase 3 for a given condition,
  what share are associated with an eventual FDA approval — directional
  signal for regulatory follow-through, not a literal per-trial odds ratio.
- **Formula:**
  ```sql
  SELECT DISTINCT condition_name, phase3_to_approval_rate
  FROM metrics.metric_phase_transition
  -- phase3_to_approval_rate = condition_approved_trials / condition_phase3_trials,
  -- rounded to 4 decimal places
  ```
- **Source model:** `metrics.metric_phase_transition`
- **Grain:** one row per `condition_name`
- **Owner:** Regulatory Affairs Analyst
- **Refresh cadence:** same as KPI 1.
- **Known caveats:**
  - The Approval stage depends on a **best-effort `sponsor_name` join**
    between CT.gov lead-sponsor names and FDA applicant names —
    `UPPER(TRIM())` exact string match, no entity resolution, because the
    two sources have no shared key (`decisions.md`, "`metric_phase_transition`
    Approval stage uses best-effort `sponsor_name` join"). The `matched_to_fda`
    flag on every row makes the match rate visible rather than hidden.
  - Match rate is low overall — only 30,307 of 594,309 trials (5.1%) link to
    any FDA-matched sponsor at all (M4 notebook, Insight 3) — and is biased
    toward large sponsors, whose names are more likely to match exactly.
  - Same relative-volume-ratio caveat as KPI 1: can exceed 100% (192 of
    1,529 conditions with ≥5 Phase-3 trials do — M4 notebook, Insight 2).
  - `fct_approvals` is aggregated up from submission-event grain to
    application grain before joining, so one FDA "approval" here can
    represent multiple underlying submission events for the same
    application.

### KPI 3: Overall Phase 2 → Approval Rate (portfolio-wide)
- **Business question:** Across the entire trial portfolio (not
  condition-by-condition), what share of Phase 2 volume associates with
  eventual FDA approval — the single top-line pipeline-efficiency number for
  the "where to invest" question.
- **Formula:**
  ```sql
  SELECT SUM(condition_approved_trials)::float / SUM(condition_phase2_trials)
  FROM (
      SELECT DISTINCT condition_name, condition_phase2_trials, condition_approved_trials
      FROM metrics.metric_phase_transition
  ) t
  -- roll-up of the same per-condition window aggregates KPI 1/2 use;
  -- DISTINCT first, since the aggregates repeat per underlying trial row
  ```
- **Source model:** `metrics.metric_phase_transition`
- **Grain:** one row, portfolio-wide (aggregate across all `condition_name`
  groups)
- **Owner:** Head of Clinical Analytics
- **Refresh cadence:** same as KPI 1.
- **Known caveats:** compounds both KPI 1 and KPI 2's caveats — it is a
  relative-volume ratio (not a followed-cohort probability), it inherits the
  best-effort FDA sponsor-name join's low/biased match rate, and it is
  computed over the `condition_name` proxy, not `therapeutic_area`. Treat
  this number as "directional pipeline signal," never quote it as
  "P(a Phase 2 trial gets approved)."

### KPI 4: Sponsor Trial Success Rate
- **Business question:** Which sponsors reliably complete the trials they
  start — a competitive-execution signal for partnership/investment
  screening.
- **Formula:**
  ```sql
  SELECT sponsor_name, sponsor_class, trials_total, trials_completed, success_rate
  FROM marts.dim_sponsor
  -- success_rate = trials_completed / trials_total, rounded to 4 decimal places
  -- (precomputed column, not recalculated downstream)
  ```
- **Source model:** `marts.dim_sponsor`
- **Grain:** one row per `sponsor_name`
- **Owner:** Sponsor Intelligence Analyst
- **Refresh cadence:** same as KPI 1.
- **Known caveats:**
  - "Success" = `overall_status = 'COMPLETED'` only. A trial that's still
    recruiting isn't a failure, but this metric can't distinguish
    "still running" from "gave up" — it only sees the current status
    snapshot at extraction time.
  - Low-volume sponsors (1-2 trials) produce misleadingly extreme 0%/100%
    rates; the Sponsor League Table dashboard mitigates this with a minimum
    trial-count filter, but the raw `dim_sponsor.success_rate` column has no
    such floor built in.

### KPI 5: Sponsor Cohort 10-Year Survivorship Rate
- **Business question:** Of sponsors who entered the trial ecosystem in a
  given year, what share are still actively running trials a decade later —
  a proxy for sustained R&D commitment and financial viability.
- **Formula:**
  ```sql
  SELECT cohort_year, survivorship_rate
  FROM metrics.metric_sponsor_cohorts
  WHERE years_since_cohort = 10
  -- survivorship_rate = active_sponsor_count / cohort_launch_sponsor_count,
  -- rounded to 4 decimal places
  ```
- **Source model:** `metrics.metric_sponsor_cohorts`
- **Grain:** one row per `(cohort_year, activity_year)`; filtered to
  `years_since_cohort = 10` for this specific cut.
- **Owner:** Sponsor Intelligence Analyst
- **Refresh cadence:** same as KPI 1.
- **Known caveats:**
  - A trial with a NULL `completion_date` is treated as active only in its
    `start_date` year, not open-ended — a deliberately conservative choice
    to avoid inflating survivorship for cohorts with a lot of still-enrolling
    trials (`decisions.md`, "`metric_sponsor_cohorts` treats a NULL
    `completion_date` as active only in the trial's start year"). This
    **undercounts** survivorship most severely for the most recent cohorts,
    whose still-active trials look like drop-offs.
  - Sponsors with an all-NULL `start_date` are excluded from cohorting
    entirely (can't be assigned a `cohort_year`).

### KPI 6: Median Trial Duration, Year-over-Year
- **Business question:** Are trials taking longer or shorter to complete
  over time — informs sponsor timeline planning and budget assumptions for
  new trial commitments.
- **Formula:**
  ```sql
  SELECT start_year, median_duration_days, yoy_change_pct
  FROM metrics.metric_duration_trends
  -- median_duration_days = PERCENTILE_CONT(0.5) of duration_days, rounded to 1 decimal
  -- yoy_change_pct = (median_duration_days - LAG(median_duration_days)) / LAG(...) * 100,
  --   rounded to 2 decimal places, NULL for the earliest start_year
  ```
- **Source model:** `metrics.metric_duration_trends`
- **Grain:** one row per `start_year`
- **Owner:** Clinical Operations Analyst
- **Refresh cadence:** same as KPI 1.
- **Known caveats:**
  - **Right-censoring, post-~2017:** `duration_days` requires a non-null
    `completion_date`. Recent-year trials that are long-running are
    disproportionately still enrolling and so are excluded from the median
    — only the fast-completing recent trials have a measurable duration yet.
    The apparent drop from ~4,200 days (1990) to ~700 days (2020) is **not**
    a real speed-up; it's a measurement artifact of which trials have
    finished. `decisions.md` and the M4 notebook (Insight 7) both flag this;
    the Streamlit dashboard renders the post-2017 segment as a dashed line
    for this reason.
  - `metric_duration_trends_by_phase` is a separate model at grain
    `(start_year, phase)` — do not sum its `trial_count` across phases and
    expect it to reconcile exactly with this model's `trial_count`
    (`decisions.md`).

### KPI 7: Termination Rate by Phase
- **Business question:** At which trial phase is early-stop risk highest —
  informs risk-adjusted timeline and budget planning for a trial at a given
  phase.
- **Formula:**
  ```sql
  SELECT
      phase,
      COUNT(*) FILTER (WHERE is_terminated) AS terminated_trials,
      COUNT(*) AS total_trials,
      COUNT(*) FILTER (WHERE is_terminated)::float / COUNT(*) AS termination_rate
  FROM marts.fct_trials
  WHERE phase IS NOT NULL
  GROUP BY phase
  ```
- **Source model:** `marts.fct_trials`. There is no dedicated
  `metrics`-layer model for this KPI — it's computed directly off
  `fct_trials`, the same pattern `scripts/export_tableau_extracts.py`'s
  `export_termination_reasons()` / `export_phase_distribution()` functions
  use to build the Termination Reasons dashboard.
- **Grain:** one row per `phase` (raw pipe-delimited value — a combined
  phase string like `"PHASE1|PHASE2"` is its own bucket, same convention as
  `metric_duration_trends_by_phase`).
- **Owner:** Clinical Operations Analyst
- **Refresh cadence:** same as KPI 1.
- **Known caveats:**
  - `phase` is NULL for ~24% of trials (observational studies, by design)
    — excluded from the denominator entirely, not bucketed into a
    fabricated "Unknown" phase.
  - `why_stopped` (the free-text reason) is populated for only ~7.8% of
    trials and has zero normalization applied (`decisions.md`, "`why_stopped`
    added to `stg_trials`/`fct_trials` in M5") — this KPI answers *how often*
    trials terminate by phase, not *why*; the reason-level breakdown is
    representative of reported reasons only.
  - Real computed rates (current data): Phase 1/Phase 2 combined and Phase 2
    show the highest termination rates (~11.2-11.4%), Early Phase 1 the
    lowest of the labeled phases (6.4%); "Not Reported" phase trials show an
    unexplained low rate (3.25%) that likely reflects a different
    `overall_status` mix in that bucket, not necessarily lower true risk —
    flagged as observed, not explained.

### KPI 8: FDA Approval Volume, Year-over-Year
- **Business question:** Is FDA approval throughput growing or shrinking
  year over year — a headline regulatory-environment indicator for planning
  submission timing.
- **Formula:**
  ```sql
  SELECT
      EXTRACT(YEAR FROM approval_date)::int AS approval_year,
      COUNT(*) AS approval_count
  FROM marts.fct_approvals
  WHERE submission_status = 'AP' AND approval_date IS NOT NULL
  GROUP BY 1
  ORDER BY 1
  ```
- **Source model:** `marts.fct_approvals`
- **Grain:** one row per `approval_year`, aggregated from the fact's native
  submission-event grain (`approval_key` = `application_number` +
  `submission_type` + `submission_number`) — **not** collapsed to
  `application_number` first. `fct_approvals` is deliberately kept at this
  3-part grain rather than one row per application, because collapsing to
  application-level silently discards supplement-level approvals (label
  expansions, new indications) that are each independently a regulatory
  action (`decisions.md`, "`fct_approvals` kept at the 3-part submission-event
  grain, not `application_number` alone"). One row in this KPI's result is
  one approved submission event, not one distinct approved drug — a single
  application can contribute multiple rows across years via its
  supplements.
- **Owner:** Regulatory Affairs Analyst
- **Refresh cadence:** same as KPI 1.
- **Known caveats:**
  - <0.01% of `fct_approvals` rows are missing `approval_date` and are
    excluded from the yearly grouping entirely (not imputed).
  - **Known divergence from the shipped Approval Landscape dashboard:**
    `scripts/export_tableau_extracts.py`'s `export_approval_landscape()`
    (built in M5) collapses to one row per `(application_number,
    sponsor_name)` using each application's *first* approval date, i.e. it
    counts distinct applications, not submission events. That dashboard cut
    undercounts true approval-event volume for the same reason the
    `fct_approvals` grain decision above exists — this KPI's formula is the
    grain-correct one; the dashboard's is a simplification that was not
    revisited as of M6. Flagged here, not fixed, since M6 is a docs
    milestone.
