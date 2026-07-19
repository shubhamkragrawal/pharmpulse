
    
    

with child as (
    select condition_key as from_field
    from "pharmapulse"."marts"."bridge_trial_condition"
    where condition_key is not null
),

parent as (
    select condition_key as to_field
    from "pharmapulse"."marts"."dim_condition"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


