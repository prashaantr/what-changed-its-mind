# Architecture

## Context

```mermaid
C4Context
  title What Changed Its Mind — context
  Person(reader, "Reader", "Explores evidence and model behavior")
  Person(contributor, "Contributor", "Adds verified sources and fixes")
  System(lab, "Election experiment", "Frozen evidence and public audit")
  System_Ext(sources, "Primary publishers", "Election records, polls, reporting")
  System_Ext(jev, "TypeSafe Jev", "Pinned decision model")
  Rel(reader, lab, "Explores public results", "HTTPS")
  Rel(contributor, lab, "Submits reviewed changes", "Git")
  Rel(lab, sources, "Acquires registered evidence", "HTTPS")
  Rel(lab, jev, "Submits approved bounded packets", "HTTPS")
```

## Containers

```mermaid
C4Container
  title What Changed Its Mind — containers
  Person(reader, "Reader")
  System_Ext(sources, "Primary publishers", "Public evidence")
  System_Ext(jev, "Jev 1.14", "Typed probability answers")
  Container(pipeline, "Research CLI", "Python / Pydantic", "Collects, freezes, forecasts and scores")
  ContainerDb(local, "Local archive", "Ignored files", "Raw sources, key and API cache")
  ContainerDb(public, "Versioned artifacts", "Git / optional LFS", "Approved records and immutable outputs")
  Container(web, "Interactive essay", "React / Vite / D3", "Static GitHub Pages site")
  Rel(pipeline, sources, "Fetches allowlisted URLs", "HTTPS")
  Rel(pipeline, local, "Stores private raw receipts", "Files")
  Rel(pipeline, jev, "Requests typed judgments", "HTTPS")
  Rel(pipeline, public, "Exports reviewed artifacts", "JSON")
  Rel(web, public, "Reads public bundle", "HTTPS")
  Rel(reader, web, "Explores and audits", "HTTPS")
```

Classifications annotate browsing; forecasts consume original approved evidence. Certified outcomes enter scoring only. No browser-side API key, database or server-side inference. Data flow and privacy boundaries are enforced in snapshot/export modules, not by display conventions.
