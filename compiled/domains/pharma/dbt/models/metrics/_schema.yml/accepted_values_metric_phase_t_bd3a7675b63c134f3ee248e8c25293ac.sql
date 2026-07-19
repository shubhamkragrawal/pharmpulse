
    
    

with all_values as (

    select
        grouping_by_condition_name as value_field,
        count(*) as n_records

    from "pharmapulse"."metrics"."metric_phase_transition"
    group by grouping_by_condition_name

)

select *
from all_values
where value_field not in (
    'True'
)


