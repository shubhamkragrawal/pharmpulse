
    
    

select
    nct_id as unique_field,
    count(*) as n_records

from "pharmapulse"."raw"."ct_studies"
where nct_id is not null
group by nct_id
having count(*) > 1


