import { BACKEND_URL } from "./config";

const BASE_URL = BACKEND_URL;

export type MarketStatus = "active" | "inactive" | "closed" | "archived";
export type Side = "up" | "down";

export interface Market {
  id: string;
  event_id: string;
  symbol: string;
  timeframe: string;
  side: Side;
  status: MarketStatus;
  source_timestamp: string | null;
  end_date: string | null;
  created_at: string;
  updated_at: string;
}

export async function fetchMarkets(): Promise<Market[]> {
  const resp = await fetch(`${BASE_URL}/api/v1/markets`);
  if (!resp.ok) throw new Error(`Backend error: ${resp.status}`);
  return resp.json();
}

export interface SyncResult {
  fetched_count: number;
  mapped_count: number;
  written_count: number;
  skipped_mapping_count: number;
  skipped_duplicate_count: number;
  registry_total_count: number;
}

export async function triggerSync(): Promise<SyncResult> {
  const resp = await fetch(`${BASE_URL}/api/v1/markets/sync`, { method: "POST" });
  if (!resp.ok) throw new Error(`Sync failed: ${resp.status}`);
  return resp.json();
}

export interface DiscoverResult {
  fetched_count: number;
  candidate_count: number;
  rejected_count: number;
  rejection_breakdown: Record<string, number>;
}

export async function triggerDiscover(): Promise<DiscoverResult> {
  const resp = await fetch(`${BASE_URL}/api/v1/markets/discover`, { method: "POST" });
  if (!resp.ok) throw new Error(`Discover failed: ${resp.status}`);
  return resp.json();
}
