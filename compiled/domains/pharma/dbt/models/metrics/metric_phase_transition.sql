-- FUNNEL CAVEAT (applies to ALL THREE rate columns, not just Approval):
-- CT.gov has no field linking a trial to its own phase-successor trial, so
-- is_phase2/is_phase3 counts for a condition are independent cross-sectional
-- volumes, not a followed cohort -- phase2_to_phase3_rate is NOT bounded at
-- 100% and is not a true transition probability (verified live: 14 of 109
-- conditions with >=100 Phase-2 trials show a rate above 100%, e.g. Diabetes
-- at 203%). Read all three rate columns as relative-volume ratios, not
-- literal P(reach next stage).
--
-- APPROVAL STAGE CAVEAT (an additional, compounding gap on top of the above):
-- CT.gov lead-sponsor names (dim_sponsor.sponsor_name) and FDA applicant names
-- (fct_approvals.sponsor_name) are different namespaces. No fuzzy matching or
-- entity resolution applied. Match rate is expected to be low; approval rates
-- derived here are directional/descriptive only, not true regulatory approval
-- rates. A named entity resolution step (future milestone) would be required
-- to harden this figure.
--
-- GROUPING NOTE: dim_condition.therapeutic_area is NULL for all rows as of M3
-- (no CT.gov source field, no MeSH crosswalk). This model groups by
-- condition_name instead (grouping_by_condition_name = TRUE) and retains
-- therapeutic_area as a NULL passthrough column so the interface doesn't
-- change when a crosswalk lands. See decisions.md.
--
-- GRAIN: one row per nct_id (bridge_trial_condition tie-broken to a single
-- representative condition per trial). condition_phase2_trials /
-- condition_phase3_trials / condition_approved_trials / the three rate columns
-- are window-function aggregates over the trial's condition_name group,
-- repeated on every row in that group -- dedupe to one row per condition_name
-- downstream for a funnel chart.

with bridge_ranked as (

    select
        nct_id,
        condition_key,
        row_number() over (partition by nct_id order by condition_key asc) as condition_rank,
        count(*) over (partition by nct_id) > 1 as multi_condition_flag
    from "pharmapulse"."marts"."bridge_trial_condition"

),

trial_condition as (

    select
        nct_id,
        condition_key,
        multi_condition_flag
    from bridge_ranked
    where condition_rank = 1

),

fda_applications as (

    -- collapse fct_approvals from submission-event grain (application_number,
    -- submission_type, submission_number) up to application grain before any
    -- metric touches it, per M3's as-built note (one row != one approval).
    select
        application_number,
        sponsor_name,
        bool_or(submission_status = 'AP') as has_approved_submission
    from "pharmapulse"."marts"."fct_approvals"
    group by application_number, sponsor_name

),

fda_sponsors as (

    select
        upper(trim(sponsor_name)) as sponsor_name_norm,
        count(distinct application_number) as fda_application_count,
        bool_or(has_approved_submission) as has_fda_approval
    from fda_applications
    where sponsor_name is not null
    group by upper(trim(sponsor_name))

),

trial_fda_match as (

    select
        fct_trials.nct_id,
        dim_sponsor.sponsor_name,
        fda_sponsors.sponsor_name_norm is not null as matched_to_fda,
        coalesce(fda_sponsors.has_fda_approval, false) as has_fda_approval
    from "pharmapulse"."marts"."fct_trials" as fct_trials
    left join "pharmapulse"."marts"."dim_sponsor" as dim_sponsor using (sponsor_key)
    left join fda_sponsors
        on upper(trim(dim_sponsor.sponsor_name)) = fda_sponsors.sponsor_name_norm

),

base as (

    select
        fct_trials.nct_id,
        trial_condition.condition_key,
        dim_condition.condition_name,
        dim_condition.therapeutic_area,
        true as grouping_by_condition_name,
        coalesce(trial_condition.multi_condition_flag, false) as multi_condition_flag,
        fct_trials.phase,
        coalesce(fct_trials.phase ilike '%PHASE2%', false) as is_phase2,
        coalesce(fct_trials.phase ilike '%PHASE3%', false) as is_phase3,
        trial_fda_match.sponsor_name,
        coalesce(trial_fda_match.matched_to_fda, false) as matched_to_fda,
        coalesce(trial_fda_match.has_fda_approval, false) as has_fda_approval
    from "pharmapulse"."marts"."fct_trials" as fct_trials
    left join trial_condition using (nct_id)
    left join "pharmapulse"."marts"."dim_condition" as dim_condition using (condition_key)
    left join trial_fda_match using (nct_id)

),

windowed as (

    select
        *,
        sum(case when is_phase2 then 1 else 0 end)
            over (partition by condition_name) as condition_phase2_trials,
        sum(case when is_phase3 then 1 else 0 end)
            over (partition by condition_name) as condition_phase3_trials,
        sum(case when matched_to_fda and has_fda_approval then 1 else 0 end)
            over (partition by condition_name) as condition_approved_trials
    from base

),

final as (

    select
        *,
        round(condition_phase3_trials::numeric / nullif(condition_phase2_trials, 0), 4) as phase2_to_phase3_rate,
        round(condition_approved_trials::numeric / nullif(condition_phase3_trials, 0), 4) as phase3_to_approval_rate,
        round(condition_approved_trials::numeric / nullif(condition_phase2_trials, 0), 4) as phase2_to_approval_rate
    from windowed

)

select * from final