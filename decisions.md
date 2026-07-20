# PharmaPulse — Decision Log


> Engineering decisions made during the build, with rationale, failure modes, 
> scaling implications, and the interview question each decision maps to.
> Updated after every milestone.

## Decision: `core/` (domain-agnostic) vs `domains/pharma/` (domain-specific) split
- **What:** `core/extractor_base.py` defines pagination, retry/backoff, checkpoint read/write, and idempotent upsert as an abstract class with zero knowledge of trials, sponsors, or any pharma vocabulary — it operates on generic `record`/`record_id`/`target_table` concepts. `domains/pharma/extractors.py` supplies `CTGovExtractor` and `OpenFDAExtractor` as thin subclasses. `core/config.py` + `core/extraction_runner.py` read `config.yaml`'s `active_domain` at runtime and dynamically import `domains.<active_domain>.extractors` — the runner itself never names pharma. Same pattern in `core/airflow/dag_template.py`.
- **Why (vs. alternatives):** The alternative — one `extractor.py` with `if domain == "pharma"` branches, or CT.gov/openFDA-specific code directly in the base class — is faster to write today but means a second domain (e.g., SEC filings for a non-healthcare pivot) requires editing tested core plumbing instead of adding an isolated `domains/finance/` folder. Spec Section 0 and the three-persona review (`REVIEW_REPORT.md`) both call this out as a first-class architectural bet, not a refactor-later nice-to-have.
- **Failure mode:** If a pharma-specific assumption leaks into `core/` (e.g., a field name, a hardcoded table, an assumed nested JSON shape like `protocolSection.identificationModule`), genericity silently breaks and the "prove it" unit test (`tests/test_extractor_base.py`) will not exercise the leak because it wasn't written to catch that specific field — the real safety net is periodically grepping `core/` for domain vocabulary, not just the one test passing.
- **Scaling story (10x/100x):** At 10x (a second domain added), the split is validated for real — either it costs zero core changes as designed, or it doesn't and the boundary was drawn wrong. At 100x (5+ domains, dozens of extractors), the current pattern (config-driven class lookup via `extractor_class` string in each domain's `config.yaml`) still holds without change; the thing that would need to evolve is `core/extraction_runner.py` running extractors sequentially — at that scale it'd need to fan out concurrently (asyncio or a worker pool) rather than looping one source at a time.
- **Interview question this maps to:** "How do you design a system to support a second, very different data domain without a rewrite?" / "Show me a codebase boundary you drew and how you'd prove it holds."

