// Backend base URL — single source of truth for all API calls.
// Override with VITE_BACKEND_URL env var for non-local deployments.
export const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL ?? "http://127.0.0.1:8000";
