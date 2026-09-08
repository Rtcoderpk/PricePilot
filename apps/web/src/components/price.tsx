import type { PriceInsight } from "@/lib/types";

export function formatPrice(amount: number | null | undefined, currency = "USD"): string {
  if (amount === null || amount === undefined) return "—";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount}`;
  }
}

export function BestPrice({ price }: { price: PriceInsight | null }) {
  if (!price || price.current === null) {
    return <span className="text-muted-foreground">No price listed</span>;
  }
  return <span className="text-lg font-semibold">{formatPrice(price.current, price.currency)}</span>;
}