## Decision: checkpoint table stores a `resume_cursor` column in addition to the spec's `last_page_completed INT`
- **What:** Added a nullable `resume_cursor TEXT` column to `raw.extraction_checkpoints`, beyond the 5 columns in the spec's schema block (`source`, `last_page_completed`, `last_run_started_at`, `last_run_completed_at`, `status`).
- **Why (vs. alternatives):** ClinicalTrials.gov API v2 paginates via an opaque `nextPageToken` cursor, not a numeric page offset — there is no page 47 to ask for directly, only "the page after this token." `last_page_completed INT` alone is enough to know *how far* the extractor got (and is what M1's kill/resume proof reports), but resuming CT.gov specifically requires replaying the actual token, which doesn't fit in an INT column. openFDA's `skip`/`limit` pagination doesn't need this (a plain integer offset resumes it fine), so the column is nullable and unused for that source. This is implementation-forced by the real API shape, not a scope add — flagging per your standing instruction rather than changing the schema silently.
- **Failure mode:** If `resume_cursor` is null but `status` was left `running` from a crashed process on a cursor-paginated source, resume falls back to `cursor=None`, which `fetch_page` will interpret as "start of the underlying source" — i.e., it silently restarts a cursor-based source from the beginning instead of resuming, even though `last_page_completed` looks like it points partway through. Upsert idempotency (`nct_id` as natural key) makes this wasteful, not incorrect.
- **Scaling story (10x/100x):** Holds as-is even for many cursor-paginated sources, since the column is generic (not CT.gov-specific). At 100x extraction volume, the real change needed is checkpointing more often than once per page (e.g., every N records) so a mid-page failure on a huge page size doesn't waste as much re-fetch work.
- **Interview question this maps to:** "Tell me about a time a spec's schema didn't survive contact with the real API." / "Cursor vs. offset pagination — when does each break down?"

## Decision: checkpoint-based resume is the primary recovery mechanism; upsert idempotency is the safety net, not the strategy
- **What:** On a mid-pagination failure, `BaseExtractor.run()` reads `raw.extraction_checkpoints` and resumes from `last_page_completed + 1` (plus `resume_cursor` for token-paginated sources). Natural-key upsert (`ON CONFLICT (nct_id) DO UPDATE`) still runs on every page as a second layer, so a page processed twice is harmless — but the design does not rely on "just restart from page 0 every time and let upsert dedupe it."
- **Why (vs. alternatives):** Restart-from-zero + idempotent-upsert-as-safety-net is simpler to write and was explicitly called out as the *wrong* default in the spec's Review & Revisions section (AI Engineer persona: relying on idempotency alone "wastes API quota and time at scale, even if it's technically correct"). Verified live: killing the CT.gov run at page 22 (~23,000 rows) and resuming picked up at page 23 in a few seconds, instead of re-fetching and re-upserting 23 pages it already had.
- **Failure mode:** If `_checkpoint()` and `_upsert()` are ever reordered so the checkpoint commits *before* the upsert, a crash between the two would mark a page "done" whose records never landed — the checkpoint would lie. Current code upserts first, checkpoints second, specifically to avoid this.
- **Scaling story (10x/100x):** At 10x the page size (or 10x the number of sources running concurrently), per-page checkpointing still bounds the worst-case re-fetch to one page, which is why page size — not just page count — is a real tuning knob; too-large a page size (we used 1000) trades fewer round trips for more wasted work on a crash right before a checkpoint.
- **Interview question this maps to:** "Walk me through your failure-recovery design for a long-running ingestion job." / "Why not just make everything idempotent and skip checkpointing?"

## Decision: remapped local Postgres container to host port 5433
- **What:** `docker-compose.yml`'s Postgres service publishes `${POSTGRES_PORT:-5433}:5432` instead of the conventional `5432:5432`; `.env.example`'s `POSTGRES_PORT` default was updated to match.
- **Why (vs. alternatives):** Discovered live — this machine already runs a native Postgres process bound to `127.0.0.1:5432`/`::1:5432` outside Docker. Docker's proxy could still bind the wildcard address on 5432, but macOS resolves `localhost` connections to the pre-existing native process first, so anything connecting via `localhost:5432` silently hit the wrong database ("role does not exist") instead of failing loudly. Remapping to 5433 avoids touching that unrelated, already-running service.
- **Failure mode:** Anyone cloning this repo on a machine *without* a conflicting local Postgres would have been fine on the default 5432 — this fix is specific to this dev machine's state, not a general correctness issue with the original spec. If `.env` and `docker-compose.yml` ever drift out of sync on the port value, connections fail with a plain "connection refused" (loud), not the silent wrong-database failure this fix avoids.
- **Scaling story (10x/100x):** N/A — purely a local dev-environment collision, not a production concern (production Postgres wouldn't share a host with an unrelated native instance).
- **Interview question this maps to:** "Tell me about a bug that wasn't in your code." (Good example of a silent-wrong-target failure mode vs. a loud one, and why the loud one is preferable.)

## Decision: `uv run <script>` is not a safe target for `kill -9` in a background job — invoke the venv interpreter directly
- **What:** During the M1 kill/resume proof, `kill -9` on the PID returned by `nohup uv run python scripts/run_ctgov_extraction.py &` killed only the `uv` launcher process, not the Python worker it had forked — the worker got reparented to PID 1 and kept running as an orphan, invisibly racing a second "resumed" process for several minutes. Switched to launching via `.venv/bin/python` directly (bypassing the `uv run` wrapper) for anything that needs to be killed and observed by PID; `Makefile`'s `extract`/`test` targets still use `uv run` since nothing there needs mid-run signal handling.
- **Why (vs. alternatives):** Could have used `kill -9 -$PID` (negative PID, kills the whole process group) and kept `uv run` — that also works and is arguably more idiomatic for background job management in general, but doesn't remove the underlying fragility (a launcher that forks instead of exec'ing means "the PID I have" and "the PID doing the work" can silently diverge). For this project, invoking the interpreter directly for anything requiring precise process control is the simpler fix.
- **Failure mode observed, live:** Two extractor processes wrote to the same `raw.ct_studies`/`raw.extraction_checkpoints` rows concurrently for ~5 minutes with no coordination beyond a blind `UPDATE` in `_checkpoint()` (no compare-and-swap, no advisory lock). Result: idempotent upsert absorbed the duplicate writes cleanly (zero duplicate `nct_id`s afterward), but `last_page_completed` could have regressed if the slower process's write landed after the faster one's — it happened not to, but the checkpoint UPDATE has no protection against that ordering. A single-threaded design assumption (only one extractor process per source at a time) was true operationally but was never enforced in code.
- **Scaling story (10x/100x):** At 10x, if `extraction_checkpoints` writes ever needed to tolerate legitimate concurrent workers (e.g., sharding CT.gov extraction by date range across processes), the checkpoint table would need either a monotonic guard (`WHERE last_page_completed < %s`) or to move to per-shard checkpoint rows instead of one row per source — the current single-row-per-source design implicitly assumes single-writer.
- **Interview question this maps to:** "Tell me about a race condition you found by accident, not by design review." / "What guarantees does your checkpoint table actually enforce, versus what you assumed it enforced?"

## Decision: `OpenFDAExtractor` repurposes `cursor` as a keyset (last-seen `application_number`), not skip/limit
- **What:** Discovered live during M2: openFDA's `skip` parameter hard-errors (400) once `skip` reaches ~25,000, permanently capping the old `skip = page_index * page_size` approach at 25,100/29,218 applications no matter how many retries. Rewrote `fetch_page` to sort by `application_number:asc` and page via an exclusive range filter (`search=application_number:{<last_seen> TO *}`), always requesting `skip=0`. `cursor` in `PageResult`/`resume_cursor` now holds the last-seen `application_number` string for this extractor, reusing the same generic checkpoint/resume plumbing `core/extractor_base.py` already provides for CT.gov's opaque token cursor — no core changes needed.
- **Why (vs. alternatives):** Could have kept skip/limit and windowed around the 25K ceiling (reset skip to 0 every ~24,900 records using successive range filters), but that requires tracking two state variables (window boundary + in-window skip) for no benefit over pure keyset pagination, which needs only one (last-seen key) and has no ceiling at any data volume. Verified against the real API before implementing (`curl` with `sort` + exclusive-range `{X TO *}` both confirmed working against `api.fda.gov`) rather than guessing at Lucene range syntax.
- **Failure mode:** Because the pagination *mechanism* changed entirely (not just its parameters), the old checkpoint's `resume_cursor = NULL` with `last_page_completed = 250` couldn't be resumed in-place — `fetch_page(251, None)` under the new logic means "start over from the beginning," not "continue from page 251." Re-ran a full pass; idempotent upsert on `application_number` absorbed the 25,100 already-loaded rows harmlessly. This is a one-time migration cost from changing an extractor's pagination strategy after checkpoints already exist for it — a second such change would hit the same wrinkle.
- **Scaling story (10x/100x):** Keyset pagination has no ceiling regardless of dataset size (unlike skip/limit, which degrades or breaks entirely on large offsets in most APIs/DBs) — this is why it's the standard approach for paginating large result sets in general, not just an openFDA-specific fix.
- **Interview question this maps to:** "Why does skip/offset pagination break down at scale, and what do you replace it with?" / "Tell me about an API constraint you only discovered by running against the real thing."

## Decision: added `ops.extraction_log` (schema not specified in the spec) to implement the staging missingness policy's row-exclusion strategy
- **What:** Spec line 108 requires row-exclusion decisions in staging to be "logged to `ops.extraction_log`" but never defines that table's schema (unlike `raw.extraction_checkpoints`, which has an explicit `CREATE TABLE` block). Added `scripts/init_ops_schema.sql` (`ops.extraction_log`: `log_id`, `model_name`, `exclusion_reason`, `excluded_count`, `logged_at`), mounted it in `docker-compose.yml` alongside the raw-schema init script, and applied it manually to the already-running Postgres container (init scripts only run on first volume creation, so a fresh `docker compose up` wouldn't have picked it up otherwise). `stg_approvals.sql` writes to it via a `post_hook` that counts FDA applications with no `submissions` array (2,707 of 29,218) on every `dbt build`.
- **Why (vs. alternatives):** Could have used a dbt `store_failures` test instead of a hand-written post-hook, but that mechanism is designed for *test* failures (rows that violate an assertion), not an intentional, expected exclusion that's part of normal model logic — using it here would conflate "this is broken" with "this is a documented policy," which is exactly the silent-bias failure mode the spec is guarding against for TrialOutcome (Project 2).
- **Failure mode:** The log accumulates one row per model per `dbt build` run rather than upserting a single current count — appropriate for an audit trail (you can see the exclusion count trend over time as more data lands), but a naive `SELECT * FROM ops.extraction_log` reader who expects "current state" instead of "history" would need to filter to the latest `logged_at` per `model_name`.
- **Scaling story (10x/100x):** Holds unchanged as more staging models add their own exclusion post-hooks; at high `dbt build` frequency (e.g. hourly instead of daily) the log grows unbounded and would eventually want a retention policy, which doesn't exist yet.
- **Interview question this maps to:** "How do you make a data-quality decision auditable instead of silent?" / "A spec references infrastructure it never fully defines — what do you do?"

