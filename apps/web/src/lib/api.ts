import type { SearchResponse, ErrorEnvelope, ShoppingAgentResponse } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Base URL for the PricePilot API, overridable by env. */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function parseResponse<T>(res: Response): Promise<T> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const err = (body as ErrorEnvelope | null)?.error;
    if (err) {
      throw new ApiError(res.status, err.code, err.message, err.details);
    }
    throw new ApiError(res.status, "unknown", `Request failed with status ${res.status}`);
  }

  return body as T;
}

export async function searchProducts(
  query: string,
  maxResults = 20,
): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/api/v1/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, max_results: maxResults }),
    cache: "no-store",
  });
  return parseResponse<SearchResponse>(res);
}

export async function shoppingSearch(query: string): Promise<ShoppingAgentResponse> {
  const res = await fetch(`${API_BASE}/api/v1/shopping/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, use_llm: true }),
    cache: "no-store",
  });
  return parseResponse<ShoppingAgentResponse>(res);
}

export async function shoppingChat(
  query: string,
  sessionId?: string,
): Promise<ShoppingAgentResponse> {
  const res = await authFetch("/api/v1/shopping/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, session_id: sessionId }),
  });
  return parseResponse<ShoppingAgentResponse>(res);
}

export async function shoppingImage(
  file: File,
  maxMatches = 3,
): Promise<ShoppingAgentResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("max_matches", String(maxMatches));
  const res = await fetch(`${API_BASE}/api/v1/shopping/image`, {
    method: "POST",
    body: form,
    cache: "no-store",
  });
  return parseResponse<ShoppingAgentResponse>(res);
}

export async function getHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  return parseResponse<{ status: string }>(res);
}

export function apiBaseUrl(): string {
  return API_BASE;
}

// ---- Phase 5: price monitoring ----

const USER_ID_HEADER = "X-User-Id";
// Local demo identity until real auth lands: a valid UUID, because the
// monitoring schema keeps UUID FKs to `users.id` and the identity resolver
// idempotently creates the user row on first request.
const DEFAULT_USER = "11111111-1111-4111-8111-111111111111";

async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
      [USER_ID_HEADER]: DEFAULT_USER,
    },
    cache: "no-store",
  });
}

export type TrackingItem = {
  id: string;
  product_id: string;
  name: string;
  target_price?: number | null;
  target_currency?: string | null;
  alert_preferences?: Record<string, boolean>;
  paused: boolean;
  last_monitor_status?: string | null;
  last_observed_at?: string | null;
  current_price?: number | null;
  previous_price?: number | null;
  percentage_change?: number | null;
  movement?: "up" | "down" | "flat" | "unknown" | null;
  observation_count?: number;
};

export type HistoryObservation = {
  amount: number;
  currency: string;
  observed_at: string;
  source?: string | null;
};

export type PriceAnalytics = {
  status: string;
  current_price?: number | null;
  previous_price?: number | null;
  absolute_change?: number | null;
  percentage_change?: number | null;
  lowest_observed?: number | null;
  highest_observed?: number | null;
  average_observed?: number | null;
  observation_count: number;
  first_observed?: string | null;
  last_observed?: string | null;
  trend?: string | null;
};

export type AlertItem = {
  id: string;
  title: string;
  body: string;
  status: string;
  created_at?: string | null;
  product_id?: string | null;
  target_amount?: number | null;
  percent_threshold?: number | null;
  triggering_offer?: {
    event_type?: string;
    current_price?: number | null;
    previous_price?: number | null;
    source?: string | null;
    currency?: string | null;
  } | null;
  kind: string;
};

export async function monitoringStatus(): Promise<{
  enabled: boolean;
  provider: string;
  interval_seconds: number;
  tracked_products: number;
  message?: string | null;
}> {
  const res = await fetch(`${API_BASE}/api/v1/monitoring/status`, { cache: "no-store" });
  return parseResponse(res);
}

export async function priceHistory(productId: string): Promise<{
  product_id: string;
  observations: HistoryObservation[];
  analytics: PriceAnalytics;
  currency?: string | null;
}> {
  const res = await authFetch(`/api/v1/price-history/${encodeURIComponent(productId)}`);
  return parseResponse(res);
}

export async function trackingList(): Promise<TrackingItem[]> {
  const res = await authFetch("/api/v1/tracking");
  return parseResponse(res);
}

export async function trackingCreate(body: {
  product_id: string;
  target_price?: number | null;
  alert_preferences?: Record<string, boolean>;
}): Promise<{ status: string; id: string }> {
  const res = await authFetch("/api/v1/tracking", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse(res);
}

export async function trackingUpdate(
  id: string,
  body: { target_price?: number | null; paused?: boolean; alert_preferences?: Record<string, boolean> },
): Promise<TrackingItem> {
  const res = await authFetch(`/api/v1/tracking/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse(res);
}

export async function trackingDelete(id: string): Promise<void> {
  await authFetch(`/api/v1/tracking/${id}`, { method: "DELETE" });
}

export async function alertsList(onlyUnread = false): Promise<AlertItem[]> {
  const res = await authFetch(`/api/v1/alerts?unread=${onlyUnread}`);
  return parseResponse(res);
}

export async function alertMark(id: string, status: "read" | "dismissed"): Promise<void> {
  await authFetch(`/api/v1/alerts/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export type UserPreferences = {
  preferred_brands?: string[];
  max_budget?: number | null;
  min_specs?: Record<string, unknown>;
  preferred_stores?: string[];
  preferred_condition?: string[];
  price_vs_quality?: number | null;
  currency_code?: string | null;
  shopping_locale?: string | null;
  updated_at?: string | null;
};

export async function preferencesGet(): Promise<{ preferences: UserPreferences | null }> {
  const res = await authFetch("/api/v1/preferences");
  return parseResponse(res);
}

export async function preferencesUpdate(
  fields: Partial<UserPreferences>,
): Promise<{ preferences: UserPreferences }> {
  const res = await authFetch("/api/v1/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(fields),
  });
  return parseResponse(res);
}
