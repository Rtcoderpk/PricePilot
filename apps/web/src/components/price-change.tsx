import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

/** Pure classification of a price movement — unit-testable, never fabricates. */
export type PriceMovementKind = "unknown" | "flat" | "down" | "up";

export function classifyPriceChange(
  current?: number | null,
  previous?: number | null,
): { kind: PriceMovementKind; pct: number | null } {
  if (current == null || previous == null) return { kind: "unknown", pct: null };
  const diff = current - previous;
  if (Math.abs(diff) < 0.005) return { kind: "flat", pct: null };
  // Signed pct: negative for a drop, positive for a rise — matching the
  // analytics convention used elsewhere in the app.
  const pct = previous !== 0 ? Math.round((diff / Math.abs(previous)) * 1000) / 10 : null;
  return { kind: diff < 0 ? "down" : "up", pct };
}

/**
 * Renders a price movement (current vs previous) as an honest, typed badge.
 * Only ever reflects real numbers passed in — never fabricates a direction.
 */
export function PriceChange({
  current,
  previous,
  className,
}: {
  current?: number | null;
  previous?: number | null;
  className?: string;
}) {
  const { kind, pct } = classifyPriceChange(current, previous);

  if (kind === "unknown") {
    return (
      <span className={cn("inline-flex items-center gap-1 text-xs text-muted-foreground", className)}>
        <Minus aria-hidden className="h-3 w-3" /> n/a
      </span>
    );
  }
  if (kind === "flat") {
    return (
      <span className={cn("inline-flex items-center gap-1 text-xs text-muted-foreground", className)}>
        <Minus aria-hidden className="h-3 w-3" /> flat
      </span>
    );
  }
  const down = kind === "down";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium",
        down ? "text-emerald-700" : "text-red-600",
        className,
      )}
    >
      {down ? <TrendingDown aria-hidden className="h-3 w-3" /> : <TrendingUp aria-hidden className="h-3 w-3" />}
      {down ? "▼" : "▲"} {pct != null ? `${pct}%` : Math.abs((current ?? 0) - (previous ?? 0)) < 1 ? "small" : "moved"}
    </span>
  );
}