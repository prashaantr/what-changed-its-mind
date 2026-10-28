# What Changed Its Mind?

**Does more evidence make Jev's election forecasts better—or just more certain?**

A playful, open research essay on competitive 2026 US midterm races. Explore a map, add evidence, inspect the exact requests, and compare them with precomputed changes in candidate/source order. This is an experiment, not a calibrated election forecast.

The public dataset distinguishes fully audited races from an incomplete candidate pool. A target of 30 is a cap, not a claim that 30 races have been verified. Missing material is never replaced with generated transcripts, synthetic voters or fabricated probabilities.

**[Explore the site](https://prashaantr.github.io/what-changed-its-mind/)** · [Initial findings and limitations](docs/INITIAL_REPORT.md)

The first frozen release contains **three Senate races, 23 valid forecasts, one failed forecast and eight diagnostic records**. Candidate statements, finance and usable focus-group material are not present yet.

## Run the site

Requirements: Node 24+, Python 3.12+, [uv](https://docs.astral.sh/uv/). `pdftotext` (Poppler) is required only for collecting official PDF candidate rosters. Existing public records, stored results and the website work without it.

```sh
uv sync --locked --extra dev
npm --prefix apps/web ci
uv run research validate
uv run pytest -q
npm --prefix apps/web test
npm --prefix apps/web run dev
```

Open the local URL printed by Vite. The checked-in public export includes real sources and saved results; no API key is needed to explore or replay it. The separate fictional development fixture is never shipped as production data.

If macOS marks editable-install `.pth` files as hidden and `research` reports `ModuleNotFoundError`, prefix commands with `PYTHONPATH=pipeline` (for example, `PYTHONPATH=pipeline uv run research validate`). This uses the same local source and does not require changing system Python.

## Understand the experiment

| Arm | Evidence |
| --- | --- |
| A | Identities and available structured fundamentals |
| B | A + eligible polls |
| C | A + qualitative evidence |
| D | A + polls + the same qualitative evidence |

B and D have two extra order variants. Where available, D without focus groups is a separate exploratory comparison. The primary result is final-snapshot paired D-minus-B multiclass Brier score after certified outcomes. Ranges in the UI describe tested orderings, **not confidence intervals**. Diagnostic tests do not establish election calibration.

Read [the frozen protocol](docs/PROTOCOL.md), [data sources](docs/DATA_SOURCES.md), [architecture](docs/architecture.md), [public data contract](docs/WEB_CONTRACT.md), and [the runbook](docs/RUNBOOK.md).

## Collect or rerun

```sh
uv run research fetch
uv run research normalize
uv run research snapshot --snapshot-id my-initial
uv run research forecast --snapshot results/snapshots/my-initial.json
```

The last command previews the request count and byte budget; it does not spend API credits. To make a fresh live run, set `TYPESAFE_API_KEY` in ignored `.env.local`, run diagnostics first, then add `--live` with a new output filename. Never commit or paste credentials into an issue.

Raw acquisition archives and API caches stay local. Small reviewed records and exact public model requests/results live in Git. Approved large Parquet datasets alone use Git LFS; the website never requests LFS pointers.

## Contribute

Start with a missing-source issue, a collector fixture, an accessibility fix or an analysis of a saved response. See [CONTRIBUTING.md](CONTRIBUTING.md). No credentials are available to contributor PR checks. Original code is MIT; data and third-party assets follow [DATA_LICENSES.md](DATA_LICENSES.md) and their source-specific terms.

## Credits

Inspired by [Midterm Pulse's interactive explanation](https://www.us-elections.dev/en/how-it-works), [Daniel Rosehill's Jev election experiment](https://blog.danielrosehill.com/posts/knesset-2026-decision-model-forecast-aijs1i), and [Jev Does Not Play Dice](https://github.com/KantaHayashiAI/jev-does-not-play-dice). Palette inspired by [Matplotlib's FiveThirtyEight style](https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/mpl-data/stylelib/fivethirtyeight.mplstyle). This project is independent of those creators, FiveThirtyEight, TypeSafe and political campaigns.
