# Protocol 1.0.0 — What Changed Its Mind?

This is an exploratory, prospective experiment, not a validated election forecast. Changes after inspecting model outputs require a new protocol version and explicit exploratory status. The design extends Midterm Pulse and Daniel Rosehill's Jev election experiments; it does not claim priority.

## Cohort and resolution

At most 30 US House and Senate races in the 2026 general election. Select from one dated public Crystal Ball ratings snapshot, Toss-up before Lean. Within a rating class, prefer coverage by both a qualifying poll and independent local reporting; break ties by SHA-256 of race ID. Admit only races with independently checked candidate roster and actual election geography. Keep all ballot nominees and OTHER_WINNER for an unlisted/write-in winner. Do not include Likely or Safe seats just to hit 30. Freeze the chosen IDs before inference; missing later inputs never trigger replacement.

The outcome is the official certified winner of the named contest, including any required runoff. A projection is not resolution. Missing certification remains pending. No national chamber probabilities are inferred from this selected cohort.

## Time

Initial cutoff is the actual freeze time, never a retrospective October27 label. Final predeclared cutoff is 2026-11-02T23:00:00Z (18:00 Eastern, 15:00 Pacific). For every observation preserve publication, substantiated availability and acquisition time. Input must have been acquired and available by cutoff. Unknown availability excludes an input. The final run may execute after cutoff using already-acquired material; log execution time and disclose lateness, never call a post-result run prospective. Initial freezes cannot be backdated beyond clock tolerance. No scheduled automation.

## Evidence and arms

A: identities, incumbency, comparable official prior results and finance. B: A+polls. C: A+qualitative bundle. D: A+polls+the same qualitative bundle. All candidates remain options even if a source only mentions two. Missing evidence is missing, not a zero or a fabricated probability.

Polls: original publisher, general election, field dates ending within30days, public bycutoff. For polling-leader comparison use latest release per pollster and prefer LV over RV when available. Equal mean of aligned candidate shares; no share-to-win-probability conversion. Candidate-authored documents: at most2 per candidate. Independent local reporting: at most5 race-specific documents in60days. Within quotas newest first then sourceID. Deduplicate repeated source text; retain source omissions.

Qualitative arm requires at least one independent race-specific local report or a verified geographically relevant focus-group record. Candidate statements alone do not establish balanced independent coverage; absence of a candidate statement is visible. Focus groups require original recording/transcript anchors, format (full session/clip/summary), recruitment and geography where known. State groups can inform state Senate races; House requires district geography. National context is not local evidence. Statements are not independent sampled voters. No synthetic people or substitute transcripts.

Public inference inputs require allowed model use and redistribution of the exact approved factual records/excerpts. Source registry records each rights basis separately. Unknown rights or missing text remains metadata-only. Vote-Scope is not a required data dependency.

## Sensitivity

For B and D, run canonical, reversed candidate block/option order, and reversed evidence record order. Maintain byte-equivalent underlying facts, identical question wording and canonical candidate IDs. Primary results use canonical output. Never select a pleasing variant or rerun a valid surprising answer. Where D contains focus groups, run canonical D_no_focus as a secondary ablation. The primary D-B contrast tests the entire qualitative bundle, not focus groups individually.

30races×2snapshots×8 core slots=480; focus removal adds at most60. Separate passage classification cap1000. Budget6–8k estimated tokens/forecast, hard24,000UTF-8 bytes over state+questions, a proxy not an official tokenizer. Preserve whole records and log omissions. No silent truncation. Jev model pinned to jev-1.14.0; longcontext disabled. At most4 concurrent requests and2 transient retries. Failed responses remain failures; exact valid requests reuse cached results with original inference time.

Passage classifications are for the browsing interface; raw approved evidence, not unverified generated labels, feeds forecasting.

## Diagnostics and scoring

Archive known fair/biased die distributions, deterministic supplied outcomes and synthetic order variants before live election calls. These diagnostics test behavior, not election calibration. Do not label raw outputs calibrated probabilities even when diagnostics pass.

Primary endpoint: final-snapshot mean unscaled multiclass Brier score, sum_i(p_i-y_i)^2, range0–2. Paired contrast D minus B on identical valid races; negative favors additional evidence. Report race-level differences, denominator and failure/coverage exclusions. Include uniform probabilities over identical options; polling-leader top-choice accuracy is a separate comparator, not a probabilistic forecast. Initial snapshot and focus ablation are exploratory. Thirty races yield thirty outcomes, not hundreds of independent trials; common national shocks further limit generalization. No significance or calibration claims from tiny bins. Publish all errors and unresolved outcomes.

## Replay and publication

Source→acquisition hash→observation→snapshot→exact request→response→display value is the provenance chain. Exact stored replay is deterministic; future API inference may differ. Corrections create new immutable versions. Synthetic fixtures use fictional races and cannot enter production export. Contributor CI is offline without secrets. Raw archives, keys, headers and local paths stay private. Export only approved fields and content; no LFS pointers in the website bundle.
