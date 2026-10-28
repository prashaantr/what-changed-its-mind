# Initial release: what is actually on file

The initial evidence cutoff is **2026-10-28 06:24:05.134763 UTC**, or **October 27 at 11:24:05 p.m. Pacific**. The registered cohort is Iowa, Kansas and Texas Senate. The immutable IDs and snapshot hash are in `experiments/cohort.json`.

This is a three-race exploratory release, not a national forecast. Six races are listed in the discovery register; only three passed the entry rules. North Carolina is outside the verified competitive cohort. Maine and Ohio lack verified candidate rosters in this collection. No House contest was admitted. The three selected races each have one official prior-election record, one original poll and one independent-reporting record. Finance, candidate-authored documents and usable focus-group material are missing. Qualitative records are cited factual extracts/paraphrases, not full transcripts. With no approved passages to classify, the passage-classification run made zero calls.

## What the model returned

Twenty-four election slots were attempted once, after eight known-process diagnostics. **Twenty-three returned valid distributions; one failed validation.** No valid answer was rerun to obtain a preferred result. The table below uses canonical B (fundamentals + polls), canonical D (B + reporting), and the range across three stored D orderings. Values are Jev choice weights, not calibrated win probabilities.

| Candidate | B | D | Tested D order range |
| --- | ---: | ---: | ---: |
| Josh Turek, Iowa | 72% | 74% | 71–74% |
| Adam Hamilton, Kansas | 16% | 17% | 11–17% |
| James Talarico, Texas | 74% | 72% | 72–78% |

These descriptive examples do not establish that the added reporting helped. There are no certified outcomes yet, so Brier scores and accuracy are pending. The primary analysis remains the predeclared final snapshot on November 2 at 23:00 UTC. The experiment has at most three eventual race outcomes; order variants do not create more elections.

The canonical Iowa C response failed because its returned probabilities did not sum to one. Its request, timestamps and validation error are retained. **An adapter defect meant that this first invalid raw response body was not archived.** The adapter now preserves invalid JSON response bodies and usage prospectively. The original failure record is unchanged; no replacement call was made. This limits auditing of that one response.

## Diagnostic observations

In the archived fair binary probe, Jev assigned 70% and 30% to outcomes explicitly described as equally likely. In the synthetic 70/30 candidate-order probe, Alpha received 77% in one order and 89% after reversal. These are single diagnostic observations with exact inputs in `results/diagnostics/initial.json`; they are not an estimate of general model calibration.

## Publication and later work

All successful election requests and provider responses are public. Raw acquired publisher pages and PDFs remain local. Hashes identify the acquired bytes; hashes are not a guarantee of source truth or provider authenticity. Code is MIT; source records and assets retain separate notices.

The public build contains a small JSON bundle and local state-map/font assets. No API key or public inference endpoint exists. The final snapshot and certified-outcome steps are manual commands in `docs/RUNBOOK.md`; no scheduled polling or automation was installed.
