
    
    

select
    sponsor_name as unique_field,
    count(*) as n_records

from "pharmapulse"."staging"."stg_sponsors"
where sponsor_name is not null
group by sponsor_name
having count(*) > 1


