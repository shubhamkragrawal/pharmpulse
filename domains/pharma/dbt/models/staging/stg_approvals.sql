{{
    config(
        post_hook="insert into ops.extraction_log (model_name, exclusion_reason, excluded_count) select '{{ this.name }}', 'application has no submissions array (empty or null)', count(*) from {{ source('raw', 'fda_applications') }} where coalesce(jsonb_array_length(payload -> 'submissions'), 0) = 0"
    )
}}

with source as (

    select * from {{ source('raw', 'fda_applications') }}

),

-- Applications with no submissions array are excluded here (no submission-level
-- grain exists for them); the excluded count is logged via the post-hook above
-- rather than silently dropped, per the staging missingness policy.
submissions as (

    select
        application_number,
        nullif(source.payload ->> 'sponsor_name', '') as sponsor_name,
        s.value ->> 'submission_type' as submission_type,
        s.value ->> 'submission_number' as submission_number,
        nullif(s.value ->> 'submission_status', '') as submission_status,
        s.value ->> 'submission_status_date' as submission_status_date_raw,
        nullif(s.value ->> 'review_priority', '') as review_priority,
        fetched_at as source_fetched_at
    from source
    cross join lateral jsonb_array_elements(coalesce(source.payload -> 'submissions', '[]'::jsonb)) as s(value)

),

final as (

    select
        {{ generate_surrogate_key(['application_number', 'submission_type', 'submission_number']) }} as approval_key,
        application_number,
        sponsor_name,
        submission_type,
        submission_number,
        submission_status,
        -- submission_status_date arrives as an unpunctuated YYYYMMDD string; a small
        -- number of submissions omit it entirely (NULL passthrough).
        case
            when submission_status_date_raw ~ '^\d{8}$'
                then to_date(submission_status_date_raw, 'YYYYMMDD')
            else null
        end as submission_status_date,
        review_priority,
        source_fetched_at
    from submissions

)

select * from final
