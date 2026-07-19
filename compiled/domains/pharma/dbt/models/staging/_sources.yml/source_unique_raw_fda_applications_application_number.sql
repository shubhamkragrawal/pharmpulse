
    
    

select
    application_number as unique_field,
    count(*) as n_records

from "pharmapulse"."raw"."fda_applications"
where application_number is not null
group by application_number
having count(*) > 1


