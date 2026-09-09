import { describe, expect, it } from "vitest";
import { classifyPriceChange } from "@/components/price-change";

describe("classifyPriceChange", () => {
  it("returns unknown when a price is missing (null/missing price)", () => {
    expect(classifyPriceChange(null, 10)).toEqual({ kind: "unknown", pct: null });
    expect(classifyPriceChange(10, null)).toEqual({ kind: "unknown", pct: null });
    expect(classifyPriceChange(undefined, undefined)).toEqual({ kind: "unknown", pct: null });
  });

  it("returns flat for no real change", () => {
    expect(classifyPriceChange(10, 10)).toEqual({ kind: "flat", pct: null });
  });

  it("returns down with a percentage for a price decrease", () => {
    expect(classifyPriceChange(45, 50).kind).toBe("down");
    expect(classifyPriceChange(45, 50).pct).toBe(-10);
  });

  it("returns up with a percentage for a price increase", () => {
    expect(classifyPriceChange(55, 50).kind).toBe("up");
    expect(classifyPriceChange(55, 50).pct).toBe(10);
  });

  it("never fabricates a pct from a zero base", () => {
    expect(classifyPriceChange(5, 0).kind).toBe("up");
    expect(classifyPriceChange(5, 0).pct).toBeNull();
  });
});