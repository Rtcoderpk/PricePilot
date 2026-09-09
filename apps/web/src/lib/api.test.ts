import { afterEach, describe, expect, it, vi } from "vitest";
import {
  trackingList,
  trackingCreate,
  trackingUpdate,
  trackingDelete,
  alertsList,
  alertMark,
  preferencesGet,
  preferencesUpdate,
  priceHistory,
} from "@/lib/api";

function mockFetchOnce(status: number, body: unknown) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("monitoring API client request shaping", () => {
  it("trackingList attaches X-User-Id (deferred auth)", async () => {
    mockFetchOnce(200, []);
    await trackingList();
    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((init.headers as Record<string, string>)["X-User-Id"]).toBeTruthy();
  });

  it("trackingCreate posts JSON with product id + target", async () => {
    mockFetchOnce(201, { status: "created", id: "wl-1" });
    await trackingCreate({ product_id: "pp_gtin_x", target_price: 30 });
    const [url, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/v1/tracking");
    expect(JSON.parse(init.body as string)).toEqual({ product_id: "pp_gtin_x", target_price: 30 });
  });

  it("trackingUpdate patches paused", async () => {
    mockFetchOnce(200, { id: "wl-1", paused: true });
    await trackingUpdate("wl-1", { paused: true });
    const [url, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/v1/tracking/wl-1");
    expect((init as RequestInit).method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ paused: true });
  });

  it("trackingDelete uses DELETE", async () => {
    mockFetchOnce(204, null);
    await trackingDelete("wl-1");
    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect((init as RequestInit).method).toBe("DELETE");
  });

  it("alertsList sends the unread flag", async () => {
    mockFetchOnce(200, []);
    await alertsList(true);
    const [url] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("unread=true");
  });

  it("alertMark patches status read", async () => {
    mockFetchOnce(200, { status: "ok" });
    await alertMark("n-1", "read");
    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(JSON.parse(init.body as string)).toEqual({ status: "read" });
  });

  it("preferencesUpdate PUTs partial fields", async () => {
    mockFetchOnce(200, { preferences: { preferred_brands: ["Acme"] } });
    await preferencesUpdate({ preferred_brands: ["Acme"] });
    const [url, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/v1/preferences");
    expect((init as RequestInit).method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ preferred_brands: ["Acme"] });
  });

  it("priceHistory encodes the product id in the path", async () => {
    mockFetchOnce(200, { product_id: "pp/gtin/x", observations: [], analytics: { status: "insufficient_history" } });
    await priceHistory("pp/gtin/x");
    const [url] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain(encodeURIComponent("pp/gtin/x"));
  });
});

describe("real-data state handling", () => {
  it("preferencesGet returns null when unset (honest empty)", async () => {
    mockFetchOnce(200, { preferences: null });
    const res = await preferencesGet();
    expect(res.preferences).toBeNull();
  });

  it("priceHistory surfaces insufficient_history rather than fabricating analytics", async () => {
    mockFetchOnce(200, {
      product_id: "x",
      observations: [],
      analytics: { status: "insufficient_history", observation_count: 0 },
      currency: "USD",
    });
    const res = await priceHistory("x");
    expect(res.analytics.status).toBe("insufficient_history");
    expect(res.observations).toHaveLength(0);
  });
});