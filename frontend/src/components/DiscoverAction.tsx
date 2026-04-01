import { useState } from "react";
import { triggerDiscover, type DiscoverResult } from "../lib/api";

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; result: DiscoverResult }
  | { status: "error"; message: string };

export default function DiscoverAction() {
  const [state, setState] = useState<State>({ status: "idle" });

  async function handleDiscover() {
    setState({ status: "loading" });
    try {
      const result = await triggerDiscover();
      setState({ status: "success", result });
    } catch (err) {
      setState({
        status: "error",
        message: err instanceof Error ? err.message : "Discover failed",
      });
    }
  }

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-[var(--color-text)]">
            Market Discovery
          </h3>
          <p className="text-sm text-[var(--color-text-muted)] mt-0.5">
            Fetch markets from Polymarket and evaluate how many pass candidate
            selection rules. Does not write to the registry.
          </p>
        </div>
        <button
          onClick={handleDiscover}
          disabled={state.status === "loading"}
          aria-label={state.status === "loading" ? "Discovering" : "Discover now"}
          className="shrink-0 rounded-md px-4 py-2 text-sm font-medium transition-colors
            bg-[var(--color-accent)] text-[var(--color-bg)]
            hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {state.status === "loading" ? "Discovering…" : "Discover now"}
        </button>
      </div>

      {state.status === "loading" && (
        <div
          role="status"
          aria-label="Discovery in progress"
          className="text-sm text-[var(--color-text-muted)] animate-pulse"
        >
          Discovering…
        </div>
      )}

      {state.status === "error" && (
        <div
          role="alert"
          className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400"
        >
          {state.message}
        </div>
      )}

      {state.status === "success" && (
        <DiscoverSummary result={state.result} />
      )}
    </div>
  );
}

const BREAKDOWN_LABELS: Record<string, string> = {
  inactive: "Inactive / closed",
  no_order_book: "No order book",
  empty_tokens: "Empty tokens",
  missing_dates: "Missing dates",
  duration_out_of_range: "Duration out of range",
};

function DiscoverSummary({ result }: { result: DiscoverResult }) {
  const topRows: [string, number][] = [
    ["Fetched", result.fetched_count],
    ["Candidates", result.candidate_count],
    ["Rejected", result.rejected_count],
  ];

  const breakdownEntries = Object.entries(result.rejection_breakdown);

  return (
    <div
      role="region"
      aria-label="Discovery result"
      className="space-y-3"
    >
      <div className="rounded-md border border-[var(--color-border)] divide-y divide-[var(--color-border)]">
        {topRows.map(([label, value]) => (
          <div
            key={label}
            className="flex items-center justify-between px-4 py-2 text-sm"
          >
            <span className="text-[var(--color-text-muted)]">{label}</span>
            <span className="font-mono font-medium text-[var(--color-text)]">
              {value}
            </span>
          </div>
        ))}
      </div>

      {breakdownEntries.length > 0 && (
        <div>
          <p className="text-xs text-[var(--color-text-muted)] px-1 mb-1">
            Rejection breakdown
          </p>
          <div className="rounded-md border border-[var(--color-border)] divide-y divide-[var(--color-border)]">
            {breakdownEntries.map(([key, count]) => (
              <div
                key={key}
                className="flex items-center justify-between px-4 py-2 text-sm"
              >
                <span className="text-[var(--color-text-muted)]">
                  {BREAKDOWN_LABELS[key] ?? key}
                </span>
                <span className="font-mono font-medium text-[var(--color-text)]">
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