## Decision: real staging models (`stg_trials`, `stg_sponsors`, `stg_approvals`) live in `domains/pharma/dbt/models/staging/`, not `core/dbt/models/staging/_template`
- **What:** Spec Section 0's tree shows `core/dbt/models/staging/_template` as "staging model pattern, parameterized by domain config" — a single template, not a models folder. Read that as: the *pattern* (documented conventions: view materialization, missingness-policy discipline, source declarations) is core/reusable, but the actual staging SQL (which encodes pharma vocabulary — `nct_id`, `phase`, `sponsor_class`) is domain-specific, same as `dim_sponsor.sql` was already placed under `domains/pharma/dbt/models/marts/` before this session. Placed all three staging models next to it.
- **Why (vs. alternatives):** The alternative (treating `core/dbt/models/staging/` as where real staging models live, on the theory that "staging = generic ELT plumbing") would mean a second domain inherits pharma's exact column names — the opposite of what Section 0's core/domains split is for. Flagging this explicitly per this repo's own architecture-discipline rule, since the spec's tree diagram doesn't spell out a `domains/pharma/dbt/models/staging/` path the way it does for `marts/`.
- **Failure mode:** If a future staging model turns out to be genuinely domain-agnostic (e.g., a generic "flatten a JSONB array into rows" pattern with zero pharma column names), it should move to `core/dbt/models/staging/_template` instead — none of the three M2 models qualify, since all reference pharma-specific JSON paths.
- **Scaling story (10x/100x):** Validated the same way as the M0 core/domains split: a second domain would add its own `domains/<name>/dbt/models/staging/` folder and reuse only `dbt/dbt_project.yml`'s dynamic model-path resolution (`../domains/{{ env_var('ACTIVE_DOMAIN') }}/dbt/models`) and `core/dbt/macros/generate_surrogate_key.sql` — zero edits to pharma's staging models.
- **Interview question this maps to:** "How do you decide what's 'core' vs 'domain' when a spec's file tree doesn't spell out every path?"

## Decision: staging missingness policy applied concretely (real data, not guessed)
- **What:** Queried the live `raw.ct_studies`/`raw.fda_applications` data (594,309 / 29,218 rows) before writing any staging SQL, rather than assuming CT.gov/openFDA's documented shape matched reality. Findings that shaped the models: (1) `start_date`/`completion_date` arrive at year-month-only precision for ~37-39% of trials (e.g. `"2020-07"`) — day defaulted to `01` (named imputation), true absence (~1-3%) passed through as NULL; (2) `phase` is legitimately absent for ~24% of trials (observational studies have no phase by design) — NULL passthrough, not imputed; (3) the same `sponsor_name` occasionally reports a different `sponsor_class` across trials — `stg_sponsors` resolves via mode (most frequent class), ties broken alphabetically; (4) FDA `submission_number` is only unique within `submission_type` per application (ORIG and SUPPL both start numbering at 1) — `stg_approvals`' natural/surrogate key is the 3-part `(application_number, submission_type, submission_number)`, not 2-part as first assumed.
- **Why (vs. alternatives):** Assuming field shapes from the API docs or the spec's field_mappings.yaml alone would have produced a `stg_approvals` model with a silently-wrong (non-unique) key, or a date-cast that throws on every year-month-only row — both of which would have passed a superficial review and failed on real data.
- **Failure mode:** If CT.gov changes date precision conventions or openFDA changes submission numbering in a future extraction, these hardcoded assumptions (length-7 vs length-10 date strings, 3-part approval key) would need re-verification — they're grounded in the current data, not guaranteed by any documented API contract.
- **Scaling story (10x/100x):** Holds unchanged at 10x/100x row volume (these are per-row parsing rules, not volume-dependent); would need revisiting only if the *source schema* changes, not if the *row count* changes.
- **Interview question this maps to:** "Tell me about a time the real data didn't match your assumptions from the docs." / "How do you design a natural key when the obvious one turns out not to be unique?"

## Decision: custom `generate_schema_name` macro to keep staging/marts schemas separate
- **What:** Added `dbt/macros/get_custom_schema.sql`, overriding dbt's default `generate_schema_name` macro so a model's `+schema:` config (`staging` or `marts`) is used as-is, and set `+schema: staging` / `+schema: marts` explicitly per folder in `dbt_project.yml`.
- **Why (vs. alternatives):** `profiles.yml`'s target schema is `staging` (the dev default), and dbt's *default* `generate_schema_name` macro concatenates `<target_schema>_<custom_schema>` whenever a custom schema is set — so without this override, marts configured with `+schema: marts` would have silently landed in `staging_marts`, not `marts`. Verified live: before the fix, an earlier `dim_sponsor` build had in fact landed in `staging.dim_sponsor` (dropped once the fix was confirmed working).
- **Failure mode:** If a future model sets a schema this macro doesn't expect (e.g. relying on dbt's multi-schema-per-target convention for a true multi-tenant setup), this override would silently ignore that convention rather than erroring — the override is a blunt "use exactly what's configured," not a smart merge.
- **Scaling story (10x/100x):** Holds unchanged regardless of row volume or model count; would need revisiting only if the project ever needed per-environment schema prefixing (e.g. `dev_shubham_marts` for multiple developers sharing one database), which this override currently does not support.
- **Interview question this maps to:** "A build worked in dev but tables ended up in the wrong schema — how do you debug that?" / "What does dbt's default schema-naming behavior actually do, and why do teams almost always override it?"

