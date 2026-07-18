# PharmaPulse

A domain-agnostic ELT warehouse platform — pharma regulatory 
data as the reference implementation.

Pulls from ClinicalTrials.gov (594K+ trials) and openFDA 
(29K+ FDA applications), transforms via dbt into a tested 
star schema, and serves as the data foundation for a 
6-project AI/ML portfolio.

## Current status

#### Done

- ✅ domain-agnostic core/domains scaffold
- ✅ raw extraction layer (594,309 trials, 29,218 FDA applications)
- ✅ dbt staging models (24/24 tests green)

#### To-Do

- star schema marts (in progress)
- metrics layer + dashboards
- Airflow orchestration

## Quick start
```bash
git clone https://github.com/shubhamkragrawal/pharmpulse
cd pharmpulse
uv sync
cp .env.example .env   # fill in your values
make start             # starts Postgres container
make extract           # pulls ClinicalTrials.gov + openFDA
```

## Architecture
Domain-agnostic core (`core/`) + pharma-specific implementation 
(`domains/pharma/`). Adding a second domain = new folder, 
zero changes to core.

See `decisions.md` for every non-trivial engineering decision 
made during the build, with failure modes and scaling notes.

## Part of a larger portfolio

PharmaPulse is the data foundation for a multi-project AI/ML 
portfolio — every downstream project (ML prediction, NER, 
agentic RAG, causal inference, open benchmarking) reads 
from this warehouse.

Full portfolio: [coming soon]