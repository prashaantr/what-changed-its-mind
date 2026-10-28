# Operator runbook

Use repository root as working directory. All commands have `--help`. The published initial release uses `results/diagnostics/initial.json`; pass that path to `--diagnostics` when reusing its diagnostic archive. The examples below show filenames for a fresh experiment. Do not recreate or overwrite the published initial records. Validate and build offline first; collection is a separate network step. Record protocol changes before running paid inference.

## Initial acquisition and inference

```sh
uv run research fetch
uv run research validate
uv run research normalize
uv run research snapshot --snapshot-id initial-v1
uv run research diagnostics --live --output results/diagnostics/initial-v1.json
uv run research forecast --snapshot results/snapshots/initial-v1.json
uv run research forecast --snapshot results/snapshots/initial-v1.json --live --diagnostics results/diagnostics/initial-v1.json --output results/forecasts/initial-v1.json
uv run research classify --snapshot results/snapshots/initial-v1.json --live --output results/classifications/initial-v1.json
uv run research export --snapshot results/snapshots/initial-v1.json --inferences results/forecasts/initial-v1.json --diagnostics results/diagnostics/initial-v1.json
```

Set `TYPESAFE_API_KEY` in ignored `.env.local` before the live commands. Commands refuse an existing result filename. No third-party LLM is used to manufacture summaries. Collection is incomplete when source parsers/access fail; inspect `data/registry/collection_report.json` before freezing. API errors are retained and never replaced with a fabricated forecast.

## Immutable cohort registration

The first nonempty `snapshot` command writes `experiments/cohort.json` with the ordered race IDs, original race records, protocol version, initial snapshot hash and a manifest checksum. Review and publish this receipt with the initial snapshot before inference. Every later snapshot automatically reads this manifest and preserves exactly those IDs; it never replaces a race because new coverage or ratings look better. The `--cohort` option selects an isolated experiment manifest when testing a separate, explicitly versioned study.

If a frozen race is absent from the current collection, its original identity is retained with roster/geography verification disabled. Its forecast slots are unavailable until its current record is independently verified; candidates are never guessed. A missing or changed cohort checksum stops the run. Existing snapshot filenames are refused.

An empty snapshot is explicitly collecting and does not register an empty cohort. Complete the source audit and create a new initial snapshot filename when eligible races become available. Do not delete or rewrite a registered cohort to add races after inference; that requires a separately disclosed protocol and experiment.

## Final snapshot

Collect and validate sources **before November2,2026 at23:00UTC**, then freeze the dataset at that exact cutoff:

```sh
uv run research snapshot --snapshot-id final-v1 --cutoff 2026-11-02T23:00:00Z
uv run research forecast --snapshot results/snapshots/final-v1.json --live --diagnostics results/diagnostics/initial-v1.json --output results/forecasts/final-v1.json
uv run research classify --snapshot results/snapshots/final-v1.json --live --output results/classifications/final-v1.json
uv run research export --snapshot results/snapshots/final-v1.json --inferences results/forecasts/final-v1.json --diagnostics results/diagnostics/initial-v1.json
```

The final command requires the existing initial cohort manifest. Freeze cannot happen before cutoff. Evidence acquired later is excluded even if its page claims an earlier publication date. Do not substitute an opportunistically changed cohort: reuse the originally registered IDs, and disclose source changes/missingness. If the operational deadline is missed, label the actual execution date; a post-outcome run is not prospective. No automatic schedule is created.

## Official outcomes

Add `Outcome` records with source IDs and acquisition timestamps to a new JSON file. Only `certified` outcomes are scored; projections remain pending. Include any required runoff. Then:

```sh
uv run research evaluate --snapshot results/snapshots/final-v1.json --inferences results/forecasts/final-v1.json --outcomes results/outcomes/certified-v1.json --output results/evaluation/final-v1.json
```

Export that evaluation alongside its matching snapshot and inferences. Never insert outcomes into the acquisition dataset used for forecasting.

## Deployment and replay

GitHub Actions tests on every PR/push; deployment is an explicit workflow dispatch or a push to the release branch. Public build uses checked-in approved exports and never receives model credentials. `npm --prefix apps/web run build` creates the static Pages artifact. The base path is relative, so both local preview and repository Pages URLs work.

Full stored requests and responses remain available for audit. Exact replay means reading those records; a fresh API call can differ despite the pinned model. The provider's32k/64k limits are not estimated using a nonexistent official tokenizer; the24k-byte budget is explicitly a conservative proxy.
