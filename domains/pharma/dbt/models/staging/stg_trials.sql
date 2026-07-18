with source as (

    select * from {{ source('raw', 'ct_studies') }}

),

parsed as (

    select
        nct_id,
        payload -> 'protocolSection' -> 'identificationModule' ->> 'briefTitle' as brief_title,
        payload -> 'protocolSection' -> 'statusModule' ->> 'overallStatus' as overall_status,
        nullif(
            array_to_string(
                array(
                    select jsonb_array_elements_text(
                        payload -> 'protocolSection' -> 'designModule' -> 'phases'
                    )
                ),
                '|'
            ),
            ''
        ) as phase,
        (payload -> 'protocolSection' -> 'designModule' -> 'enrollmentInfo' ->> 'count')::int as enrollment_count,
        payload -> 'protocolSection' -> 'statusModule' -> 'startDateStruct' ->> 'date' as start_date_raw,
        payload -> 'protocolSection' -> 'statusModule' -> 'completionDateStruct' ->> 'date' as completion_date_raw,
        nullif(payload -> 'protocolSection' -> 'sponsorCollaboratorsModule' -> 'leadSponsor' ->> 'name', '') as sponsor_name,
        nullif(payload -> 'protocolSection' -> 'sponsorCollaboratorsModule' -> 'leadSponsor' ->> 'class', '') as sponsor_class,
        fetched_at as source_fetched_at
    from source

),

final as (

    select
        nct_id,
        brief_title,
        overall_status,
        phase,
        enrollment_count,
        -- CT.gov reports some dates at year-month precision only ("2020-07"); day is
        -- defaulted to the 1st for those (~37-39% of rows) rather than dropping the row.
        -- True absence (no date at all) passes through as NULL.
        case
            when length(start_date_raw) = 10 then start_date_raw::date
            when length(start_date_raw) = 7 then (start_date_raw || '-01')::date
            else null
        end as start_date,
        case
            when length(completion_date_raw) = 10 then completion_date_raw::date
            when length(completion_date_raw) = 7 then (completion_date_raw || '-01')::date
            else null
        end as completion_date,
        sponsor_name,
        sponsor_class,
        source_fetched_at
    from parsed

)

select * from final
