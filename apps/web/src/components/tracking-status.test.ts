import { describe, expect, it } from "vitest";
import { trackingStateLabel } from "@/components/tracking-status";

describe("trackingStateLabel", () => {
  it("reports paused before anything else", () => {
    expect(trackingStateLabel({ paused: true, movement: "down", observationCount: 3 })).toBe("paused");
  });

  it("reports monitoring disabled", () => {
    expect(
      trackingStateLabel({ paused: false, monitoringEnabled: false, providerAvailable: true, observationCount: 3 }),
    ).toBe("monitoring disabled");
  });

  it("reports provider unavailable honestly", () => {
    expect(
      trackingStateLabel({ paused: false, monitoringEnabled: true, providerAvailable: false, observationCount: 3 }),
    ).toBe("provider unavailable");
  });

  it("reports waiting for data with zero observations", () => {
    expect(
      trackingStateLabel({ paused: false, monitoringEnabled: true, providerAvailable: true, observationCount: 0 }),
    ).toBe("waiting for data");
  });

  it("reports price movement when data exists", () => {
    const base = { paused: false, monitoringEnabled: true, providerAvailable: true, observationCount: 2 };
    expect(trackingStateLabel({ ...base, movement: "down" })).toBe("price down");
    expect(trackingStateLabel({ ...base, movement: "up" })).toBe("price up");
    expect(trackingStateLabel({ ...base, movement: "flat" })).toBe("steady");
    expect(trackingStateLabel({ ...base, movement: "unknown" })).toBe("monitoring");
  });
});