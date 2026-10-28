# Contributor and subagent execution guide

Read `AGENTS.md`, [PROTOCOL.md](PROTOCOL.md), [DATA_SOURCES.md](DATA_SOURCES.md) and [RUNBOOK.md](RUNBOOK.md) before editing. This is an exploratory evidence experiment. Never generate missing election facts, voter transcripts, probabilities, acquisition times or certified outcomes.

## Frozen boundary

`experiments/cohort.json` fixes **IA-SEN-2026, KS-SEN-2026 and TX-SEN-2026**. `results/snapshots/initial-v1.json` and its stored requests/results are immutable. Do not edit them, their hashes or their original candidate options. More races may be researched as unselected metadata; they cannot replace a frozen race or enter the registered final comparison. Do not change `protocol_version` on an existing object to disguise a changed experiment.

Adding races, changing selection rules, model version, prompts or resolution requires a separately named exploratory protocol and cohort. The coordinator writes its rationale, differences, actual prospective cutoff and analysis scope before new inference, then uses distinct filenames and output directories. Preserve the initial protocol, cohort and outputs. New collection after a cutoff cannot be relabeled as previously available. A later corrected source creates a documented new version, not a rewrite of initial evidence.

## Setup and offline acceptance

Run from the repository root with Python3.12+, Node24+, uv and npm installed:

```sh
uv sync --locked --extra dev
npm --prefix apps/web ci
uv run research validate
uv run pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
```

Collecting PDFs additionally requires Poppler's `pdftotext` on PATH. Reading the stored dataset and building the website do not. The build includes TypeScript checking. Run targeted tests while editing; run the acceptance commands before handing off. Do not run `fetch`, `snapshot` or a live command merely to verify a presentation change.

## Task allocation

When delegation is authorized, use one coordinator and at most three workers. Give each worker its exact files, acceptance criteria and forbidden files. Workers report verified findings, changed files, tests and unresolved gaps to the coordinator; they do not send messages to outside people, publish releases or change another worker's files.

| Owner | Owned files | Deliverable |
| --- | --- | --- |
| Data worker | `pipeline/jev_elections/collection.py`, `tests/test_collection.py`, working `data/registry/` and `data/processed/` records, `docs/DATA_SOURCES.md` | Original-source acquisition, deterministic parser, factual records and provenance; never frozen snapshots |
| Experiment worker | `pipeline/jev_elections/experiment.py`, `jev.py`, `evaluation.py` and their corresponding tests | Eligibility, exact requests, cache, diagnostics and scoring; no live API calls without an explicitly authorized run |
| Web worker | `apps/web/` | Accessible scrollable map, source inspection and stored-result replay against the public contract; do not hand-edit generated production `public/data/experiment.json` |
| Coordinator | `models.py`, `cli.py`, `export.py`, export/schema tests, `experiments/`, `results/`, CI, dependencies and all other documentation | Schema coordination, integration, freezes, public export, final acceptance and release |

All pipeline paths in this table are under `pipeline/jev_elections/`. Shared schema changes go through the coordinator before dependent workers edit. Commit or hand off only owned files. Do not race a dataset write against a snapshot/export: data must announce a final acquisition timestamp and then stop while the coordinator freezes it.

Suggested worker instructions:

1. **Data:** “Verify one missing original source, acquire its actual bytes, preserve rights and timestamps, implement a fail-closed parser and offline tests. Keep all frozen files unchanged. Stop with a coverage report.”
2. **Experiment:** “Check the proposed observation against the existing protocol and public schema. Test missingness, source rights and cutoff rejection offline. Preserve all previously valid outputs.”
3. **Web:** “Show the new supported evidence category using the public JSON contract; expose missingness and provenance. Do not invent live predictions. Test keyboard interaction and build.”
4. **Coordinator:** Review their evidence and tests; integrate only compatible changes. Recompute a new working export, never silently replace the initial experiment.

## Data worker checklist

1. Identify the actual primary publisher URL, office, election date and geography. A poll's candidate names do not verify a ballot roster. Use election authorities for nominees and declared write-ins. House geometry must match the election's district plan.
2. Copy [source.template.json](../data/registry/source.template.json) as a drafting reference. Replace every placeholder and set `synthetic=false` only for verified real records. Set storage, model use and redistribution separately; unknown rights remain unknown and excluded from model/public evidence. “Publicly readable” does not authorize publishing the full document.
3. Register a fixed URL in `source_records()` or `expansion_sources()` and add only its exact publisher host to the HTTPS allowlist. The collector does **not** glob registry JSON; adding a file alone neither registers nor downloads it. No credentialed fetching, paid keys, arbitrary-URL proxies, private IPs or unsafe redirects. Stop on access denial.
4. Work in a separate branch/checkout when adding sources. `uv run research fetch` mutates the working dataset and registry, even when collection output is customized. It must not run concurrently with a freeze. Default collection reuses an existing raw response only after checking its SHA-256 and preserves its original retrieval time. Explicit refresh is a new acquisition, never grounds to rewrite an initial snapshot.
5. Each acquisition needs source ID, original response SHA-256, actual UTC retrieval, final URL, media type, parser version and real HTTP status. Keep raw bytes under ignored `data/raw/`. Never call reader text original PDF bytes or invent HTTP200 for a failed request.
6. Parser output must fit `Dataset`/`Observation` in `models.py`: stable race/candidate/source/acquisition IDs, locator, factual value, content hash, publication precision, substantiated availability, actual retrieval, geography and scope. Keep day/month precision in `value`; leave exact publication time null when unknown. Availability must not precede evidence supporting that timestamp.
7. Poll values use `population="LV"` or the substantiated population, ISO `field_start`/`field_end`, `pollster`, and `shares` keyed by verified candidate ID. Preserve sponsor, third parties, undecided, rounding and missing sample counts. Do not convert vote shares to win probabilities. Historical results retain historical candidate names and a comparability note.
8. Qualitative facts must be independently worded, attributed and dated. A focus group needs original session/transcript anchors, format, recruitment and geographic scope plus rights. Statements are not independent voters; statewide groups cannot be assigned to House districts without evidence. Never synthesize missing transcripts.
9. Tests are offline. Parser-only fixtures must be visibly artificial; synthetic observations use fictional races and `synthetic=true`. Test failure when document shape changes, candidate joins fail, dates exceed cutoff, counts do not reconcile or URLs become unsafe. Do not put restricted source text or personal contacts in fixtures.
10. Run `uv run pytest tests/test_collection.py -q` and `uv run research validate`. Send the coordinator exact coverage, blocked sources, acquisition timestamps, rights limits and tested commands. Do not freeze or call Jev yourself.

## Inference, exports and CI

Preview existing-snapshot requests without spending credits:

```sh
uv run research forecast --snapshot results/snapshots/initial-v1.json
```

Live calls require an explicitly authorized run and local ignored credentials. Never add `--live` to tests, CI, contributor workflows or routine documentation checks. CI and fork PRs must have no model credentials, access to `.env.local`, raw archive upload or paid API calls. Do not print authorization headers or secrets in logs.

The coordinator uses the CLI exporter and [WEB_CONTRACT.md](WEB_CONTRACT.md) to create site data. The website receives approved JSON, not raw documents, credentials, private cache records or Git LFS pointers. Preserve exact stored requests/responses and link every displayed result back through snapshot, observation and acquisition. New evidence does not alter a stored model response.

Large approved factual tables follow [data/bulk/README.md](../data/bulk/README.md). The initial three-race dataset is small enough for normal reviewed JSON; LFS is not needed merely to make the project appear substantial.
