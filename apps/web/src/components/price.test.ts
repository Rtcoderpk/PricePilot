import { describe, expect, it } from "vitest";
import { formatPrice } from "@/components/price";

describe("formatPrice", () => {
  it("formats USD", () => {
    expect(formatPrice(1234.5, "USD")).toBe("$1,234.50");
  });

  it("returns em dash for null/undefined", () => {
    expect(formatPrice(null)).toBe("—");
    expect(formatPrice(undefined)).toBe("—");
  });

  it("handles arbitrary 3-letter currency codes via Intl", () => {
    // Intl formats any 3-letter code; cursor/format may vary, we check it contains code.
    expect(formatPrice(10, "ZZZ")).toContain("ZZZ");
  });
});