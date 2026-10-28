# Approved bulk factual datasets

This directory is reserved for reviewed Parquet tables whose exact contents may be redistributed. `.gitattributes` tracks `data/bulk/*.parquet` with Git LFS. No bulk table is currently required for the three-race pilot.

Use LFS only after verifying each source's rights and removing personal contact fields, restricted text and private metadata. Public availability is not permission to upload full PDFs, recordings or transcripts. Raw acquisition bodies remain ignored in `data/raw/`; they do not belong here.

To prepare a reviewed table:

1. Install Git LFS and run `git lfs install` in the contributor checkout. Optionally install Parquet support with `uv sync --locked --extra dev --extra bulk`.
2. Export only approved factual columns from validated records. Preserve stable source/acquisition/observation IDs, applicable geography, dates and hashes. Never substitute unknowns with zeros.
3. Give each immutable table a versioned filename directly in this directory; the current LFS rule does not cover nested folders.
4. Add a small ordinary-Git manifest next to it with filename, actual byte SHA-256, row count, schema version, creation time, source IDs, upstream acquisition hashes, transformation command/code version, rights basis and required attribution. Include a correction/version note where relevant. Keep machine-local paths out.
5. Stage the approved table and manifest, then verify `git lfs ls-files` and `git lfs fsck`. Inspect the table's columns and row counts before pushing. Never commit an unreviewed raw corpus just because LFS can hold it.

Consumers needing the optional table run `git lfs pull --include='data/bulk/*.parquet'` after cloning. Site builds and offline core tests must not require that download. Produce the website's bounded, approved JSON through the exporter; never import a Parquet file or a Git LFS pointer into `apps/web/public/`. Code MIT licensing does not override data-source rights.
