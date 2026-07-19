
    
    

select
    sponsor_key as unique_field,
    count(*) as n_records

from "pharmapulse"."marts"."dim_sponsor"
where sponsor_key is not null
group by sponsor_key
having count(*) > 1


