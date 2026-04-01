import { useState } from "react";
import { triggerSync, type SyncResult } from "../lib/api";

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; result: SyncResult }
  | { status: "error"; message: string };

interface SyncActionProps {
  onSuccess?: () => void;
}

export default function SyncAction({ onSuccess }: SyncActionProps) {
  const [state, setState] = useState<State>({ status: "idle" });

  async function handleSync() {
    setState({ status: "loading" });
    try {
      const result = await triggerSync();
      setState({ status: "success", result });
      onSuccess?.();
    } catch (err) {
      setState({
        status: "error",
        message: err instanceof Error ? err.message : "Sync failed",
      });
    }
  }

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-[var(--color-text)]">
            Market Sync
          </h3>
          <p className="text-sm text-[var(--color-text-muted)] mt-0.5">
            Fetch active candidates from Polymarket and write new entries to the
            registry.
          </p>
        </div>
        <button
          onClick={handleSync}
          disabled={state.status === "loading"}
          aria-label={state.status === "loading" ? "Syncing" : "Sync now"}
          className="shrink-0 rounded-md px-4 py-2 text-sm font-medium transition-colors
            bg-[var(--color-accent)] text-[var(--color-bg)]
            hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {state.status === "loading" ? "Syncing…" : "Sync now"}
        </button>
      </div>

      {state.status === "loading" && (
        <div
          role="status"
          aria-label="Sync in progress"
          className="text-sm text-[var(--color-text-muted)] animate-pulse"
        >
          Syncing…
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
        <SyncSummary result={state.result} />
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

function SyncSummary({ result }: { result: SyncResult }) {
  const rows: [string, number][] = [
    ["Fetched", result.fetched_count],
    ["Mapped", result.mapped_count],
    ["Written", result.written_count],
    ["Skipped (mapping)", result.skipped_mapping_count],
    ["Skipped (duplicate)", result.skipped_duplicate_count],
    ["Registry total", result.registry_total_count],
    ["Rejected", result.rejected_count],
  ];

  const breakdownEntries = Object.entries(result.rejection_breakdown);

  return (
    <div
      role="region"
      aria-label="Sync result"
      className="space-y-3"
    >
      <div className="rounded-md border border-[var(--color-border)] divide-y divide-[var(--color-border)]">
        {rows.map(([label, value]) => (
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
