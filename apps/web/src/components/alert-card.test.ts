import { describe, expect, it } from "vitest";
import { alertKindLabel, alertKindVariant } from "@/components/alert-card";

describe("alertKind", () => {
  it("maps real alert kinds to readable labels", () => {
    expect(alertKindLabel("back_in_stock")).toBe("back in stock");
    expect(alertKindLabel("target_price")).toBe("target reached");
    expect(alertKindLabel("percent_drop")).toBe("price drop");
    expect(alertKindLabel("new_low")).toBe("new low");
  });

  it("falls back to a readable string for unknown kinds", () => {
    expect(alertKindLabel("availability_change")).toBe("availability change");
  });

  it("assigns tones per kind", () => {
    expect(alertKindVariant("back_in_stock")).toBe("success");
    expect(alertKindVariant("target_price")).toBe("info");
    expect(alertKindVariant("new_low")).toBe("info");
    expect(alertKindVariant("percent_drop")).toBe("secondary");
  });
});