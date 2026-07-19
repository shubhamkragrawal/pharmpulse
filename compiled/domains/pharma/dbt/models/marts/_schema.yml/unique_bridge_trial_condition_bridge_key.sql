
    
    

select
    bridge_key as unique_field,
    count(*) as n_records

from "pharmapulse"."marts"."bridge_trial_condition"
where bridge_key is not null
group by bridge_key
having count(*) > 1


