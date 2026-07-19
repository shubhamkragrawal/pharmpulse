
    
    

with all_values as (

    select
        submission_type as value_field,
        count(*) as n_records

    from "pharmapulse"."marts"."fct_approvals"
    group by submission_type

)

select *
from all_values
where value_field not in (
    'ORIG','SUPPL'
)


