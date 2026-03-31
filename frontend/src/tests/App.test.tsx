import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";
import type { Market } from "../lib/api";

// ── fetch mock setup ──────────────────────────────────────────────────────────

const MOCK_MARKETS: Market[] = [
  {
    id: "mkt-btc-up",
    event_id: "evt-001",
    symbol: "BTC",
    timeframe: "5m",
    side: "up",
    status: "active",
    source_timestamp: null,
    created_at: "2026-04-01T00:00:00Z",
    updated_at: "2026-04-01T00:00:00Z",
  },
];

function mockFetch(data: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status: ok ? 200 : 500,
      json: () => Promise.resolve(data),
    })
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

function renderWithRouter(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>
  );
}

// ── routing tests ─────────────────────────────────────────────────────────────

describe("App routing", () => {
  it("renders POLYMAX header", () => {
    mockFetch([]);
    renderWithRouter("/user");
    expect(screen.getByText("POLYMAX")).toBeDefined();
  });

  it("renders User Panel on /user", () => {
    mockFetch([]);
    renderWithRouter("/user");
    expect(screen.getByText("User Panel")).toBeDefined();
  });

  it("renders Admin Panel on /admin", () => {
    mockFetch([]);
    renderWithRouter("/admin");
    expect(screen.getByText("Admin Panel")).toBeDefined();
  });

  it("redirects unknown routes to /user", () => {
    mockFetch([]);
    renderWithRouter("/unknown");
    expect(screen.getByText("User Panel")).toBeDefined();
  });

  it("shows nav tabs for User and Admin", () => {
    mockFetch([]);
    renderWithRouter("/user");
    expect(screen.getByText("User")).toBeDefined();
    expect(screen.getByText("Admin")).toBeDefined();
  });
});

// ── market list tests ─────────────────────────────────────────────────────────

describe("MarketList", () => {
  it("shows loading state initially", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {}))); // never resolves
    renderWithRouter("/user");
    expect(screen.getByRole("status", { name: /loading markets/i })).toBeDefined();
  });

  it("renders markets after successful fetch", async () => {
    mockFetch(MOCK_MARKETS);
    renderWithRouter("/user");
    await waitFor(() => {
      expect(screen.getByText("BTC")).toBeDefined();
    });
    expect(screen.getByText("mkt-btc-up")).toBeDefined();
  });

  it("shows empty state when no markets returned", async () => {
    mockFetch([]);
    renderWithRouter("/user");
    await waitFor(() => {
      expect(screen.getByText("No markets available.")).toBeDefined();
    });
  });

  it("shows error state on fetch failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Backend error: 500"))
    );
    renderWithRouter("/user");
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeDefined();
    });
  });
});
