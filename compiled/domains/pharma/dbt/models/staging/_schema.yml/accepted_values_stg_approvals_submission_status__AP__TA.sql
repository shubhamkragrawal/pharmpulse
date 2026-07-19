
    
    

with all_values as (

    select
        submission_status as value_field,
        count(*) as n_records

    from (select * from "pharmapulse"."staging"."stg_approvals" where submission_status is not null) dbt_subquery
    group by submission_status

)

select *
from all_values
where value_field not in (
    'AP','TA'
)


