import { Badge } from "@/components/ui/badge";

/** Pure derivation of the honest monitoring state label. Unit-testable. */
export type TrackingStateLabel =
  | "paused"
  | "monitoring disabled"
  | "provider unavailable"
  | "waiting for data"
  | "price down"
  | "price up"
  | "steady"
  | "monitoring";

export function trackingStateLabel({
  paused,
  movement,
  observationCount,
  monitoringEnabled,
  providerAvailable,
}: {
  paused: boolean;
  movement?: "up" | "down" | "flat" | "unknown" | null;
  observationCount?: number;
  monitoringEnabled?: boolean;
  providerAvailable?: boolean;
}): TrackingStateLabel {
  if (paused) return "paused";
  if (monitoringEnabled === false) return "monitoring disabled";
  if (providerAvailable === false) return "provider unavailable";
  if (!observationCount || observationCount < 1) return "waiting for data";
  if (movement === "down") return "price down";
  if (movement === "up") return "price up";
  if (movement === "flat") return "steady";
  return "monitoring";
}

/** Honest per-tracking monitoring state. */
export function TrackingStatusBadge({
  paused,
  movement,
  observationCount,
  monitoringEnabled,
  providerAvailable,
}: {
  paused: boolean;
  movement?: "up" | "down" | "flat" | "unknown" | null;
  observationCount?: number;
  monitoringEnabled?: boolean;
  providerAvailable?: boolean;
}) {
  const label = trackingStateLabel({ paused, movement, observationCount, monitoringEnabled, providerAvailable });
  if (label === "paused") {
    return (
      <Badge variant="warning" title="Monitoring is paused for this product.">
        paused
      </Badge>
    );
  }
  if (label === "monitoring disabled") {
    return (
      <Badge variant="secondary" title="Monitoring is disabled via configuration.">
        monitoring disabled
      </Badge>
    );
  }
  if (label === "provider unavailable") {
    return (
      <Badge variant="destructive" title="No real price provider is configured.">
        provider unavailable
      </Badge>
    );
  }
  if (label === "waiting for data") {
    return (
      <Badge variant="info" title="No price observations recorded yet.">
        waiting for data
      </Badge>
    );
  }
  if (label === "price down") {
    return (
      <Badge variant="success" title="Price has moved down since the previous observation.">
        price down
      </Badge>
    );
  }
  if (label === "price up") {
    return <Badge variant="destructive">price up</Badge>;
  }
  if (label === "steady") {
    return <Badge variant="secondary">steady</Badge>;
  }
  return <Badge variant="secondary">monitoring</Badge>;
}