## Decision: dropped `fct_trials.condition_key` FK from the spec; conditions/interventions reachable only via bridge tables
- **What:** The spec's mart schema listed both a single `condition_key FK` column directly on `fct_trials` *and* a `bridge_trial_condition` many-to-many bridge table — an internally inconsistent design. Built only the bridge tables (`bridge_trial_condition`, `bridge_trial_intervention`), with no direct condition/intervention FK on the fact table.
- **Why (vs. alternatives):** Checked real data before deciding: only ~63% of trials report exactly one condition (rest report 2-10+), and only ~47% report exactly one intervention — a single FK column on the fact grain cannot represent this without arbitrarily picking one condition/intervention per trial and silently discarding the rest. The bridge-table pattern is the standard, correct star-schema solution for a genuine M:N relationship.
- **Failure mode:** Any downstream query or dashboard that assumes "one condition per trial" (e.g. a naive `fct_trials JOIN dim_condition`) will need to go through the bridge and handle fan-out (a trial with 3 conditions produces 3 joined rows) — this is a real modeling consideration for M4/M5's metric models and Tableau views, not just a build-time detail.
- **Scaling story (10x/100x):** Bridge tables scale linearly with (trial × condition) pairs regardless of data volume; no redesign needed at 10x/100x row counts.
- **Interview question this maps to:** "A spec asked for both a FK and a bridge table for the same relationship — how did you resolve the conflict?" / "How do you model a many-to-many relationship in a star schema?"

## Decision: `fct_approvals` kept at the 3-part submission-event grain, not `application_number` alone
- **What:** Spec listed `fct_approvals`' PK as `application_number` alone. Built it at the same grain as `stg_approvals` (`approval_key` PK, one row per `(application_number, submission_type, submission_number)`), carrying `submission_status`/`approval_date`/`review_priority` straight through.
- **Why (vs. alternatives):** M2 already established (real data) that one application has multiple submission events (ORIG + SUPPLs) that are each independently a regulatory action — collapsing to one row per `application_number` (e.g. keeping only the first/latest submission) would silently discard supplement-level approvals (label expansions, new indications), which is real information loss, not just a grain simplification.
- **Failure mode:** Any consumer expecting "one row = one application" (matching the spec's literal PK) will get more rows than applications and must aggregate explicitly (e.g. `count(distinct application_number)` vs `count(*)`) — documented in schema.yml so this isn't a silent surprise.
- **Scaling story (10x/100x):** Unchanged at higher volume; this is a grain decision, not a performance one.
- **Interview question this maps to:** "When does 'match the spec exactly' conflict with 'don't lose real information,' and how do you decide?"

## Decision: `dim_condition.mesh_term` and `.therapeutic_area` are always NULL for M3
- **What:** CT.gov's derived MeSH terms (`derivedSection.conditionBrowseModule.meshes`) live at the study level, not paired to individual free-text conditions (`protocolSection.conditionsModule.conditions`) — the two arrays commonly differ in length and have no positional or ID-based correspondence. `therapeutic_area` has no CT.gov source field at all. Asked the user explicitly rather than guessing: chose NULL passthrough for both over a best-effort single-condition/single-mesh pairing heuristic, and over building a real MeSH tree-number crosswalk (which would need external reference data — genuine scope add, not implementation-forced).
- **Why (vs. alternatives):** A best-effort pairing (match when a trial has exactly 1 condition and exactly 1 mesh term) was considered but still not guaranteed semantically correct (the mesh term is NLM's own indexing of the whole study, not proven to correspond to that one free-text string) and would have implied more confidence in the mapping than the data supports. NULL passthrough matches the same missingness-policy discipline already established in M2 (document the gap, don't silently guess or drop).
- **Failure mode:** If M4/M5 dashboards want a therapeutic-area cut, that dimension simply won't be available from `dim_condition` — this needs to be visible in the KPI framework doc (M6) as a known limitation, not discovered late as a dashboard bug.
- **Scaling story (10x/100x):** Unchanged by volume. Only resolved by adding a real MeSH tree-number crosswalk as a scoped, confirmed addition later — not something that "gets better" with more rows.
- **Interview question this maps to:** "A spec named a column your source data can't actually populate — what do you do?" / "How do you decide when 'leave it NULL and document why' is the right call vs. building the real derivation?"

## Decision: bumped Postgres container `shm_size` to 256mb
- **What:** `docker-compose.yml`'s `postgres` service now sets `shm_size: '256mb'` (Docker's default is 64MB).
- **Why (vs. alternatives):** Discovered live during M3's `dbt build`: with 4 concurrent dbt threads (`profiles.yml`'s `threads: 4`) each potentially triggering Postgres parallel workers on hash joins over the new ~1M-row bridge tables, `/dev/shm` filled up and a *different* single test failed on each of two consecutive full `dbt build` runs with `could not resize shared memory segment ... No space left on device`. Confirmed it wasn't a data/logic bug by re-running the failing test alone (`--threads 1`), which passed instantly — isolated the cause to concurrent shared-memory contention, not query correctness. Could have instead dropped `threads` to 1 in `profiles.yml`, which would "fix" it too, but that trades away real parallelism for the rest of the build (models still benefit from concurrency; only the shared-memory ceiling was the problem) — bumping `shm_size` fixes the actual constraint instead of working around it.
- **Failure mode:** Requires recreating the container (`docker compose up -d --force-recreate postgres`) since `shm_size` is a container-creation-time setting, not hot-patchable on a running container — data is safe (the `pgdata` named volume persists across recreation, verified by re-checking row counts post-recreate), but anyone who forgets this and just edits the YAML without recreating won't see the fix take effect and may wrongly conclude it didn't work.
- **Scaling story (10x/100x):** At 10x the row count (or more concurrent dbt threads / CI runners), 256MB may need to grow further — this is a "when tests start flaking with the same shared-memory error again" signal, not a one-time-fixed-forever number.
- **Interview question this maps to:** "You hit a flaky test in CI — how do you tell a real bug from an infra/resource problem?" / "What's `/dev/shm` for in Postgres, and when does its default size become a real constraint?"

