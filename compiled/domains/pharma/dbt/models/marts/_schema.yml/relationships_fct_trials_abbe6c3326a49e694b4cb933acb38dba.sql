
    
    

with child as (
    select sponsor_key as from_field
    from (select * from "pharmapulse"."marts"."fct_trials" where sponsor_key is not null) dbt_subquery
    where sponsor_key is not null
),

parent as (
    select sponsor_key as to_field
    from "pharmapulse"."marts"."dim_sponsor"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


