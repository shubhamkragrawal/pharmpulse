
    
    

select
    condition_name as unique_field,
    count(*) as n_records

from "pharmapulse"."marts"."dim_condition"
where condition_name is not null
group by condition_name
having count(*) > 1


