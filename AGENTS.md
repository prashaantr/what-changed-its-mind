# What Changed Its Mind?

Build the approved, public election-evidence experiment. Read docs/PROTOCOL.md before changing inference semantics.

- Never invent election data, model responses, source dates, author quotations or certified outcomes.
- Fixture observations use fictional races and `synthetic=true`; production export rejects them.
- Shared contracts live in pipeline/jev_elections/models.py. Coordinate schema changes with the owner.
- Keep credentials, raw downloads, private logs and working requests out of Git. Public exports are allowlisted.
- Keep model versions, candidate IDs, source hashes, timestamps and missingness through every stage.
- Publication status is independent of model confidence; do not claim calibrated election probabilities.
- Run offline Python tests and the web typecheck/build before release. Do not call paid APIs from CI.
- Worker ownership: data owns collection.py and source records; experiment owns experiment.py, jev.py, evaluation.py and their tests; web owns apps/web; coordinator owns shared models, CLI, export, documentation and CI.
