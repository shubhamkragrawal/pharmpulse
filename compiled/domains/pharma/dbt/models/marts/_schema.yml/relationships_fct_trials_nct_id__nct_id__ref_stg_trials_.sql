
    
    

with child as (
    select nct_id as from_field
    from "pharmapulse"."marts"."fct_trials"
    where nct_id is not null
),

parent as (
    select nct_id as to_field
    from "pharmapulse"."staging"."stg_trials"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


