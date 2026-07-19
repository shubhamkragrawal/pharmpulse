
    
    

with all_values as (

    select
        intervention_type as value_field,
        count(*) as n_records

    from "pharmapulse"."marts"."dim_intervention"
    group by intervention_type

)

select *
from all_values
where value_field not in (
    'DRUG','DEVICE','BIOLOGICAL','PROCEDURE','BEHAVIORAL','DIETARY_SUPPLEMENT','DIAGNOSTIC_TEST','RADIATION','GENETIC','COMBINATION_PRODUCT','OTHER'
)