## Decision: `metric_phase_transition` multi-condition tie-break rule: first-listed condition, not rarest-condition
- **What:** For trials with >1 condition in `bridge_trial_condition`, `metric_phase_transition` selects a single representative condition via `ROW_NUMBER() OVER (PARTITION BY nct_id ORDER BY condition_key ASC) = 1`. A `multi_condition_flag` column (TRUE where the trial had >1 condition) is carried on every row so this tie-break is auditable, not silent.
- **Why (vs. alternatives):** Rarest-condition (pick the condition_name with the lowest overall trial count as "most specific") was considered, since it's arguably a better single label for a multi-condition trial. Rejected because it requires a point-in-time rarity count — the rarity of a condition changes as more trials get ingested over time, so computing it naively over the full historical table would leak future information into any point-in-time feature (a real concern flagged for TrialOutcome's condition-rarity feature, which explicitly joins through this same bridge table — see M3's downstream flag in `04_PHARMAPULSE_SPEC.md`). First-listed-by-key is deterministic, stable, and adds no temporal-leakage risk, at the cost of being an arbitrary (not semantically meaningful) tie-break.
- **Failure mode:** For any trial with >1 condition, the tie-break silently drops all but one condition from this metric's condition-level grouping — `multi_condition_flag` is the guard against this becoming invisible, but a consumer who ignores that flag and reads `condition_name` counts as ground truth will undercount trials for a condition that's usually listed second or later for multi-condition trials.
- **Scaling story (10x/100x):** Holds unchanged at any data volume — the tie-break is per-trial, not a function of table size. Only revisited if a real crosswalk/canonicalization layer for conditions is built, at which point the tie-break question changes shape entirely (deduping semantically-equivalent condition names, not just picking one of several genuinely-different reported conditions).
- **Interview question this maps to:** "How do you resolve a many-to-one tie-break when the 'obviously correct' choice would leak future information?" / "Walk me through a modeling decision you made specifically to protect a downstream ML feature."

## Decision: `metric_phase_transition` groups by `condition_name`, not `therapeutic_area`
- **What:** `therapeutic_area` is NULL for all rows (no CT.gov source, no MeSH crosswalk as of M3). Grouping by it produces one NULL bucket. Substituting `condition_name` as interim proxy.
- **Why (vs. alternatives):** keeping `therapeutic_area` produces an unqueryable metric (one NULL group, no sliceability). `condition_name` is real, granular, and available now. `therapeutic_area` column retained as NULL passthrough so the model interface doesn't change when the crosswalk lands.
- **Failure mode:** `condition_name` is too granular for dashboards — hundreds of buckets. Mitigation: dashboard and notebook filter to top-N conditions by trial volume.
- **Scaling story (10x/100x):** MeSH crosswalk (future milestone or appendix) populates `therapeutic_area`; metric model and dashboard swap GROUP BY column, no structural change needed.
- **Interview question this maps to:** "How did you handle missing data in your pipeline?" — concrete, documented NULL-handling decision with a clear upgrade path.

## Decision: `metric_phase_transition` Approval stage uses best-effort `sponsor_name` join
- **What:** no entity resolution exists between CT.gov lead-sponsor names and FDA applicant names. Used `UPPER(TRIM())` exact match as best available option.
- **Why (vs. dropping Approval stage):** a two-stage funnel (Phase 2 → Phase 3) is not a funnel — it's a trial-status breakdown. The Approval stage is the metric's entire value for the M5 dashboard and M6 exec memo. Low match rate is documented and surfaced via `matched_to_fda` flag, not hidden.
- **Failure mode:** large sponsors match well, small/regional sponsors do not — approval rate metric is biased toward large pharma. Caveat in `_schema.yml` and model comment block.
- **Scaling story:** replace string join with an entity resolution layer (fuzzy match + manual golden set for top-50 sponsors) in a future milestone — `matched_to_fda` flag makes the upgrade path testable without restructuring the model.
- **Interview question this maps to:** "How did you handle data integration across sources with no shared key?" — this is the concrete answer, with a documented upgrade path.

## Decision: `metric_phase_transition`'s rate columns are relative-volume ratios, not true transition probabilities — for all three stages, not just Approval
- **What:** Discovered live while writing the M4 notebook (querying real output, not just reasoning about the design): `phase2_to_phase3_rate` and `phase2_to_approval_rate` can both exceed 100%, same as the already-documented Approval-stage caveat — 14 of 109 conditions with ≥100 Phase-2 trials show `phase2_to_phase3_rate` above 100% (Diabetes at 203%). Extended the model's top-of-file caveat comment and `_schema.yml` column descriptions to cover all three rate columns, not just the Approval one originally scoped.
- **Why (vs. alternatives):** The root cause is structural, not a bug to fix: CT.gov has no field linking a trial to its own phase-successor trial, so `is_phase2`/`is_phase3` counts per condition are independent cross-sectional volumes (however many Phase-2 and Phase-3 trials happen to be registered under that condition_name), not a cohort followed from Phase 2 into Phase 3. There's no clean fix available at this milestone (would require the same kind of entity-resolution/trial-lineage work already flagged as out-of-scope for the Approval stage) — the correct response is documenting the gap precisely, matching this project's established NULL-passthrough / caveat-don't-hide discipline, not silently rounding or clipping the numbers to look plausible.
- **Failure mode:** Anyone reading `phase2_to_phase3_rate` as a literal "P(a Phase-2 trial for this condition becomes a Phase-3 trial)" — the natural reading of the column name and the milestone's own spec language ("P(Phase 2 → Phase 3 → Approval)") — will draw a false conclusion for any condition where the ratio exceeds 100%, and will still be misled at conditions under 100% since even those aren't a true followed-cohort rate, just a ratio that happens to land in a plausible-looking range. The M4 notebook's Insight 1 makes this caveat itself the finding (14/109 over 100%) specifically so it can't be missed downstream in M5/M6.
- **Scaling story (10x/100x):** Unchanged by data volume — this is a data-model gap (no phase-lineage field), not a scale problem. Only resolved by building real trial-lineage linkage (e.g., matching on drug/intervention + sponsor + condition across phase-labeled trials, itself an uncertain heuristic) as a scoped future addition.
- **Interview question this maps to:** "Tell me about a metric whose name promised something the underlying data couldn't support." / "How do you catch a modeling assumption that only breaks on real data, not in the design review?"

