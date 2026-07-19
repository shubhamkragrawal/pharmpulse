
    
    

with all_values as (

    select
        sponsor_class as value_field,
        count(*) as n_records

    from (select * from "pharmapulse"."staging"."stg_trials" where sponsor_class is not null) dbt_subquery
    group by sponsor_class

)

select *
from all_values
where value_field not in (
    'AMBIG','FED','INDIV','INDUSTRY','NETWORK','NIH','OTHER','OTHER_GOV','UNKNOWN'
)


