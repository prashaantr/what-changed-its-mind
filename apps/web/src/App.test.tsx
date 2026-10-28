// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./main";
import fixture from "../data/fixture.json";
const geometry = {
  type: "Topology",
  objects: { states: { type: "GeometryCollection", geometries: [] } },
  arcs: [],
};
beforeEach(() => {
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(url.includes("/geo/") ? geometry : fixture),
      }),
    ),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("public research interactions", () => {
  it("shows recorded fixture evidence, never substitutes output for an absent variant, and restores receipt focus", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("button", { name: /Fictional example contest/ });
    expect(screen.getByText("60.0%")).toBeTruthy();
    await user.click(
      screen.getByRole("button", { name: "Reverse candidate order" }),
    );
    expect(screen.getByText("Forecast pending.")).toBeTruthy();
    expect(screen.queryByText("60.0%")).toBeNull();
    const source = screen.getByRole("button", {
      name: /Fictional fixture source/,
    });
    await user.click(source);
    expect(screen.getByRole("dialog").getAttribute("aria-modal")).toBe("true");
    expect(document.activeElement?.getAttribute("aria-label")).toBe(
      "Close evidence receipt",
    );
    expect(document.querySelector("main")?.inert).toBe(true);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(source);
    expect(document.querySelector("main")?.inert).toBe(false);
  });
  it("uses an honest load failure instead of synthetic production fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: false })),
    );
    render(<App />);
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "No substitute forecasts",
      ),
    );
    expect(screen.queryByText("Fictional example contest")).toBeNull();
  });
});

it("rejects an unknown snapshot query without fetching it as a URL", async () => {
  window.history.replaceState(
    null,
    "",
    "?snapshot=https%3A%2F%2Fevil.example%2Fdata.json",
  );
  const fetcher = vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ snapshots: [] }),
    }),
  );
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  await screen.findByRole("alert");
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0]).toEqual(["/data/snapshots.json"]);
  expect(
    screen.getByRole("button", { name: "Use current dataset" }),
  ).toBeTruthy();
  window.history.replaceState(null, "", "/");
});
