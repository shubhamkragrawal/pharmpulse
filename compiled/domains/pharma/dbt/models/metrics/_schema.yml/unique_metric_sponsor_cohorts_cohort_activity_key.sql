
    
    

select
    cohort_activity_key as unique_field,
    count(*) as n_records

from "pharmapulse"."metrics"."metric_sponsor_cohorts"
where cohort_activity_key is not null
group by cohort_activity_key
having count(*) > 1


