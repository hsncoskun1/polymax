import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";
import DiscoverAction from "../components/DiscoverAction";
import SyncAction from "../components/SyncAction";
import UserPanel from "../pages/UserPanel";
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
    end_date: null,
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

// ── sync action tests ─────────────────────────────────────────────────────────

const MOCK_SYNC_RESULT = {
  fetched_count: 4,
  mapped_count: 4,
  written_count: 4,
  skipped_mapping_count: 0,
  skipped_duplicate_count: 0,
  registry_total_count: 4,
  rejected_count: 0,
  rejection_breakdown: {},
};

describe("SyncAction", () => {
  it("renders Sync now button on admin panel", () => {
    mockFetch([]);
    renderWithRouter("/admin");
    expect(screen.getByRole("button", { name: /sync now/i })).toBeDefined();
  });

  it("shows loading state while sync is in progress", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {}))); // never resolves
    renderWithRouter("/admin");
    fireEvent.click(screen.getByRole("button", { name: /sync now/i }));
    expect(screen.getByRole("status", { name: /sync in progress/i })).toBeDefined();
  });

  it("renders sync summary on successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(MOCK_SYNC_RESULT),
      })
    );
    renderWithRouter("/admin");
    fireEvent.click(screen.getByRole("button", { name: /sync now/i }));
    await waitFor(() => {
      expect(screen.getByRole("region", { name: /sync result/i })).toBeDefined();
    });
    expect(screen.getByText("Written")).toBeDefined();
    expect(screen.getByText("Fetched")).toBeDefined();
  });

  it("shows error message when sync request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Sync failed: 502"))
    );
    renderWithRouter("/admin");
    fireEvent.click(screen.getByRole("button", { name: /sync now/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeDefined();
    });
    expect(screen.getByText(/sync failed/i)).toBeDefined();
  });
});

// ── sync → refresh flow tests ─────────────────────────────────────────────────

describe("SyncAction onSuccess callback", () => {
  it("calls onSuccess after successful sync", async () => {
    const onSuccess = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(MOCK_SYNC_RESULT),
      })
    );
    render(
      <MemoryRouter>
        <SyncAction onSuccess={onSuccess} />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole("button", { name: /sync now/i }));
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledTimes(1);
    });
  });

  it("does not call onSuccess when sync fails", async () => {
    const onSuccess = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Sync failed: 502"))
    );
    render(
      <MemoryRouter>
        <SyncAction onSuccess={onSuccess} />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole("button", { name: /sync now/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeDefined();
    });
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("re-fetches market list when UserPanel receives a new refreshKey", async () => {
    let marketsGetCount = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => {
        marketsGetCount++;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve([]),
        });
      })
    );

    // Mount UserPanel with refreshKey=0 — MarketList mounts → fetches once
    const { rerender } = render(
      <MemoryRouter>
        <UserPanel refreshKey={0} />
      </MemoryRouter>
    );
    await waitFor(() => expect(marketsGetCount).toBe(1));

    // Simulate sync completing: refreshKey increments → MarketList re-keyed → fetches again
    rerender(
      <MemoryRouter>
        <UserPanel refreshKey={1} />
      </MemoryRouter>
    );
    await waitFor(() => expect(marketsGetCount).toBe(2));
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

// ── discover action tests ──────────────────────────────────────────────────────

const MOCK_DISCOVER_RESULT = {
  fetched_count: 10,
  candidate_count: 3,
  rejected_count: 7,
  rejection_breakdown: {
    inactive: 2,
    missing_dates: 3,
    duration_out_of_range: 2,
  },
};

describe("DiscoverAction", () => {
  it("renders Discover now button on admin panel", () => {
    mockFetch([]);
    renderWithRouter("/admin");
    expect(screen.getByRole("button", { name: /discover now/i })).toBeDefined();
  });

  it("shows loading state while discovery is in progress", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {}))); // never resolves
    renderWithRouter("/admin");
    fireEvent.click(screen.getByRole("button", { name: /discover now/i }));
    expect(screen.getByRole("status", { name: /discovery in progress/i })).toBeDefined();
  });

  it("renders discovery summary on successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(MOCK_DISCOVER_RESULT),
      })
    );
    renderWithRouter("/admin");
    fireEvent.click(screen.getByRole("button", { name: /discover now/i }));
    await waitFor(() => {
      expect(screen.getByRole("region", { name: /discovery result/i })).toBeDefined();
    });
    expect(screen.getByText("Fetched")).toBeDefined();
    expect(screen.getByText("Candidates")).toBeDefined();
    expect(screen.getByText("Rejected")).toBeDefined();
  });

  it("renders rejection breakdown on successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve(MOCK_DISCOVER_RESULT),
      })
    );
    render(
      <MemoryRouter>
        <DiscoverAction />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole("button", { name: /discover now/i }));
    await waitFor(() => {
      expect(screen.getByText("Rejection breakdown")).toBeDefined();
    });
    expect(screen.getByText("Inactive / closed")).toBeDefined();
    expect(screen.getByText("Missing dates")).toBeDefined();
    expect(screen.getByText("Duration out of range")).toBeDefined();
  });

  it("shows error message when discover request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Discover failed: 502"))
    );
    renderWithRouter("/admin");
    fireEvent.click(screen.getByRole("button", { name: /discover now/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeDefined();
    });
    expect(screen.getByText(/discover failed/i)).toBeDefined();
  });
});
