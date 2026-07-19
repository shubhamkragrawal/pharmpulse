with trials as (

    select sponsor_name, sponsor_class
    from "pharmapulse"."staging"."stg_trials"
    where sponsor_name is not null

),

-- Same sponsor_name occasionally reports a different sponsor_class across trials
-- (real data-quality wrinkle, not a bug) -- resolved by taking the most frequent
-- class per sponsor, ties broken alphabetically for determinism.
class_counts as (

    select
        sponsor_name,
        sponsor_class,
        count(*) as n,
        row_number() over (
            partition by sponsor_name
            order by count(*) desc, sponsor_class asc nulls last
        ) as rn
    from trials
    group by sponsor_name, sponsor_class

),

final as (

    select
        sponsor_name,
        sponsor_class
    from class_counts
    where rn = 1

)

select * from final