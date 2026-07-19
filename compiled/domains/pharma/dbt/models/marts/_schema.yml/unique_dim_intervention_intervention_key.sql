
    
    

select
    intervention_key as unique_field,
    count(*) as n_records

from "pharmapulse"."marts"."dim_intervention"
where intervention_key is not null
group by intervention_key
having count(*) > 1


