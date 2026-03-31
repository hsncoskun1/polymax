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
  created_at: string;
  updated_at: string;
}

export async function fetchMarkets(): Promise<Market[]> {
  const resp = await fetch(`${BASE_URL}/api/v1/markets`);
  if (!resp.ok) throw new Error(`Backend error: ${resp.status}`);
  return resp.json();
}
