
    
    

with child as (
    select sponsor_name as from_field
    from "pharmapulse"."staging"."stg_trials"
    where sponsor_name is not null
),

parent as (
    select sponsor_name as to_field
    from "pharmapulse"."staging"."stg_sponsors"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


