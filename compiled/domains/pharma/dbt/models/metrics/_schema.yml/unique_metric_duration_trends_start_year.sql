
    
    

select
    start_year as unique_field,
    count(*) as n_records

from "pharmapulse"."metrics"."metric_duration_trends"
where start_year is not null
group by start_year
having count(*) > 1


