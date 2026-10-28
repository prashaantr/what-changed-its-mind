import { describe, it, expect } from "vitest";
import {
  safeUrl,
  findForecast,
  formatDate,
  signatureValues,
  type Race,
} from "./types";
describe("public evidence helpers", () => {
  it("rejects script and local URLs from untrusted source records", () => {
    expect(safeUrl("javascript:alert(1)")).toBeNull();
    expect(safeUrl("file:///tmp/secret")).toBeNull();
    expect(safeUrl("https://example.org/a")).toBe("https://example.org/a");
  });
  it("never substitutes canonical output for a missing reversed request", () => {
    const race = {
      forecasts: [{ arm: "A", ordering: "canonical", id: "canonical" }],
    } as unknown as Race;
    expect(findForecast(race, "A", "reverse_candidates")).toBeUndefined();
    expect(findForecast(race, "A", "canonical")?.id).toBe("canonical");
    expect(findForecast(undefined, "A", "canonical")).toBeUndefined();
  });
  it("handles absent source dates without manufacturing a timestamp", () => {
    expect(formatDate(null)).toBe("Not recorded");
    expect(formatDate("bad")).toBe("Not recorded");
  });
});

describe("signature comparison", () => {
  it("requires stored valid results and never turns a missing arm into zero", () => {
    const race = {
      forecasts: [
        {
          arm: "D",
          ordering: "canonical",
          status: "ok",
          probabilities: { a: 0.7 },
        },
        {
          arm: "D",
          ordering: "reverse_candidates",
          status: "error",
          probabilities: { a: 0.2 },
        },
      ],
    } as unknown as Race;
    expect(signatureValues(race, "a")).toEqual({
      b: null,
      d: 0.7,
      low: null,
      high: null,
      count: 1,
    });
    expect(signatureValues(undefined, "a").count).toBe(0);
  });
  it("reports the min-max of valid D orderings and excludes out-of-range values", () => {
    const race = {
      forecasts: [
        {
          arm: "B",
          ordering: "canonical",
          status: "ok",
          probabilities: { a: 0.4 },
        },
        {
          arm: "D",
          ordering: "canonical",
          status: "ok",
          probabilities: { a: 0.7 },
        },
        {
          arm: "D",
          ordering: "reverse_candidates",
          status: "ok",
          probabilities: { a: 0.65 },
        },
        {
          arm: "D",
          ordering: "reverse_evidence",
          status: "ok",
          probabilities: { a: 2 },
        },
      ],
    } as unknown as Race;
    expect(signatureValues(race, "a")).toEqual({
      b: 0.4,
      d: 0.7,
      low: 0.65,
      high: 0.7,
      count: 2,
    });
  });
});

it("includes the residual outcome and preserves exact request option order", async () => {
  const { candidateOptions, storedChoiceOrder, exactTimestamp } = await import(
    "./types"
  );
  const race = {
    candidates: [{ id: "a", name: "A", party: "D", incumbent: null }],
  } as unknown as Race;
  expect(candidateOptions(race).map((c) => c.id)).toEqual([
    "a",
    "OTHER_WINNER",
  ]);
  expect(
    storedChoiceOrder({
      request: {
        questions: { winner: { criteria: { OTHER_WINNER: "Other", a: "A" } } },
      },
    } as unknown as import("./types").Forecast),
  ).toEqual(["OTHER_WINNER", "a"]);
  expect(storedChoiceOrder(undefined)).toEqual([]);
  expect(exactTimestamp("2026-11-02T23:00:00Z")).toBe(
    "2026-11-02 23:00:00 UTC",
  );
});

it("loads snapshots only from the catalog and rejects arbitrary URLs and traversal", async () => {
  const { snapshotPath } = await import("./types");
  const entries = [
    {
      id: "initial-v1",
      cutoff: "2026-10-28T00:00:00Z",
      url: "data/snapshots/initial-v1.json",
    },
  ];
  expect(snapshotPath("", entries)).toBe("data/experiment.json");
  expect(snapshotPath("initial-v1", entries)).toBe(
    "data/snapshots/initial-v1.json",
  );
  expect(() => snapshotPath("https://evil.example/data.json", entries)).toThrow(
    "not in the published archive",
  );
  expect(() =>
    snapshotPath("bad", [
      { id: "bad", cutoff: "", url: "data/snapshots/../../secret.json" },
    ]),
  ).toThrow();
  expect(() =>
    snapshotPath("bad", [
      { id: "bad", cutoff: "", url: "https://evil.example/a.json" },
    ]),
  ).toThrow();
});
