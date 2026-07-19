
    
    

select
    duration_by_phase_key as unique_field,
    count(*) as n_records

from "pharmapulse"."metrics"."metric_duration_trends_by_phase"
where duration_by_phase_key is not null
group by duration_by_phase_key
having count(*) > 1


