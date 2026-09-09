import type { PriceInsight } from "@/lib/types";

export function formatPrice(amount: number | null | undefined, currency: string | null | undefined = "USD"): string {
  if (amount === null || amount === undefined) return "—";
  const cur = currency ?? "USD";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: cur,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${cur} ${amount}`;
  }
}

export function BestPrice({ price }: { price: PriceInsight | null }) {
  if (!price || price.current === null) {
    return <span className="text-muted-foreground">No price listed</span>;
  }
  return <span className="text-lg font-semibold">{formatPrice(price.current, price.currency)}</span>;
}