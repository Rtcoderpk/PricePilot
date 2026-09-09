"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageContainer } from "@/components/container";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PriceChart } from "@/components/price-chart";
import { formatPrice } from "@/components/price";
import { EmptyState, ErrorState, InlineSpinner, InsufficientData } from "@/components/states";
import { priceHistory } from "@/lib/api";
import type { HistoryObservation } from "@/lib/api";

interface CompareItem {
  product_id: string;
  currency?: string | null;
  observations: HistoryObservation[];
  analytics: Awaited<ReturnType<typeof priceHistory>>["analytics"];
}

/** Pick the cheapest real observation across offers for a comparison row. */
function bestPrice(item: CompareItem): number | null {
  if (item.analytics.current_price != null) return item.analytics.current_price;
  if (item.observations.length >= 1) return item.observations[item.observations.length - 1].amount;
  return null;
}

export default function ComparePage({ searchParams }: { searchParams: Promise<{ ids?: string }> }) {
  const [items, setItems] = useState<CompareItem[] | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error" | "empty">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const { ids } = await searchParams;
      const idList = (ids ?? "").split(",").filter(Boolean).slice(0, 4);
      if (idList.length === 0) {
        setStatus("empty");
        return;
      }
      try {
        const results = await Promise.all(idList.map((id) => priceHistory(id)));
        setItems(
          idList.map((id, i) => ({
            product_id: id,
            currency: results[i].currency,
            observations: results[i].observations,
            analytics: results[i].analytics,
          })),
        );
        setStatus("ok");
      } catch (e) {
        setStatus("error");
        setError(e instanceof Error ? e.message : "Could not load comparison data.");
      }
    })();
  }, [searchParams]);

  return (
    <PageContainer>
      <PageHeader
        title="Compare products"
        description="Side-by-side price intelligence from real recorded observations — never synthetic."
      />

      {status === "loading" ? (
        <div className="mt-6">
          <InlineSpinner label="Loading comparison…" />
        </div>
      ) : null}

      {status === "error" ? (
        <div className="mt-6">
          <ErrorState title="Could not load comparison" description={error ?? undefined} />
        </div>
      ) : null}

      {status === "empty" ? (
        <div className="mt-6">
          <EmptyState
            title="No products to compare"
            description="Select 2–4 products from a search and they'll appear here side-by-side."
            action={
              <Link href="/search" className="text-sm font-medium text-primary underline underline-offset-2">
                Go to search
              </Link>
            }
          />
        </div>
      ) : null}

      {status === "ok" && items ? <CompareTable items={items} /> : null}
    </PageContainer>
  );
}

function CompareTable({ items }: { items: CompareItem[] }) {
  const hasHistory = items.some((i) => i.observations.length >= 2);
  const cheapestId = items.reduce<CompareItem | null>((acc, i) => {
    const p = bestPrice(i);
    if (p == null) return acc;
    const accP = acc ? bestPrice(acc) : null;
    return accP == null || p < accP ? i : acc;
  }, null);

  return (
    <div className="mt-6 space-y-6">
      {!hasHistory ? (
        <InsufficientData title="Not enough price history to compare" />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((item) => (
          <Card key={item.product_id}>
            <CardHeader>
              <CardTitle className="text-sm">
                <Link
                  href={`/product/${item.product_id}`}
                  className="line-clamp-2 hover:underline"
                >
                  {item.product_id.slice(0, 12)}…
                </Link>
              </CardTitle>
              {cheapestId?.product_id === item.product_id ? (
                <Badge variant="success">Lowest price</Badge>
              ) : null}
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <PriceLine label="Current" value={bestPrice(item)} currency={item.currency} />
              <PriceLine
                label="Lowest"
                value={item.analytics.lowest_observed}
                currency={item.currency}
              />
              <PriceLine
                label="Highest"
                value={item.analytics.highest_observed}
                currency={item.currency}
              />
              <PriceLine
                label="Average"
                value={item.analytics.average_observed}
                currency={item.currency}
              />
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Observations</span>
                <span className="font-medium">{item.analytics.observation_count}</span>
              </div>
              {item.analytics.trend ? (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Trend</span>
                  <Badge variant={item.analytics.trend === "down" ? "success" : "secondary"}>
                    {item.analytics.trend}
                  </Badge>
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts */}
      <div>
        <h2 className="text-base font-semibold">Price history</h2>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            <Card key={item.product_id}>
              <CardContent className="p-4">
                <p className="mb-2 truncate text-sm font-medium">{item.product_id.slice(0, 12)}…</p>
                <PriceChart points={item.observations} currency={item.currency} />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

function PriceLine({ label, value, currency }: { label: string; value?: number | null; currency?: string | null }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value != null ? formatPrice(value, currency) : "—"}</span>
    </div>
  );
}