## Decision: `metric_sponsor_cohorts` treats a NULL `completion_date` as active only in the trial's start year, not open-ended
- **What:** When expanding each trial into the calendar years it was "active" for cohort survivorship, a trial with a NULL `completion_date` contributes only its `start_date` year, not a range extending to the present.
- **Why (vs. alternatives):** The alternative — treating an open `completion_date` as "still active through the current year" — would inflate survivorship for any recent cohort with a lot of currently-enrolling trials, since every such trial would count as "active" every year up to today by construction, regardless of whether it's actually still running or just missing a recorded end date. Treating it as active only in its start year is the conservative choice: it undercounts true activity duration for genuinely-ongoing trials, but doesn't fabricate an activity signal the data doesn't support.
- **Failure mode:** For a sponsor whose only trials are recent and still enrolling (no `completion_date` yet), this model will show them as active only in their trial(s)' start year and then "dropping off" in the survivorship curve the very next year — which looks identical to a sponsor who genuinely stopped running trials. The model cannot currently distinguish "stopped" from "still running, no recorded end date yet," and undercounts survivorship for the most recent cohorts as a result.
- **Scaling story (10x/100x):** Unchanged by data volume. Would be resolved by treating `overall_status` (e.g. `RECRUITING`, `ACTIVE_NOT_RECRUITING`) as a signal that a NULL-completion trial is still genuinely active as of the extraction date, rather than ignoring status and just using date fields — a real refinement, not currently built.
- **Interview question this maps to:** "How do you handle right-censored data in a cohort/survival analysis when you don't have a formal survival-analysis library available?" / "What's the difference between 'no end date recorded' and 'still ongoing,' and why does conflating them bias your metric?"

## Decision: Streamlit as primary live demo artifact; Tableau built separately from CSV extracts
- **What:** Streamlit (Claude Code-built, 8 dashboards, Dockerized) serves as the live interactive demo. Tableau Public (built manually) serves as the BA/DA resume credential. Both source from the same marts/metrics layer.
- **Why (vs. Streamlit only):** Tableau Public URL is a specific signal BA/DA hiring managers look for — it cannot be substituted by Streamlit for that audience. Streamlit is the engineering artifact; Tableau is the credential.
- **Why (vs. Tableau only):** Tableau cannot be built by Claude Code; Streamlit gives a live demo URL and shows Python/Plotly skills for DS/AI-Eng roles.
- **Failure mode:** Tableau Public free tier throttles or changes terms — Streamlit remains the functional demo; the credential signal is lost but the artifact is not.
- **Scaling story:** replace Streamlit with a proper BI layer (Metabase, Superset) if this were a real team deployment; Tableau replaced by Tableau Server or Looker behind SSO.
- **Interview question this maps to:** "How did you think about your audience when deciding how to present your analysis?" — two artifacts, two audiences, same data.

## Decision: `why_stopped` added to `stg_trials`/`fct_trials` in M5, extending a previously-"done" M3 deliverable
- **What:** `why_stopped` (CT.gov `statusModule.whyStopped`, free text, populated for ~7.8% of trials spanning TERMINATED/WITHDRAWN/SUSPENDED) was in the raw payload since M2 but never extracted. Added as a straight passthrough column on both models for the M5 "why trials fail" dashboard.
- **Why (vs. alternatives):** The Streamlit read-only role is scoped to `marts`+`metrics` only (no `raw`), so the alternative — querying `raw.ct_studies` directly from the dashboard — isn't just worse practice, it's flatly impossible under the access-control the M5 spec itself required. Dropping the reason-level breakdown from Dashboard 6 (keeping only termination *rate* by phase/sponsor_class) was the real alternative; rejected because it guts the dashboard's own stated framing ("why trials fail") down to "how often," not why.
- **Failure mode:** `why_stopped` is free text with zero normalization (see the next decision) — real, but a small share (~7.8%) of trials even carry a reason at all, so the breakdown chart is representative of *reported* reasons only, not a full accounting of every termination's cause.
- **Scaling story (10x/100x):** Unchanged by row volume. Would need revisiting only if reason-level normalization (merging "Low enrollment" / "Insufficient accrual" / etc. into canonical categories) became a real requirement — out of scope for M5, a genuine future NLP/entity-resolution task.
- **Interview question this maps to:** "A downstream feature needed a field that was never extracted upstream — how do you decide where that fix belongs?" / "How does a read-only access-control boundary you set yourself end up shaping a data-modeling decision two milestones later?"

## Decision: `metric_duration_trends_by_phase` is a new model, not an in-place grain change to `metric_duration_trends`
- **What:** Dashboard 4 wanted duration trends "by phase," but M4's `metric_duration_trends` is grain = `start_year` only. Added a second model at grain `(start_year, phase)` rather than adding `phase` to the existing model's `GROUP BY`.
- **Why (vs. alternatives):** Changing the existing model's grain in place would have shifted the overall YoY median numbers already quoted verbatim in the M4 notebook and in this file's own M4 decision entries (phase-NULL trials, ~24% of rows, would fragment out of an all-trials aggregate into their own group) — silently invalidating a already-shipped, already-documented milestone's numbers to serve a later one. A new model costs one extra file and keeps both deliverables independently correct.
- **Failure mode:** Two models now answer "duration trends" at different grains — a future consumer who doesn't read both models' `_schema.yml` descriptions could pull the wrong one and get numbers that don't reconcile with the one they expected (e.g. summing `metric_duration_trends_by_phase.trial_count` across phases for a year won't exactly equal `metric_duration_trends.trial_count` for trials reporting >1 phase in one string, since `metric_duration_trends` doesn't split combined-phase trials either).
- **Scaling story (10x/100x):** Unchanged by volume. If a third cut (e.g. by sponsor_class) were needed later, the same pattern applies — a new model, not a third dimension bolted onto an existing one whose consumers already depend on its current grain.
- **Interview question this maps to:** "When do you version/fork a data model instead of just adding a column to it?" / "How do you avoid a metrics-layer change silently invalidating a report someone already shipped?"

## Decision: Approval Landscape dashboard breaks down by top FDA applicant, not `sponsor_class` — the spec's literal ask doesn't exist in FDA data
- **What:** M5's spec asked Dashboard 1 to show "approval counts over time by sponsor_class." `fct_approvals.sponsor_name` is the FDA applicant (a namespace `_schema.yml` already documents as distinct from CT.gov's classified `sponsor_class`, established in M3) — there is no sponsor_class equivalent for FDA data. Built the by-category cut as top-10 individual applicants instead, with an in-page warning explaining the substitution.
- **Why (vs. alternatives):** Joining FDA `sponsor_name` to CT.gov's `dim_sponsor.sponsor_class` on name-string match was considered and rejected for the same reason the Phase Funnel's Approval stage already carries a heavy caveat for exactly this join (M4 decision: different namespaces, no entity resolution) — reusing a known-noisy join to *invent* a sponsor_class for FDA data would launder Dashboard 2's documented caveat into a second dashboard's confident-looking bar chart, which is worse than just not having the cut.
- **Failure mode:** Top-10-applicant is a reasonable substitute for "who dominates approval volume" but doesn't answer the original question ("does approval volume skew Industry vs. NIH vs. Federal") at all — a viewer expecting a sponsor_class legend will need the in-page warning to understand why they're seeing applicant names instead.
- **Scaling story (10x/100x):** Unchanged by volume. Only resolved by the same entity-resolution work already flagged as a future milestone for the Phase Funnel's Approval stage — if that gets built, both dashboards benefit from the same fix.
- **Interview question this maps to:** "A dashboard spec assumed a field existed that turned out to belong to a different data source's namespace — what do you do?"

