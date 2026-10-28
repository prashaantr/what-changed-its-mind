# What changed its mind? — web essay

Static React/Vite/TypeScript site. Run on Node 22.12+ with `npm ci`, then `npm run dev -- --port 5173`. `npm run build` typechecks and produces `dist/`; `npm test` runs offline helper tests.

The coordinator's export command must write `public/data/experiment.json` using the contract in `../../docs/WEB_CONTRACT.md`. The browser fetches this bundle and local state geometry only. It never calls Jev or substitutes synthetic forecasts. Missing data displays an explicit loading/error/collecting state.

`data/fixture.json` is fictional development data, deliberately outside `public/` and never included in the deployed app. Tests may intercept the data request with this fixture. Do not copy it into production public data.

All geography comes from us-atlas 3.0.1 (ISC; public/geo/ATTRIBUTION.md). It is **state** geography, not congressional district geography. Source provenance remains available from the map race records and source register. All source links are restricted to http(s), text is escaped by React, and model receipts contain only the exported allowlisted fields.

Fonts are self-hosted through Fontsource: Archivo Black and Public Sans, both under the SIL Open Font License. Their license texts are included in public/licenses.

Build uses a relative base path for GitHub Pages project deployment. Upload `dist/` as the Pages artifact; do not deploy node_modules, raw data, private inference requests or LFS pointers. Browser functionality does not require credentials.
