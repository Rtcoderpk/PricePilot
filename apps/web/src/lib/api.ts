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

export async function getHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  return parseResponse<{ status: string }>(res);
}

export function apiBaseUrl(): string {
  return API_BASE;
}