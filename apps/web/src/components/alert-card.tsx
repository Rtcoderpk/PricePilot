import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { formatPrice } from "@/components/price";
import type { AlertItem } from "@/lib/api";

const KIND_LABELS: Record<string, string> = {
  back_in_stock: "back in stock",
  target_price: "target reached",
  percent_drop: "price drop",
  new_low: "new low",
};

/** Pure mapping: alert kind → readable label. Unit-testable. */
export function alertKindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind.replace(/_/g, " ");
}

/** Alert kind → badge tone. Only reflects the real `kind`. */
export function alertKindVariant(kind: string): "success" | "info" | "secondary" {
  if (kind === "back_in_stock") return "success";
  if (kind === "target_price" || kind === "new_low") return "info";
  return "secondary";
}

/** Alert kind → readable label + badge tone. Only reflects the real `kind`. */
export function AlertKindBadge({ kind }: { kind: string }) {
  return <Badge variant={alertKindVariant(kind)}>{alertKindLabel(kind)}</Badge>;
}

export function AlertCard({ alert, action }: { alert: AlertItem; action?: React.ReactNode }) {
  const prev = alert.triggering_offer?.previous_price ?? null;
  const cur = alert.triggering_offer?.current_price ?? null;
  const currency = alert.triggering_offer?.currency;
  const pct = alert.triggering_offer
    ? prev != null && cur != null && prev !== 0
      ? Math.round(((cur - prev) / prev) * 1000) / 10
      : null
    : null;

  return (
    <Card className={alert.status === "unread" ? "border-primary/40" : ""}>
      <CardContent className="flex items-start justify-between gap-4 p-5 text-sm">
        <div>
          <div className="flex items-center gap-2 font-medium">
            {alert.title}
            <AlertKindBadge kind={alert.kind} />
          </div>
          <p className="mt-1 text-muted-foreground">{alert.body}</p>
          {(prev != null || cur != null) && (cur == null || prev == null || cur !== prev) ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {prev != null ? formatPrice(prev, currency) : "—"} → {cur != null ? formatPrice(cur, currency) : "—"}
              {pct != null ? ` (${pct > 0 ? "+" : ""}${pct}%)` : ""}
            </p>
          ) : null}
          <p className="mt-1 text-xs text-muted-foreground">
            {alert.created_at ? new Date(alert.created_at).toLocaleString() : ""}
            {alert.triggering_offer?.source ? ` · ${alert.triggering_offer.source}` : ""}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant={alert.status === "unread" ? "default" : "secondary"}>{alert.status}</Badge>
          {action ? <div className="mt-1">{action}</div> : null}
        </div>
      </CardContent>
    </Card>
  );
}