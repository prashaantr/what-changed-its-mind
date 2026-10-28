export type Observation = {
  id: string;
  kind: string;
  candidateId: string | null;
  excerpt: string | null;
  value: Record<string, unknown>;
  sourceId: string;
  acquisitionId?: string;
  contentHash?: string;
  retrievedAt?: string;
  locator: string;
  publishedAt: string | null;
  availableAt: string;
  recordType: string;
};
export type Forecast = {
  id: string;
  arm: string;
  ordering: string;
  status: string;
  probabilities: Record<string, number> | null;
  selected: string | null;
  error: string | null;
  requestHash: string;
  responseHash?: string | null;
  requestedModel?: string;
  returnedModel?: string | null;
  usage?: Record<string, unknown>;
  startedAt: string;
  completedAt: string;
  request: unknown;
  response: unknown;
  observationIds: string[];
  omittedObservationIds: string[];
};
export type Race = {
  id: string;
  name: string;
  office: "house" | "senate";
  state: string;
  stateFips: string;
  district: string | null;
  rating: string | null;
  selected: boolean;
  selectionReason: string;
  geographyVerified: boolean;
  rosterVerified: boolean;
  candidates: Array<{
    id: string;
    name: string;
    party: string;
    incumbent: boolean | null;
  }>;
  coverage: Record<string, number>;
  missing: string[];
  observations: Observation[];
  forecasts: Forecast[];
  outcome: null | { status: string; winnerId: string | null };
};
export type Source = {
  id: string;
  title: string;
  url: string;
  publisher: string;
  kind: string;
  attribution: string;
  rightsBasis: string;
  redistribution: string;
  notes: string;
};
export type Acquisition = {
  id: string;
  sourceId: string;
  retrievedAt: string;
  rawHash: string;
  mediaType: string;
  parserVersion: string;
  httpStatus: number;
  finalUrl: string;
};
export type Bundle = {
  schemaVersion: "1.0";
  title: string;
  status: "collecting" | "ready";
  generatedAt: string;
  model: string;
  snapshot: null | { id: string; cutoff: string };
  protocol: {
    finalCutoff: string;
    targetRaces: number;
    primaryComparison: string;
  };
  stats: {
    races: number;
    selected: number;
    sources: number;
    forecasts: number;
    focusGroups: number;
  };
  races: Race[];
  sources: Source[];
  acquisitions?: Acquisition[];
  diagnostics: Array<Record<string, unknown>>;
  evaluation: null | Record<string, unknown>;
  limitations: string[];
};
export const ARMS = [
  {
    id: "A",
    title: "The numbers",
    short: "Fundamentals",
    description:
      "Start with the structural evidence: the race, candidates, and available fundamentals.",
    color: "#008FD5",
  },
  {
    id: "B",
    title: "Add the polls",
    short: "+ Polls",
    description:
      "Keep those fundamentals. Add polling evidence that was available before the cutoff.",
    color: "#FC4F30",
  },
  {
    id: "C",
    title: "Add their words",
    short: "+ Qualitative",
    description:
      "Start from fundamentals and add approved candidate statements, independent local reporting and eligible focus-group evidence. No polls in this arm.",
    color: "#E5AE38",
  },
  {
    id: "D",
    title: "Add the context",
    short: "+ Both",
    description:
      "Combine fundamentals and polls with the same qualitative bundle used in C. Compare D with B to isolate that bundle’s contribution.",
    color: "#6D904F",
  },
] as const;
export function findForecast(
  race: Race | undefined,
  arm: string,
  ordering: string,
) {
  return race?.forecasts.find((f) => f.arm === arm && f.ordering === ordering);
}
export function safeUrl(raw: string) {
  try {
    const u = new URL(raw);
    return ["https:", "http:"].includes(u.protocol) ? u.href : null;
  } catch {
    return null;
  }
}
export function formatDate(raw: string | null | undefined) {
  if (!raw) return "Not recorded";
  const d = new Date(raw);
  return isNaN(d.getTime())
    ? "Not recorded"
    : new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      }).format(d);
}

export function validWeight(
  forecast: Forecast | undefined,
  candidateId: string,
): number | null {
  if (forecast?.status !== "ok") return null;
  const value = forecast.probabilities?.[candidateId];
  return typeof value === "number" &&
    Number.isFinite(value) &&
    value >= 0 &&
    value <= 1
    ? value
    : null;
}
export function signatureValues(race: Race | undefined, candidateId: string) {
  const b = validWeight(findForecast(race, "B", "canonical"), candidateId);
  const d = validWeight(findForecast(race, "D", "canonical"), candidateId);
  const values = ["canonical", "reverse_candidates", "reverse_evidence"]
    .map((order) => validWeight(findForecast(race, "D", order), candidateId))
    .filter((v): v is number => v !== null);
  return {
    b,
    d,
    low: values.length >= 2 ? Math.min(...values) : null,
    high: values.length >= 2 ? Math.max(...values) : null,
    count: values.length,
  };
}

export function exactTimestamp(raw: string | null | undefined) {
  if (!raw) return "Not recorded";
  const value = new Date(raw);
  return Number.isNaN(value.getTime())
    ? "Not recorded"
    : value.toISOString().replace("T", " ").replace(".000Z", " UTC");
}
export function candidateOptions(race: Race | undefined) {
  if (!race) return [];
  return [
    ...race.candidates,
    {
      id: "OTHER_WINNER",
      name: "Other / unlisted winner",
      party: "Residual option",
      incumbent: null,
    },
  ];
}
export function storedChoiceOrder(forecast: Forecast | undefined): string[] {
  const request = forecast?.request as {
    questions?: { winner?: { criteria?: unknown } };
  } | null;
  const criteria = request?.questions?.winner?.criteria;
  return criteria && typeof criteria === "object" && !Array.isArray(criteria)
    ? Object.keys(criteria)
    : [];
}

export type SnapshotEntry = { id: string; cutoff: string; url: string };
export function snapshotPath(id: string, catalog: SnapshotEntry[]): string {
  if (!id) return "data/experiment.json";
  const entry = catalog.find((item) => item.id === id);
  if (!entry || !/^data\/snapshots\/[A-Za-z0-9_-]+\.json$/.test(entry.url))
    throw new Error(
      "That snapshot is not in the published archive. Choose the current dataset to continue.",
    );
  return entry.url;
}
