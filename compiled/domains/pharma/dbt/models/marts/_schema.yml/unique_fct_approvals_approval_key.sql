
    
    

select
    approval_key as unique_field,
    count(*) as n_records

from "pharmapulse"."marts"."fct_approvals"
where approval_key is not null
group by approval_key
having count(*) > 1


