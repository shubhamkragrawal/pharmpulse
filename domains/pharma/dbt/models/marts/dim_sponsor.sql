with source as (

    select * from {{ ref('stg_sponsors') }}

),

final as (

    select
        {{ generate_surrogate_key(['sponsor_name']) }} as sponsor_key,
        sponsor_name,
        sponsor_class
    from source

)

select * from final
