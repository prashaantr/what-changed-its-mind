import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { geoPath } from "d3-geo";
import { feature } from "topojson-client";
import type { FeatureCollection, Geometry } from "geojson";
import type { Topology, GeometryCollection } from "topojson-specification";
import "@fontsource/archivo-black/latin-400.css";
import "@fontsource/public-sans/latin-400.css";
import "@fontsource/public-sans/latin-600.css";
import "@fontsource/public-sans/latin-700.css";
import "./style.css";
import {
  ARMS,
  signatureValues,
  snapshotPath,
  type SnapshotEntry,
  exactTimestamp,
  candidateOptions,
  storedChoiceOrder,
  type Acquisition,
  validWeight,
  findForecast,
  formatDate,
  safeUrl,
  type Bundle,
  type Race,
  type Source,
  type Forecast,
  type Observation,
} from "./types";
const chapters = [
  ["question", "The question"],
  ["map", "The races"],
  ["evidence", "The evidence"],
  ["shuffle", "The stress test"],
  ["receipts", "The receipts"],
  ["limits", "The fine print"],
];
const base = import.meta.env.BASE_URL;
function Arrow() {
  return (
    <svg
      width="19"
      height="19"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}
function External({
  url,
  children,
}: {
  url: string;
  children: React.ReactNode;
}) {
  const href = safeUrl(url);
  return href ? (
    <a href={href} target="_blank" rel="noreferrer">
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  ) : (
    <span>{children}</span>
  );
}
export function App() {
  const [bundle, setBundle] = useState<Bundle | null>(null),
    [error, setError] = useState(""),
    [reload, setReload] = useState(0),
    [active, setActive] = useState("question");
  const [state, setState] = useState("all"),
    [raceId, setRaceId] = useState(""),
    [arm, setArm] = useState("A"),
    [order, setOrder] = useState("canonical"),
    [filter, setFilter] = useState("all"),
    [query, setQuery] = useState(""),
    [mapMode, setMapMode] = useState<"coverage" | "estimate">("coverage"),
    [shuffleNotice, setShuffleNotice] = useState(""),
    [catalog, setCatalog] = useState<SnapshotEntry[]>([]),
    [snapshotId, setSnapshotId] = useState(
      () => new URLSearchParams(window.location.search).get("snapshot") || "",
    ),
    [receipt, setReceipt] = useState<{
      sourceId?: string;
      observation?: Observation;
      forecast?: Forecast;
    } | null>(null);
  useEffect(() => {
    let live = true;
    setError("");
    setBundle(null);
    fetch(`${base}data/snapshots.json`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then(async (manifest) => {
        const entries: SnapshotEntry[] = Array.isArray(manifest?.snapshots)
          ? manifest.snapshots.filter(
              (entry: SnapshotEntry) =>
                typeof entry.id === "string" &&
                typeof entry.cutoff === "string" &&
                typeof entry.url === "string",
            )
          : [];
        if (live) setCatalog(entries);
        const path = snapshotPath(snapshotId, entries);
        const response = await fetch(`${base}${path}`);
        if (!response.ok)
          throw Error("The published dataset could not be loaded.");
        return response.json();
      })
      .then((d: Bundle) => {
        if (
          d.schemaVersion !== "1.0" ||
          !Array.isArray(d.races) ||
          !Array.isArray(d.sources)
        )
          throw Error("This dataset has an unsupported format.");
        if (snapshotId && d.snapshot?.id !== snapshotId)
          throw Error(
            "The archived bundle does not match the selected snapshot.",
          );
        if (live) {
          setBundle(d);
          setRaceId(
            d.races.find((r) => r.selected)?.id || d.races[0]?.id || "",
          );
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [reload, snapshotId]);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(e.target.id);
      },
      { rootMargin: "-15% 0px -60% 0px", threshold: 0 },
    );
    document
      .querySelectorAll("main section[id]")
      .forEach((e) => observer.observe(e));
    return () => observer.disconnect();
  }, [bundle]);
  const race = bundle?.races.find((r) => r.id === raceId);
  const forecast = findForecast(race, arm, order);
  const shown =
    bundle?.races.filter(
      (r) =>
        (state === "all" || r.stateFips === state) &&
        (filter === "all" || r.office === filter) &&
        `${r.name} ${r.state} ${r.candidates.map((c) => c.name).join(" ")}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    ) || [];
  const selectedArm = ARMS.find((a) => a.id === arm)!;
  const downloadPath = (() => {
    try {
      return snapshotPath(snapshotId, catalog);
    } catch {
      return "data/experiment.json";
    }
  })();
  const chooseSnapshot = (id: string) => {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("snapshot", id);
    else url.searchParams.delete("snapshot");
    window.history.replaceState(null, "", url);
    setSnapshotId(id);
    setReceipt(null);
  };
  const chooseOrder = (next: string) => {
    if (arm !== "B" && arm !== "D") {
      setArm("B");
      setShuffleNotice("Switched to arm B, which has predeclared order tests.");
    } else setShuffleNotice("");
    setOrder(next);
  };
  const chooseState = (s: string) => {
    setState(s);
    const next = bundle?.races.find((r) => r.stateFips === s);
    if (next) setRaceId(next.id);
  };
  return (
    <>
      <a className="skip-link" href="#map">
        Skip to the map
      </a>
      <header className="masthead">
        <a className="wordmark" href="#question">
          What changed
          <br />
          its mind<span>?</span>
        </a>
        <span className="mast-caption">
          An open experiment in election evidence
        </span>
        <nav className="top-links" aria-label="Project">
          <a href="#map">Explore</a>
          <a href="#evidence">Experiment</a>
          <a href="#receipts">Sources</a>
          <a
            href="https://github.com/prashaantr/what-changed-its-mind"
            target="_blank"
            rel="noreferrer"
          >
            Contribute ↗
          </a>
        </nav>
        <a className="method-link" href="#limits">
          Read the method <Arrow />
        </a>
      </header>
      <nav className="chapter-nav" aria-label="Essay chapters">
        {chapters.map(([id, title], i) => (
          <a
            key={id}
            href={`#${id}`}
            aria-current={active === id ? "location" : undefined}
          >
            <span>{i + 1}</span>
            {title}
          </a>
        ))}
      </nav>
      <main>
        <section id="question" className="opening">
          <div className="opening-copy">
            <h1>
              Same election.
              <br />
              Different evidence.
              <br />
              <span>Different answer?</span>
            </h1>
            <p className="standfirst">
              Give Jev the numbers, the polls, or the words. Compare four
              evidence sets—and follow every decision back to its source.
            </p>
            <a href="#map" className="text-action">
              Explore the experiment <Arrow />
            </a>
          </div>
          <div
            className="thesis-graphic"
            aria-label="Four evidence sets go into the same model; their decisions are compared"
          >
            <div className="evidence-stack">
              {ARMS.map((a, i) => (
                <a
                  href="#evidence"
                  className={`evidence-strip strip-${i}`}
                  key={a.id}
                  style={{ "--arm": a.color } as React.CSSProperties}
                  onClick={() => setArm(a.id)}
                >
                  <b>{a.id}</b>
                  <span>{a.short}</span>
                  <Arrow />
                </a>
              ))}
            </div>
            <div className="model-node">
              Jev<span>one model / four views</span>
            </div>
            <div className="question-node">?</div>
            <p className="graphic-caption">
              A controlled comparison.
              <br />
              An answer is not a result.
            </p>
          </div>
          <div className="opening-foot">
            <span>2026 US midterms</span>
            <span>
              {bundle
                ? `${bundle.stats.races} races in the source register`
                : "Building the public evidence register"}
            </span>
            <span className="status">
              <i />
              {bundle?.status === "ready"
                ? "Published experiment"
                : "Collection in progress"}
            </span>
          </div>
        </section>
        {error ? (
          <div className="load-error" role="alert">
            <h2>The evidence is taking a detour.</h2>
            <p>{error} No substitute forecasts are shown.</p>
            <button onClick={() => setReload((n) => n + 1)}>
              Try loading again
            </button>
            {snapshotId && (
              <button onClick={() => chooseSnapshot("")}>
                Use current dataset
              </button>
            )}
          </div>
        ) : !bundle ? (
          <div className="loading" role="status">
            Loading the published evidence register…
          </div>
        ) : (
          <>
            <section id="map" className="map-section">
              <div className="section-intro">
                <div>
                  <h2>Start with a place.</h2>
                  <p>
                    Every race begins with a source. Select a state, then
                    inspect a race.
                  </p>
                </div>
                <div className="dataset-stamp">
                  <strong>
                    {bundle.stats.selected}
                    <span> / {bundle.protocol.targetRaces}</span>
                  </strong>
                  <span>races selected for the experiment</span>
                </div>
              </div>
              <div className="atlas">
                <div className="map-column">
                  <MapMode mode={mapMode} onChange={setMapMode} />
                  <USMap
                    races={bundle.races}
                    state={state}
                    onSelect={chooseState}
                    mode={mapMode}
                    arm={arm}
                  />
                  <div className="map-legend">
                    <span>
                      <i className="sample-swatch" />
                      Frozen cohort
                    </span>
                    <span>
                      <i className="blank-swatch" />
                      Outside cohort / no data
                    </span>
                    <button onClick={() => setState("all")}>
                      Show all states
                    </button>
                  </div>
                  <p className="map-note">
                    State-level locations. House districts are listed by ID;
                    shapes do not imply verified district boundaries. Coverage
                    highlights the frozen cohort; other registered races remain
                    inspectable. Model estimate shows stored Senate decisions
                    only.
                  </p>
                </div>
                <aside className="race-browser" aria-label="Race browser">
                  <div className="browser-tools">
                    <label className="sr-only" htmlFor="race-search">
                      Find a race or candidate
                    </label>
                    <input
                      id="race-search"
                      type="search"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Find a race or candidate"
                    />
                    <label className="sr-only" htmlFor="office-filter">
                      Filter by office
                    </label>
                    <select
                      id="office-filter"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option value="all">All races</option>
                      <option value="senate">Senate</option>
                      <option value="house">House</option>
                    </select>
                  </div>
                  <div className="result-label" aria-live="polite">
                    {shown.length} {shown.length === 1 ? "race" : "races"}
                    {state !== "all" ? " in selected state" : ""}
                  </div>
                  <div className="race-list">
                    {shown.length ? (
                      shown.map((r) => (
                        <button
                          className={`race-row ${raceId === r.id ? "is-selected" : ""}`}
                          key={r.id}
                          onClick={() => setRaceId(r.id)}
                          aria-pressed={raceId === r.id}
                        >
                          <span>
                            <b>{r.name}</b>
                            <small>
                              {r.office === "house"
                                ? `House · district ${r.district}`
                                : "Senate"}{" "}
                              · {r.rating || "Rating unverified"}
                            </small>
                          </span>
                          <span className="race-count">
                            {r.observations.length}
                            <small>records</small>
                          </span>
                        </button>
                      ))
                    ) : (
                      <p className="empty-small">
                        No matching races. Try another state or clear your
                        search.
                      </p>
                    )}
                  </div>
                </aside>
              </div>
              <RaceDetail race={race} onSource={setReceipt} />
            </section>
            <div className="experiment-story">
              <div className="experiment-narrative">
                <section id="evidence" className="evidence-section">
                  <div className="section-intro">
                    <div>
                      <h2>
                        Change the evidence.
                        <br />
                        <span className="muted">Keep the question.</span>
                      </h2>
                      <p>
                        The same race, four controlled views. Choose an evidence
                        set to inspect its stored decision.
                      </p>
                    </div>
                  </div>
                  <div
                    className="arm-tabs"
                    role="tablist"
                    aria-label="Evidence sets"
                  >
                    {ARMS.map((a) => (
                      <button
                        id={`tab-${a.id}`}
                        role="tab"
                        tabIndex={arm === a.id ? 0 : -1}
                        onKeyDown={(e) => {
                          const index = ARMS.findIndex((x) => x.id === a.id);
                          const next =
                            e.key === "ArrowRight"
                              ? (index + 1) % ARMS.length
                              : e.key === "ArrowLeft"
                                ? (index + ARMS.length - 1) % ARMS.length
                                : e.key === "Home"
                                  ? 0
                                  : e.key === "End"
                                    ? ARMS.length - 1
                                    : -1;
                          if (next >= 0) {
                            e.preventDefault();
                            setArm(ARMS[next].id);
                            document
                              .getElementById(`tab-${ARMS[next].id}`)
                              ?.focus();
                          }
                        }}
                        aria-selected={arm === a.id}
                        aria-controls="arm-panel"
                        className={arm === a.id ? "active" : ""}
                        key={a.id}
                        style={{ "--arm": a.color } as React.CSSProperties}
                        onClick={() => setArm(a.id)}
                      >
                        <b>{a.id}</b>
                        <span>{a.short}</span>
                      </button>
                    ))}
                  </div>
                  <div
                    className="arm-panel"
                    id="arm-panel"
                    role="tabpanel"
                    aria-labelledby={`tab-${arm}`}
                  >
                    <div className="arm-explanation">
                      <span
                        className="large-letter"
                        style={{ color: selectedArm.color }}
                      >
                        {arm}
                      </span>
                      <div>
                        <h3>{selectedArm.title}</h3>
                        <p>{selectedArm.description}</p>
                        <p className="small-print">
                          Primary comparison:{" "}
                          {bundle.protocol.primaryComparison}
                        </p>
                      </div>
                    </div>
                    <div className="decision-panel">
                      <div className="panel-heading">
                        <h3>{race?.name || "Select a race"}</h3>
                        <span>{order.replaceAll("_", " ")}</span>
                      </div>
                      <ForecastView forecast={forecast} race={race} />
                      {forecast && (
                        <button
                          className="text-action"
                          onClick={() => setReceipt({ forecast })}
                        >
                          Open model receipt <Arrow />
                        </button>
                      )}
                      <p className="small-print">
                        These are model choice weights, not calibrated election
                        probabilities.
                      </p>
                    </div>
                  </div>
                </section>
                <section id="shuffle" className="shuffle-section">
                  <div>
                    <h2>
                      Would it say that
                      <br />
                      if we shuffled
                      <br />
                      <span>the page?</span>
                    </h2>
                    <p>
                      Evidence can stay the same while its order changes. A
                      robust judgement should not depend on which candidate
                      appears first.
                    </p>
                    <button
                      className="shuffle-button"
                      onClick={() =>
                        chooseOrder(
                          order === "canonical"
                            ? "reverse_candidates"
                            : "canonical",
                        )
                      }
                    >
                      <svg
                        aria-hidden="true"
                        width="22"
                        height="22"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                      >
                        <path d="M3 7h4l10 10h4M17 14l4 3-4 3M3 17h4L17 7h4M17 4l4 3-4 3" />
                      </svg>
                      {order === "canonical"
                        ? "Reverse candidate order"
                        : "Restore canonical order"}
                    </button>
                    <div
                      className="order-options"
                      aria-label="Stored ordering variants"
                    >
                      {[
                        "canonical",
                        "reverse_candidates",
                        "reverse_evidence",
                      ].map((o) => (
                        <button
                          key={o}
                          aria-pressed={order === o}
                          onClick={() => chooseOrder(o)}
                        >
                          {o === "canonical"
                            ? "Original"
                            : o === "reverse_candidates"
                              ? "Candidates reversed"
                              : "Evidence reversed"}
                        </button>
                      ))}
                    </div>
                    <p className="small-print" aria-live="polite">
                      {shuffleNotice} Showing {order.replaceAll("_", " ")}{" "}
                      order. This control selects stored runs; it never calls
                      Jev.
                    </p>
                  </div>
                  <div className="order-comparison">
                    <div className="order-label">
                      <span>Same evidence</span>
                      <span>Different arrangement</span>
                    </div>
                    <div className="order-slips">
                      {storedChoiceOrder(forecast).map(
                        (candidateId, position) => {
                          const candidate = candidateOptions(race).find(
                            (c) => c.id === candidateId,
                          );
                          return (
                            <div
                              key={candidateId}
                              className={`order-slip candidate-${position % 2}`}
                            >
                              <span>Option position {position + 1}</span>
                              <strong>{candidate?.name || candidateId}</strong>
                              <small>
                                {candidate?.party || "Unlisted option"}
                              </small>
                            </div>
                          );
                        },
                      )}
                      {!storedChoiceOrder(forecast).length && (
                        <p>
                          No stored request for this ordering. Option positions
                          will appear with the receipt.
                        </p>
                      )}
                      <p className="small-print">
                        Positions follow the exact stored Choice criteria,
                        including OTHER_WINNER. The verified ballot roster is
                        listed separately above.
                      </p>
                    </div>
                    <div className="shuffle-result">
                      <b>
                        {forecast?.status === "ok"
                          ? "Stored decision available"
                          : "Order test pending"}
                      </b>
                      <p>
                        {forecast?.status === "ok"
                          ? "Inspect the stored model output in the evidence panel above."
                          : "Order tests are predeclared for arms B and D. Paired results appear when the stored runs exist; no simulated flip stands in for a model response."}
                      </p>
                      <a href="#evidence">
                        Compare the decision <Arrow />
                      </a>
                    </div>
                  </div>
                </section>
              </div>
              <aside
                className="experiment-rail"
                aria-label="Persistent experiment comparison"
              >
                <div className="rail-inner">
                  <h3>{race?.name || "Choose a race"}</h3>
                  <details className="rail-map" open={window.innerWidth > 680}>
                    <summary>Explore map</summary>
                    <MapMode mode={mapMode} onChange={setMapMode} />
                    <USMap
                      races={bundle.races}
                      state={state}
                      onSelect={chooseState}
                      mode={mapMode}
                      arm={arm}
                    />
                    <p className="small-print">
                      Senate estimates only. House locations show state
                      coverage.
                    </p>
                  </details>
                  <SignatureChart race={race} />
                </div>
              </aside>
            </div>
            <section id="receipts" className="receipts-section">
              <div className="section-intro">
                <div>
                  <h2>No mysterious dots.</h2>
                  <p>
                    Every record has a source. Every model call gets a receipt.
                    Open one and follow the trail.
                  </p>
                </div>
                <div className="receipt-symbol" aria-hidden="true">
                  <svg viewBox="0 0 80 100" fill="none">
                    <path d="M15 8h50v84l-8-5-8 5-9-5-9 5-8-5-8 5V8Z" />
                    <path d="M25 28h30M25 40h30M25 52h18M25 68h30" />
                  </svg>
                </div>
              </div>
              <div className="source-table">
                <div className="source-table-head">
                  <span>Source / publisher</span>
                  <span>Material</span>
                  <span>Inspect</span>
                </div>
                {bundle.sources.map((s) => (
                  <button
                    className="source-row"
                    key={s.id}
                    onClick={() => setReceipt({ sourceId: s.id })}
                  >
                    <span>
                      <b>{s.title}</b>
                      <small>{s.publisher}</small>
                    </span>
                    <span className="source-kind">
                      {s.kind.replaceAll("_", " ")}
                    </span>
                    <Arrow />
                  </button>
                ))}
                {!bundle.sources.length && (
                  <p className="empty-small">
                    No public sources have been exported yet.
                  </p>
                )}
              </div>
            </section>
            <section id="limits" className="limits-section">
              <h2>
                The interesting part
                <br />
                is finding out
                <br />
                <span>where it fails.</span>
              </h2>
              <div className="method-columns">
                <div>
                  <h3>An experiment, in public.</h3>
                  <p className="personal-note">
                    I wanted to see what changes a model’s mind: stronger
                    evidence, or just a different arrangement of the same facts.
                    This is my attempt to make that question inspectable.
                  </p>
                  <p>
                    Freeze the inputs before the election. Compare evidence sets
                    and simple baselines. Publish the misses alongside the hits.
                  </p>
                  <label className="snapshot-label" htmlFor="snapshot-picker">
                    Published snapshot
                  </label>
                  <select
                    id="snapshot-picker"
                    className="snapshot-picker"
                    value={snapshotId}
                    onChange={(e) => chooseSnapshot(e.target.value)}
                  >
                    <option value="">Current dataset</option>
                    {catalog.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.id} · {exactTimestamp(entry.cutoff)}
                      </option>
                    ))}
                  </select>
                  <p className="small-print">
                    Archived snapshots are immutable. Selecting one loads its
                    stored evidence and decisions.
                  </p>
                  <dl className="method-facts">
                    <div>
                      <dt>Model</dt>
                      <dd>{bundle.model}</dd>
                    </div>
                    <div>
                      <dt>Final evidence cutoff</dt>
                      <dd>{exactTimestamp(bundle.protocol.finalCutoff)}</dd>
                    </div>
                    <div>
                      <dt>Published forecasts</dt>
                      <dd>{bundle.stats.forecasts}</dd>
                    </div>
                    <div>
                      <dt>Snapshot</dt>
                      <dd>{bundle.snapshot?.id || "Not frozen yet"}</dd>
                    </div>
                  </dl>
                </div>
                <div>
                  <h3>What this cannot tell us.</h3>
                  <ul>
                    {bundle.limitations.length ? (
                      bundle.limitations.map((l, i) => <li key={i}>{l}</li>)
                    ) : (
                      <>
                        <li>
                          Model confidence is not a measured chance of winning.
                        </li>
                        <li>
                          Missing sources are missing evidence, not evidence
                          against a candidate.
                        </li>
                        <li>
                          Historical tests may be affected by information in the
                          model’s training data.
                        </li>
                      </>
                    )}
                  </ul>
                  <Evaluation evaluation={bundle.evaluation} />
                  {bundle.diagnostics.length > 0 && (
                    <details className="diagnostics">
                      <summary>
                        Inspect {bundle.diagnostics.length} diagnostic records
                      </summary>
                      <p>
                        Model behaviour checks are separate from election
                        results and do not establish election calibration.
                      </p>
                      {bundle.diagnostics.map((d, i) => (
                        <pre tabIndex={0} key={i}>
                          {JSON.stringify(d, null, 2)}
                        </pre>
                      ))}
                    </details>
                  )}
                  <p className="method-note">
                    The map is a way into the evidence—not a live results feed.
                    Official outcomes will be evaluated separately after the
                    inputs are frozen.
                  </p>
                </div>
              </div>
            </section>
          </>
        )}
      </main>
      <footer>
        <a className="wordmark" href="#question">
          What changed its mind?
        </a>
        <p>
          Built to be questioned.
          <br />
          Open evidence. Inspectable decisions.
        </p>
        <span>
          {bundle
            ? `Dataset exported ${formatDate(bundle.generatedAt)}`
            : "Awaiting dataset"}
          <br />
          <a
            href="https://github.com/prashaantr/what-changed-its-mind"
            target="_blank"
            rel="noreferrer"
          >
            GitHub / contribute ↗
          </a>
          <br />
          <a href={`${base}${downloadPath}`} download>
            Download public dataset
          </a>
        </span>
      </footer>
      {receipt && (
        <Receipt
          item={receipt}
          sources={bundle?.sources || []}
          acquisitions={bundle?.acquisitions || []}
          onClose={() => setReceipt(null)}
        />
      )}
    </>
  );
}
function MapMode({
  mode,
  onChange,
}: {
  mode: "coverage" | "estimate";
  onChange: (mode: "coverage" | "estimate") => void;
}) {
  return (
    <div className="map-mode" aria-label="Map colour">
      <button
        aria-pressed={mode === "coverage"}
        onClick={() => onChange("coverage")}
      >
        Coverage
      </button>
      <button
        aria-pressed={mode === "estimate"}
        onClick={() => onChange("estimate")}
      >
        Model estimate
      </button>
      {mode === "estimate" && (
        <span>Senate · selected arm · canonical output</span>
      )}
    </div>
  );
}
export function SignatureChart({ race }: { race: Race | undefined }) {
  const [chosen, setChosen] = useState("");
  const options = candidateOptions(race);
  const candidate =
    options.find((c) => c.id === chosen) ||
    race?.candidates.find((c) => ["DEM", "D"].includes(c.party)) ||
    race?.candidates[0];
  const v = signatureValues(race, candidate?.id || "");
  const pct = (n: number | null) =>
    n === null ? "Pending" : `${(n * 100).toFixed(1)}%`;
  return (
    <div className="signature">
      <div className="signature-title">
        <h4>What changed?</h4>
        <span>B → D</span>
      </div>
      <label htmlFor="signature-candidate">Compare candidate</label>
      <select
        id="signature-candidate"
        value={candidate?.id || ""}
        onChange={(e) => setChosen(e.target.value)}
      >
        {!candidate && <option value="">Roster pending</option>}
        {options.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <svg
        viewBox="0 0 420 100"
        role="img"
        aria-label={`Model choice weights: B ${pct(v.b)}, D ${pct(v.d)}. ${v.count} valid D order variants.`}
      >
        <line x1="25" y1="48" x2="395" y2="48" stroke="#bbb" />
        {[0, 25, 50, 75, 100].map((n) => (
          <g key={n}>
            <line
              x1={25 + n * 3.7}
              y1="43"
              x2={25 + n * 3.7}
              y2="53"
              stroke="#aaa"
            />
            <text x={25 + n * 3.7} y="78" textAnchor="middle">
              {n}%
            </text>
          </g>
        ))}
        {v.low !== null && v.high !== null && (
          <rect
            x={25 + v.low * 370}
            y="37"
            width={Math.max(2, (v.high - v.low) * 370)}
            height="22"
            fill="#e5ae38"
            opacity=".7"
          />
        )}
        {v.b !== null && v.d !== null && (
          <line
            x1={25 + v.b * 370}
            x2={25 + v.d * 370}
            y1="48"
            y2="48"
            stroke="#242424"
            strokeWidth="2"
          />
        )}
        {v.b !== null && (
          <circle
            cx={25 + v.b * 370}
            cy="48"
            r="6"
            fill="#008fd5"
            stroke="#242424"
          />
        )}
        {v.d !== null && (
          <circle
            cx={25 + v.d * 370}
            cy="48"
            r="6"
            fill="#fc4f30"
            stroke="#242424"
          />
        )}
        {v.b === null && v.d === null && (
          <text x="210" y="23" textAnchor="middle">
            Awaiting stored B and D outputs
          </text>
        )}
      </svg>
      <div className="signature-legend">
        <span>
          <i style={{ background: "#008fd5" }} />
          B: polls
        </span>
        <span>
          <i style={{ background: "#fc4f30" }} />
          D: polls + qualitative
        </span>
        <span>
          <i style={{ background: "#e5ae38" }} />D order range
        </span>
      </div>
      <p className="small-print">
        The band is the min–max of {v.count} valid stored D orderings; at least
        two are required. <strong>Not a confidence interval.</strong> Choice
        weights are not calibrated win probabilities.
      </p>
      <details className="exact-values">
        <summary>Exact values · all candidates</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>B</th>
                <th>D</th>
                <th>D order range</th>
              </tr>
            </thead>
            <tbody>
              {options.map((c) => {
                const x = signatureValues(race, c.id);
                return (
                  <tr key={c.id}>
                    <th>{c.name}</th>
                    <td>{pct(x.b)}</td>
                    <td>{pct(x.d)}</td>
                    <td>
                      {x.low === null
                        ? "Pending"
                        : `${pct(x.low)}–${pct(x.high)}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
function Evaluation({ evaluation }: { evaluation: Bundle["evaluation"] }) {
  const rows: Array<[string, string]> = [];
  const flatten = (value: unknown, path: string) => {
    if (value !== null && typeof value === "object") {
      for (const [k, v] of Object.entries(value))
        flatten(v, path ? `${path} / ${k}` : k);
    } else rows.push([path, value === null ? "Pending" : String(value)]);
  };
  if (evaluation) flatten(evaluation, "");
  return (
    <div className="evaluation">
      <h3>After the outcomes arrive.</h3>
      {!evaluation ? (
        <p>
          Evaluation pending. Certified outcomes will be compared with the
          frozen forecasts. No score is available yet.
        </p>
      ) : (
        <>
          <p>
            {Number(evaluation.resolved_count || 0)} certified outcomes;{" "}
            {Number(evaluation.pending_count || 0)} races pending.
            {Number(evaluation.resolved_count || 0) === 0
              ? " Scores will appear when official results resolve."
              : " The comparisons below use only certified, resolved races."}
          </p>
          <details className="evaluation-details">
            <summary>Inspect evaluation metrics and denominators</summary>
            <table>
              <tbody>
                {rows.map(([key, value]) => (
                  <tr key={key}>
                    <th>{key.replaceAll("_", " ")}</th>
                    <td>{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
      <p className="small-print">
        Focus-group removal is a separate secondary comparison, available only
        where eligible evidence and paired stored runs exist.
      </p>
    </div>
  );
}
function USMap({
  races,
  state,
  onSelect,
  mode = "coverage",
  arm = "A",
}: {
  mode?: "coverage" | "estimate";
  arm?: string;
  races: Race[];
  state: string;
  onSelect: (s: string) => void;
}) {
  const [geo, setGeo] = useState<FeatureCollection<Geometry> | null>(null),
    [err, setErr] = useState(false);
  useEffect(() => {
    fetch(`${base}geo/states-albers-10m.json`)
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then((t: Topology<{ states: GeometryCollection }>) =>
        setGeo(feature(t, t.objects.states)),
      )
      .catch(() => setErr(true));
  }, []);
  const counts = useMemo(
    () =>
      new Map(
        races.map((r) => [
          r.stateFips,
          races.filter((x) => x.stateFips === r.stateFips).length,
        ]),
      ),
    [races],
  );
  const path = geoPath();
  if (err)
    return (
      <div className="map-fallback">
        The map could not load. All races remain available in the race list.
      </div>
    );
  return (
    <svg
      className="us-map"
      viewBox="0 0 975 610"
      role="group"
      aria-label="United States. Select a state to explore registered races."
    >
      {geo?.features.map((f) => {
        const id = String(f.id).padStart(2, "0"),
          count = counts.get(id) || 0;
        const senate = races.filter(
          (r) => r.stateFips === id && r.office === "senate",
        );
        const parties = senate.map((r) => {
          const f = findForecast(r, arm, "canonical");
          if (
            f?.status !== "ok" ||
            !f.selected ||
            validWeight(f, f.selected) === null
          )
            return null;
          return f.selected === "OTHER_WINNER"
            ? "OTHER"
            : r.candidates.find((c) => c.id === f.selected)?.party || null;
        });
        const party =
          parties.length > 0 && parties.every((p) => p && p === parties[0])
            ? parties[0]
            : null;
        const fill =
          mode === "estimate"
            ? party === "DEM" || party === "D"
              ? "#008FD5"
              : party === "REP" || party === "R"
                ? "#FC4F30"
                : party
                  ? "#8B6BB1"
                  : "#dfdfd8"
            : undefined;
        return (
          <path
            key={id}
            d={path(f) || ""}
            style={fill ? { fill } : undefined}
            className={`${races.some((r) => r.stateFips === id && r.selected) ? "has-races" : count ? "registered-races" : ""} ${state === id ? "selected-state" : ""}`}
            role="button"
            tabIndex={0}
            aria-label={`${f.properties?.name}, ${count} registered races`}
            aria-pressed={state === id}
            onClick={() => onSelect(id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(id);
              }
            }}
          >
            <title>
              {f.properties?.name}: {count} registered races
            </title>
          </path>
        );
      })}
      {!geo && (
        <text x="490" y="300" textAnchor="middle">
          Loading geography…
        </text>
      )}
    </svg>
  );
}
function RaceDetail({
  race,
  onSource,
}: {
  race: Race | undefined;
  onSource: (r: { sourceId?: string; observation?: Observation }) => void;
}) {
  if (!race) return null;
  return (
    <div className="race-detail">
      <div>
        <span className="race-id">{race.id}</span>
        <h3>{race.name}</h3>
        <p>{race.selectionReason}</p>
        <div className="candidate-names">
          {race.candidates.length ? (
            race.candidates.map((c) => (
              <span key={c.id}>
                <i
                  className={
                    c.party === "DEM"
                      ? "dem"
                      : c.party === "REP"
                        ? "rep"
                        : "other"
                  }
                />
                {c.name}
                <small>{c.party}</small>
              </span>
            ))
          ) : (
            <span>Candidate roster not yet verified</span>
          )}
        </div>
      </div>
      <div className="coverage">
        <h4>Evidence on file</h4>
        {[
          "fundamental",
          "poll",
          "candidate_statement",
          "local_reporting",
          "focus_group",
        ].map((k) => (
          <div className="coverage-row" key={k}>
            <span>
              {
                (
                  {
                    fundamental: "Fundamentals",
                    poll: "Polls",
                    candidate_statement: "Candidate statements",
                    local_reporting: "Local reporting",
                    focus_group: "Focus groups",
                  } as Record<string, string>
                )[k]
              }
            </span>
            <b>{race.coverage[k] || 0}</b>
          </div>
        ))}
        <p className="small-print">
          {race.missing.length
            ? `Missing: ${race.missing.join(", ").replaceAll("_", " ")}`
            : "See individual records for source coverage."}
        </p>
        {race.observations.length > 0 && (
          <details className="observation-browser">
            <summary>Inspect all {race.observations.length} records</summary>
            {race.observations.map((o) => (
              <button
                key={o.id}
                onClick={() =>
                  onSource({ observation: o, sourceId: o.sourceId })
                }
              >
                <span>
                  {o.kind.replaceAll("_", " ")}
                  <small>{o.locator}</small>
                </span>
                <Arrow />
              </button>
            ))}
          </details>
        )}
      </div>
    </div>
  );
}
function ForecastView({
  forecast,
  race,
}: {
  forecast: Forecast | undefined;
  race: Race | undefined;
}) {
  if (!forecast)
    return (
      <div className="pending-result">
        <span>—</span>
        <div>
          <strong>Forecast pending.</strong>
          <p>
            The source register is live. This evidence set has no published
            model output yet.
          </p>
        </div>
      </div>
    );
  if (forecast.status !== "ok" || !forecast.probabilities)
    return (
      <div className="pending-result">
        <div>
          <strong>Model output unavailable.</strong>
          <p>
            {forecast.error || "This request did not return a usable result."}
          </p>
        </div>
      </div>
    );
  return (
    <div className="forecast-bars">
      {Object.entries(forecast.probabilities).map(([id, p]) => (
        <div key={id}>
          <div className="forecast-label">
            <span>
              {candidateOptions(race).find((c) => c.id === id)?.name || id}
            </span>
            <b>{(p * 100).toFixed(1)}%</b>
          </div>
          <div className="bar-track">
            <div style={{ width: `${Math.min(100, Math.max(0, p * 100))}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
function Receipt({
  item,
  sources,
  acquisitions,
  onClose,
}: {
  item: { sourceId?: string; observation?: Observation; forecast?: Forecast };
  sources: Source[];
  acquisitions: Acquisition[];
  onClose: () => void;
}) {
  const source = sources.find((s) => s.id === item.sourceId),
    [tab, setTab] = useState("source"),
    [copied, setCopied] = useState(false),
    [copyError, setCopyError] = useState(false);
  const evidence = (
    item.forecast?.request as {
      state?: { evidence?: Array<{ acquisition_id?: string }> };
    } | null
  )?.state?.evidence;
  const requestAcquisitionIds = new Set(
    Array.isArray(evidence)
      ? evidence.map((o) => o.acquisition_id).filter(Boolean)
      : [],
  );
  const sourceAcquisitions = acquisitions.filter((a) =>
    item.observation?.acquisitionId
      ? a.id === item.observation.acquisitionId
      : item.forecast
        ? requestAcquisitionIds.has(a.id)
        : a.sourceId === source?.id,
  );
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const background = Array.from(
      document.querySelectorAll<HTMLElement>(
        ".masthead,.chapter-nav,main,footer",
      ),
    );
    background.forEach((el) => (el.inert = true));
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const elements = Array.from(
          document.querySelectorAll<HTMLElement>(
            ".receipt-drawer button,.receipt-drawer a,.receipt-drawer pre[tabindex]",
          ),
        );
        const first = elements[0],
          last = elements[elements.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    document.getElementById("close-receipt")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      background.forEach((el) => (el.inert = false));
      document.body.style.overflow = previousOverflow;
      previous?.focus();
    };
  }, [onClose]);
  const payload = item.forecast
    ? tab === "response"
      ? item.forecast.response
      : tab === "request"
        ? item.forecast.request
        : item.forecast
    : item.observation || source;
  return (
    <aside
      className="receipt-drawer"
      role="dialog"
      aria-modal="true"
      aria-labelledby="receipt-title"
    >
      <div className="drawer-header">
        <span>Evidence receipt</span>
        <button
          id="close-receipt"
          onClick={onClose}
          aria-label="Close evidence receipt"
        >
          Close <span aria-hidden="true">×</span>
        </button>
      </div>
      <h2 id="receipt-title">
        {item.forecast
          ? "Inside the model call."
          : source?.title || "Source record"}
      </h2>
      {source && (
        <>
          <p>{source.publisher}</p>
          <External url={source.url}>Visit original source ↗</External>
          <dl>
            <dt>Source ID</dt>
            <dd>{source.id}</dd>
            <dt>Public reuse status</dt>
            <dd>{source.redistribution}</dd>
            <dt>Rights basis</dt>
            <dd>{source.rightsBasis}</dd>
            <dt>Attribution</dt>
            <dd>{source.attribution}</dd>
          </dl>
          {source.notes && <p className="small-print">{source.notes}</p>}
        </>
      )}
      {item.observation && (
        <>
          <h3>The recorded evidence</h3>
          {item.observation.excerpt && (
            <blockquote>{item.observation.excerpt}</blockquote>
          )}
          <dl>
            <dt>Acquisition ID</dt>
            <dd>{item.observation.acquisitionId || "Not recorded"}</dd>
            <dt>Observation content SHA-256</dt>
            <dd className="hash">
              {item.observation.contentHash || "Not recorded"}
            </dd>
            <dt>Retrieved at (UTC)</dt>
            <dd>{exactTimestamp(item.observation.retrievedAt)}</dd>
            <dt>Source locator</dt>
            <dd>{item.observation.locator}</dd>
            <dt>Available by</dt>
            <dd>{formatDate(item.observation.availableAt)}</dd>
            <dt>Record type</dt>
            <dd>{item.observation.recordType}</dd>
          </dl>
        </>
      )}
      {sourceAcquisitions.map((acquisition) => (
        <div key={acquisition.id}>
          <h3>Acquisition receipt</h3>
          <dl>
            <dt>ID</dt>
            <dd>{acquisition.id}</dd>
            <dt>Raw source SHA-256</dt>
            <dd className="hash">{acquisition.rawHash}</dd>
            <dt>Retrieved at (UTC)</dt>
            <dd>{exactTimestamp(acquisition.retrievedAt)}</dd>
            <dt>Parser / media type</dt>
            <dd>
              {acquisition.parserVersion} / {acquisition.mediaType}
            </dd>
            <dt>Acquisition URL</dt>
            <dd>
              <External url={acquisition.finalUrl}>
                {acquisition.finalUrl}
              </External>
            </dd>
          </dl>
        </div>
      ))}
      {item.forecast && (
        <>
          <p>
            Stored output only. Opening this receipt does not run the model.
          </p>
          <dl>
            <dt>Arm / ordering</dt>
            <dd>
              {item.forecast.arm} / {item.forecast.ordering}
            </dd>
            <dt>Requested / returned model</dt>
            <dd>
              {item.forecast.requestedModel || "Not recorded"} /{" "}
              {item.forecast.returnedModel || "Not returned"}
            </dd>
            <dt>Started / completed (UTC)</dt>
            <dd>
              {exactTimestamp(item.forecast.startedAt)} /{" "}
              {exactTimestamp(item.forecast.completedAt)}
            </dd>
            <dt>Response digest</dt>
            <dd className="hash">
              {item.forecast.responseHash || "No stored response"}
            </dd>
            <dt>Usage / attempts</dt>
            <dd>
              <pre>{JSON.stringify(item.forecast.usage || {}, null, 2)}</pre>
            </dd>
            <dt>Request hash</dt>
            <dd className="hash">{item.forecast.requestHash}</dd>
            <dt>Source observation IDs</dt>
            <dd>
              {item.forecast.observationIds.join(", ") || "None recorded"}
            </dd>
            <dt>Omitted observation IDs</dt>
            <dd>{item.forecast.omittedObservationIds.join(", ") || "None"}</dd>
          </dl>
          <div
            className="receipt-tabs"
            role="tablist"
            aria-label="Receipt content"
          >
            {["source", "request", "response"].map((t) => (
              <button
                id={`receipt-tab-${t}`}
                role="tab"
                tabIndex={tab === t ? 0 : -1}
                onKeyDown={(e) => {
                  const tabs = ["source", "request", "response"];
                  const index = tabs.indexOf(t);
                  const next =
                    e.key === "ArrowRight"
                      ? (index + 1) % 3
                      : e.key === "ArrowLeft"
                        ? (index + 2) % 3
                        : -1;
                  if (next >= 0) {
                    e.preventDefault();
                    setTab(tabs[next]);
                    document
                      .getElementById(`receipt-tab-${tabs[next]}`)
                      ?.focus();
                  }
                }}
                aria-selected={tab === t}
                key={t}
                onClick={() => setTab(t)}
              >
                {t === "source" ? "Metadata" : t}
              </button>
            ))}
          </div>
        </>
      )}
      <div className="code-heading">
        <span>Machine-readable record</span>
        <button
          onClick={() => {
            navigator.clipboard
              .writeText(JSON.stringify(payload, null, 2))
              .then(() => {
                setCopied(true);
                setCopyError(false);
              })
              .catch(() => {
                setCopied(false);
                setCopyError(true);
              });
          }}
        >
          {copied ? "Copied" : "Copy JSON"}
        </button>
      </div>
      {copyError && (
        <p role="status" className="small-print">
          Clipboard access is unavailable. Select and copy the JSON below.
        </p>
      )}
      <pre tabIndex={0}>
        {JSON.stringify(payload, null, 2) || "No public payload available."}
      </pre>
      <p className="small-print">
        Only fields approved for the public dataset are shown. Missing payloads
        are not reconstructed.
      </p>
    </aside>
  );
}
const root = document.getElementById("root");
if (root)
  createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
