
    
    

with child as (
    select intervention_key as from_field
    from "pharmapulse"."marts"."bridge_trial_intervention"
    where intervention_key is not null
),

parent as (
    select intervention_key as to_field
    from "pharmapulse"."marts"."dim_intervention"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


