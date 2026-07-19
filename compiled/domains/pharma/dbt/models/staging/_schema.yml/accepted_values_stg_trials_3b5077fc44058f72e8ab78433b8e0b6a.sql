
    
    

with all_values as (

    select
        overall_status as value_field,
        count(*) as n_records

    from "pharmapulse"."staging"."stg_trials"
    group by overall_status

)

select *
from all_values
where value_field not in (
    'ACTIVE_NOT_RECRUITING','APPROVED_FOR_MARKETING','AVAILABLE','COMPLETED','ENROLLING_BY_INVITATION','NO_LONGER_AVAILABLE','NOT_YET_RECRUITING','RECRUITING','SUSPENDED','TEMPORARILY_NOT_AVAILABLE','TERMINATED','UNKNOWN','WITHDRAWN','WITHHELD'
)


