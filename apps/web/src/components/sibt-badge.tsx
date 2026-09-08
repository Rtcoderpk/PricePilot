import { Badge } from "@/components/ui/badge";
import type { SibtDetail } from "@/lib/types";

export function SibtBadge({ sibt }: { sibt?: SibtDetail | null }) {
  if (!sibt) return null;
  const { verdict, confidence } = sibt;
  const label = {
    buy: "BUY",
    wait: "WAIT",
    avoid: "AVOID",
    insufficient_data: "insufficient data",
  }[verdict];

  const variant =
    verdict === "buy"
      ? "success"
      : verdict === "wait"
        ? "warning"
        : verdict === "avoid"
          ? "destructive"
          : "secondary";

  return (
    <Badge variant={variant as "success" | "warning" | "destructive" | "secondary"} className="mr-1">
      {label}
      {verdict !== "insufficient_data" && confidence > 0 ? ` · ${Math.round(confidence * 100)}%` : ""}
    </Badge>
  );
}