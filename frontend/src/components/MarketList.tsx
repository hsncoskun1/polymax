import { useEffect, useState } from "react";
import { fetchMarkets, type Market } from "../lib/api";

function SideBadge({ side }: { side: Market["side"] }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        side === "up"
          ? "bg-green-500/15 text-green-400"
          : "bg-red-500/15 text-red-400"
      }`}
    >
      {side === "up" ? "▲ UP" : "▼ DOWN"}
    </span>
  );
}

function StatusDot({ status }: { status: Market["status"] }) {
  const colors: Record<Market["status"], string> = {
    active: "bg-green-400",
    inactive: "bg-yellow-400",
    closed: "bg-gray-500",
    archived: "bg-gray-700",
  };
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-[var(--color-text-muted)]">
      <span className={`w-1.5 h-1.5 rounded-full ${colors[status]}`} />
      {status}
    </span>
  );
}

function MarketRow({ market }: { market: Market }) {
  return (
    <div className="flex items-center justify-between px-4 py-3 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-accent)]/30 transition-colors">
      <div className="flex items-center gap-4">
        <span className="font-mono text-xs text-[var(--color-text-muted)]">
          {market.id}
        </span>
        <span className="font-semibold text-sm text-[var(--color-text)]">
          {market.symbol}
        </span>
        <span className="text-xs text-[var(--color-text-muted)]">
          {market.timeframe}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <SideBadge side={market.side} />
        <StatusDot status={market.status} />
      </div>
    </div>
  );
}

export default function MarketList() {
  const [markets, setMarkets] = useState<Market[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMarkets()
      .then(setMarkets)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Failed to load markets")
      );
  }, []);

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400"
      >
        {error}
      </div>
    );
  }

  if (markets === null) {
    return (
      <div
        role="status"
        aria-label="Loading markets"
        className="text-sm text-[var(--color-text-muted)] animate-pulse"
      >
        Loading markets...
      </div>
    );
  }

  if (markets.length === 0) {
    return (
      <div className="text-sm text-[var(--color-text-muted)]">
        No markets available.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {markets.map((m) => (
        <MarketRow key={m.id} market={m} />
      ))}
    </div>
  );
}
