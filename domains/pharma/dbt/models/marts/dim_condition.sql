with source as (

    select distinct condition_name
    from {{ ref('stg_trial_conditions') }}

),

final as (

    select
        {{ generate_surrogate_key(['condition_name']) }} as condition_key,
        condition_name,
        -- CT.gov's derived MeSH terms (derivedSection.conditionBrowseModule.meshes)
        -- are study-level, not paired to individual free-text conditions -- no
        -- reliable per-condition mapping exists, so these are NULL passthrough
        -- rather than a guessed pairing. therapeutic_area has no source field at
        -- all (would require an external MeSH tree-number crosswalk).
        cast(null as text) as mesh_term,
        cast(null as text) as therapeutic_area
    from source

)

select * from final
