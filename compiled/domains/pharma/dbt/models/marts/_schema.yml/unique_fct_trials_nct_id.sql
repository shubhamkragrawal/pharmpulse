
    
    

select
    nct_id as unique_field,
    count(*) as n_records

from "pharmapulse"."marts"."fct_trials"
where nct_id is not null
group by nct_id
having count(*) > 1


