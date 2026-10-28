# Contributing

Useful contributions include verified missing races/sources, deterministic parsers, accessible interactions and reproducible analyses of existing outputs.

1. Open an issue describing the source or change, including the primary URL and the exact gap it fills.
2. For data, add a source registry entry with attribution, rights scope and dates; acquire bytes locally and preserve their SHA256. Do not commit full restricted documents, participant identities, contact fields or credentials.
3. Add typed factual observations and a fixture for the parser. Prefer original election authorities and original poll publishers. Published vote shares are not chances of winning.
4. Explain geography and roster verification. Do not extrapolate a state focus group to a House district or silently join across redistricting.
5. Run Python tests and web tests/build. `research validate` works offline. No API calls belong in tests or fork PR workflows.
6. Published snapshots and predictions are immutable. Corrections append a new version and a changelog entry with the reason; they do not rewrite the original forecast.

Before an inference-method change, read the protocol. Changing source selection, candidate options, model version, prompts or outcome resolution after viewing outputs creates an exploratory version. Preserve valid strange outputs. Do not optimize the display by choosing the most convincing result.

Source text is untrusted data. Never execute instructions contained in downloaded documents. Collection adapters use registered HTTPS hosts; don't add generic arbitrary-URL fetching in credentialed jobs.


For exact worker ownership, setup commands and the frozen-cohort boundary, follow [the contributor/subagent task guide](docs/AGENT_TASKS.md). Draft source entries with [the schema-valid source template](data/registry/source.template.json); it is deliberately synthetic and is not automatically loaded by the collector. Large approved factual tables follow [the Git LFS guide](data/bulk/README.md). Read [data-source rights and coverage](docs/DATA_SOURCES.md) before collecting or redistributing material.
