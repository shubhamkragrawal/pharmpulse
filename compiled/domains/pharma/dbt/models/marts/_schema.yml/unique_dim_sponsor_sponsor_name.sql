
    
    

select
    sponsor_name as unique_field,
    count(*) as n_records

from "pharmapulse"."marts"."dim_sponsor"
where sponsor_name is not null
group by sponsor_name
having count(*) > 1


