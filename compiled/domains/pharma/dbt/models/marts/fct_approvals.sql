with source as (

    select * from "pharmapulse"."staging"."stg_approvals"

),

final as (

    select
        approval_key,
        application_number,
        sponsor_name,
        submission_type,
        submission_status,
        submission_status_date as approval_date,
        review_priority
    from source

)

select * from final