## Decision: read-only role created via a one-time manual script (`make create-readonly-role`), not a docker-entrypoint-initdb.d init script
- **What:** `streamlit/scripts/create_readonly_role.sql` is applied manually (via `envsubst` + `psql`), not mounted alongside `init_raw_schema.sql`/`init_ops_schema.sql` in `docker-compose.yml`.
- **Why (vs. alternatives):** `docker-entrypoint-initdb.d` scripts only run on first volume creation (already learned the hard way in M2 — the `ops.extraction_log` init script needed the same manual-apply treatment since the `pgdata` volume already existed). Mounting this script wouldn't do anything on this machine without a volume recreation, which would destroy 594K+ rows of already-extracted data to save one manual command — a bad trade for a role-creation script that needs to run exactly once anyway.
- **Failure mode:** Anyone who clones this repo fresh and runs `docker compose up` will get a Postgres container where `pharmapulse_readonly` does *not* exist yet — `make create-readonly-role` is a required manual step, not automatic, and the Streamlit container will fail to authenticate until it's run. Documented in the README's Dashboards section.
- **Scaling story (10x/100x):** `ALTER DEFAULT PRIVILEGES ... GRANT SELECT ON TABLES` (added beyond the spec's literal SQL) means future `dbt build` runs that create new mart/metric tables don't require re-running this script — without it, every new model would be invisible to the readonly role until manually re-granted, a real operational trap at any team size.
- **Interview question this maps to:** "How do you keep a read-only analytics role in sync with a schema that gets new tables added by every CI run?" — `ALTER DEFAULT PRIVILEGES` is the concrete answer, and the reason it's not in the literal spec text is worth naming.

## Decision: verified the Streamlit app by executing every page's script (`streamlit.testing.v1.AppTest`), not by checking HTTP status codes
- **What:** Curling each dashboard's URL against a locally-running instance returned 200 for all 8 pages — but Streamlit is a client-routed single-page app, so a bare HTTP GET doesn't prove the page's Python actually ran without error. Used `AppTest.from_file(...).run()` per page instead, which executes the real script server-side and surfaces exceptions.
- **Why (vs. trusting curl):** `AppTest` caught a real bug curl couldn't have: the Sponsor League Table's pandas Styler-based row highlighting (`.style.apply(...)`) hit Streamlit's 262,144-cell Styler render ceiling at the table's actual size (51,173 sponsors × 6 columns = 307,038 cells) — `03_sponsor_league_table.py` would have crashed for every real user despite every `curl` check passing. Fixed by replacing the Styler-based highlight with a plain indicator column (🏆), which also scales far better at this row count than per-row style computation would have.
- **Failure mode:** `AppTest` still doesn't render in a real browser — a genuine visual/layout regression (e.g. a chart legend overlapping its plot area) wouldn't be caught this way; only Python-level exceptions and element values are inspectable. No headless browser was available in this environment to close that last gap.
- **Scaling story (10x/100x):** At 10x the sponsor count (500K+), the same Styler ceiling would resurface in any future page that adds row-level conditional styling to a large `st.dataframe` — the fix pattern (indicator column, not Styler) is the general answer, not just a one-off patch for this table.
- **Interview question this maps to:** "Tell me about a bug you only found by actually running the code, not by reading it." / "How do you verify a Streamlit app's pages actually work, beyond 'the server started'?"

## Decision: `dbt docs generate` CI workflow runs against an empty Postgres service container — no extraction, no `dbt run`/`build`
- **What:** `.github/workflows/dbt_docs.yml` spins up a bare `postgres:15` service with no data (no `raw.ct_studies`/`raw.fda_applications`, no init scripts) and runs `dbt docs generate` directly against it, per the milestone's literal 5-step spec.
- **Why (vs. running the full pipeline in CI):** The DAG/lineage view GitHub Pages is meant to publish is driven by `manifest.json`, which compiles from the project's SQL and macros — it does not require the underlying tables to actually exist. Running the real ~594K-row CT.gov/openFDA extraction in a CI job on every push to `main` would be slow, rate-limited against live external APIs, and inappropriate for what is fundamentally a docs-publishing job, not a data job.
- **Failure mode:** `catalog.json` (the per-model column-type detail behind the "Columns" tab in the dbt docs UI) will be sparse or empty for every model, since there are no real relations for dbt to introspect via `information_schema`. The lineage graph itself is unaffected — this only degrades the column-detail drill-down, not the DAG.
- **Scaling story (10x/100x):** Unaffected by data volume, by construction — this workflow never touches real data. If column-level catalog detail in the published docs became a real requirement, the fix would be seeding a small fixture dataset into the CI Postgres (not running the real extraction), which is a scoped future addition, not implied by anything built here.
- **Interview question this maps to:** "How do you publish documentation that depends on a database without running your full pipeline in CI?" / "What's the difference between what `manifest.json` and `catalog.json` each need to exist?"

## Decision: dbt CI workflow runs against empty schema init only — no seed data
- **What:** `.github/workflows/dbt_ci.yml` runs `dbt build` against a fresh postgres
  service container with only the raw/ops schema DDL applied (init SQL scripts),
  no actual extracted data.
- **Why (vs. seeding fixture data):** dbt build in CI is a compilation and test
  check, not a data correctness check — the 107 tests passing locally against
  real data is the data-quality gate; CI's job is to catch model SQL syntax
  errors and schema drift on PR. Seeding 594K+ real rows in CI would be slow,
  rate-limited (re-extracting from live APIs), and unnecessary for what CI is
  actually validating.
- **Failure mode:** a dbt test that relies on referential integrity between real
  data rows (e.g. a relationship test between `fct_trials` and `dim_sponsor`) will
  vacuously pass in CI because both tables are empty — CI catches SQL errors
  and schema issues, not data-level assertion failures. The real data-quality
  gate is the local `dbt build` before pushing.
- **Scaling story:** if data-level tests in CI became a real requirement, the fix
  is a small fixture dataset (e.g. 1000 trials, 50 sponsors, 20 approvals)
  committed to `tests/fixtures/` and loaded via `psql` before `dbt build` — not
  re-running the full extraction.
- **Interview question this maps to:** "What does your CI pipeline actually test vs. what does
  it not test, and why?" — honest answer: SQL correctness and schema drift,
  not data correctness at row level.

## Decision: Airflow metadata DB uses a separate database on the same Postgres service
- **What:** Airflow's metadata (`dag_runs`, `task_instances`, etc.) lives in a
  new `airflow` database on the *same* `pharmapulse_postgres` service/container
  that already hosts the PharmaPulse data (`raw`/`staging`/`marts`/`metrics`
  schemas) — not a second `airflow-postgres` service. `airflow/init_airflow_db.py`
  creates it idempotently (`CREATE DATABASE IF NOT EXISTS` isn't real Postgres
  syntax, so the script checks `pg_database` first, then creates), run by the
  `airflow-init` one-shot service before `airflow db init`. Not a
  `docker-entrypoint-initdb.d` script — those only run on first volume
  creation, and this repo's `pgdata` volume already existed before Airflow was
  added (the exact same gotcha already hit twice: `ops.extraction_log` in M2,
  the readonly role in M5).
- **Why (vs. a second `airflow-postgres` service):** A second full Postgres
  container is the more architecturally "correct" isolation (separate
  failure domain, separate resource limits, separate backup schedule) and is
  what a real team deployment should do. For a single-node portfolio
  deployment, though, it's a second container to run, heal-check, and keep
  alive for marginal benefit — logical-database separation on the same
  instance already gets the two things that actually matter here: Airflow's
  metadata schema can't collide with `raw`/`staging`/`marts`/`metrics` table
  names, and `dbt build`/`dbt test` (which run against the PharmaPulse data
  DB, per `airflow/dbt_profiles/profiles.yml`) never touch Airflow's own
  bookkeeping tables or vice versa.
- **Failure mode:** Both databases now share one Postgres process's resource
  ceiling (`shm_size`, `max_connections`, disk I/O) — a runaway Airflow
  metadata query or a heavy concurrent `dbt build` could contend with the
  other's performance in a way two separate containers wouldn't. Also: a
  `docker compose down -v` (dropping the `pgdata` volume) now takes out both
  the data warehouse *and* Airflow's DAG run history in one command, where a
  separate service would let you reset one without the other.
- **Scaling story (10x/100x):** Logical separation on one instance is fine at
  portfolio/single-developer scale. At real team scale, Airflow metadata
  should move to its own managed instance (RDS/Cloud SQL) entirely separate
  from the data warehouse — exactly the direction a second `airflow-postgres`
  service here would have previewed, just not necessary to build now.
- **Interview question this maps to:** "Why does Airflow need its own
  database, and what happens if you share it with your data warehouse?"

## Decision: separate `airflow/dbt_profiles/profiles.yml`, not the local dev `dbt/profiles.yml`
- **What:** Airflow's `dbt_build`/`dbt_test` `BashOperator` tasks point at
  `airflow/dbt_profiles/profiles.yml` via `--profiles-dir`, a different file
  from the one used for local `dbt build` (`dbt/profiles.yml`). Both define
  the same `pharmapulse` profile but different `target` names (`airflow` vs
  `dev`) and, critically, a different `port` — `5432` (the internal Docker
  network port, reachable as `postgres:5432` from inside any container on
  the compose network) vs `5433` (the host-side remap `docker-compose.yml`
  already uses so this dev machine's pre-existing native Postgres on 5432
  doesn't collide — see the earlier "remapped local Postgres container to
  host port 5433" decision).
- **Why (vs. one shared profiles.yml with env-var-driven port):** `dbt/profiles.yml`
  already reads `POSTGRES_PORT` from the environment, and locally that's
  `5433`. Reusing the exact same file inside the Airflow containers would
  mean either overriding `POSTGRES_PORT=5432` for Airflow specifically
  (fragile — one shared env var name meaning two different things depending
  on which process reads it) or leaving it at `5433`, which doesn't exist
  inside the Docker network at all (only the host-side port mapping is
  `5433`; containers on the same compose network always reach Postgres on
  its real port, `5432`). A second, explicit profiles file removes the
  ambiguity entirely instead of relying on a context-dependent env var.
- **Failure mode:** Two `profiles.yml` files for one project is a real
  divergence risk — a schema/materialization change made in one won't
  propagate to the other. Mitigated by keeping `airflow/dbt_profiles/profiles.yml`
  minimal (connection info only; `dbt_project.yml`'s model config, which is
  what actually matters for correctness, is the single shared source both
  profiles point at).
- **Scaling story (10x/100x):** Unaffected by data volume. If more
  environments were added (staging, prod), the pattern generalizes — one
  `profiles.yml` per execution context, all pointing at the same
  `dbt_project.yml`, rather than one file trying to be environment-aware via
  conditionals.
- **Interview question this maps to:** "Your local dbt profile and your
  orchestrator's dbt profile disagree on a connection detail — how do you
  avoid that becoming a silent bug?"

## Decision: BashOperator for dbt_build/dbt_test, not Cosmos
- **What:** `airflow/dags/pharmapulse_daily.py`'s `dbt_build`/`dbt_test` tasks
  use `BashOperator` running dbt CLI commands directly.
- **Why (vs. Cosmos):** Cosmos (`astronomer-cosmos`) provides task-level DAG
  visualization per dbt model and better Airflow/dbt integration, but adds a
  non-trivial dependency and configuration surface for a portfolio project
  where the primary goal is proving orchestration competence, not dbt-Airflow
  integration depth. The spec explicitly calls `BashOperator` the requirement
  and Cosmos a stretch goal.
- **Failure mode:** `BashOperator` dbt failure gives a bash exit code and
  whatever dbt logs to stdout — no task-level breakdown of which dbt model
  failed within the Airflow UI. You'd need to read the dbt logs (mounted at
  `airflow/logs/`) to find the specific model.
- **Scaling story (10x/100x):** Cosmos is the right answer at team scale —
  per-model task visibility, smarter retries on individual failed models
  rather than the whole `dbt build`. Worth naming as the explicit upgrade
  path, not a silent gap.
- **Interview question this maps to:** "You used BashOperator for dbt — what
  would you change in production and why?"
