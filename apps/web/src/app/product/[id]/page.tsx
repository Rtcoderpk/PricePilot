"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageContainer } from "@/components/container";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PriceChart } from "@/components/price-chart";
import { formatPrice } from "@/components/price";
import { PriceChange } from "@/components/price-change";
import { AnalyticsRow } from "@/components/analytics-row";
import { EmptyState, ErrorState, InlineSpinner, InsufficientData } from "@/components/states";
import { priceHistory, trackingCreate } from "@/lib/api";
import type { PriceAnalytics } from "@/lib/api";

export default function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const [id, setId] = useState<string | null>(null);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof priceHistory>> | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error" | "no_history">("loading");
  const [error, setError] = useState<string | null>(null);
  const [trackMsg, setTrackMsg] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const { id } = await params;
      setId(id);
      try {
        const h = await priceHistory(id);
        setHistory(h);
        setStatus(h.observations.length >= 1 ? "ok" : "no_history");
      } catch (e) {
        setStatus("error");
        setError(e instanceof Error ? e.message : "Could not load product data.");
      }
    })();
  }, [params]);

  async function track() {
    if (!id) return;
    setTrackMsg(null);
    try {
      const res = await trackingCreate({ product_id: id });
      setTrackMsg(res.status === "already_tracked" ? "Already tracking this product." : "Added to your tracking list.");
    } catch (e) {
      setTrackMsg(e instanceof Error ? e.message : "Could not track product.");
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title={id ? `Product ${id.slice(0, 12)}…` : "Product"}
        description="Real price history, analytics, and tracking for this product — never fabricated."
      />

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={track}>
          Track price
        </Button>
        {id ? (
          <Button size="sm" variant="outline" asChild>
            <Link href={`/search?q=${encodeURIComponent(id)}`}>Search offers</Link>
          </Button>
        ) : null}
        {trackMsg ? <span className="text-sm text-muted-foreground">{trackMsg}</span> : null}
      </div>

      {status === "loading" ? (
        <div className="mt-6">
          <InlineSpinner label="Loading product data…" />
        </div>
      ) : null}

      {status === "error" ? (
        <div className="mt-6">
          <ErrorState title="Could not load product" description={error ?? undefined} />
        </div>
      ) : null}

      {status === "no_history" ? (
        <div className="mt-6">
          <InsufficientData description="No real price observations exist for this product yet. Track it and PricePilot will begin collecting history." />
        </div>
      ) : null}

      {status === "ok" && history ? (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Price analytics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <AnalyticsMetrics analytics={history.analytics} currency={history.currency} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Price history</CardTitle>
            </CardHeader>
            <CardContent>
              <PriceChart points={history.observations} currency={history.currency} />
            </CardContent>
          </Card>
        </div>
      ) : null}

      {status === "ok" && history && history.observations.length > 0 ? (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-base">Observations</CardTitle>
          </CardHeader>
          <CardContent>
            {history.observations.length === 0 ? (
              <p className="text-sm text-muted-foreground">No observations recorded yet.</p>
            ) : (
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 pr-2 font-medium">When</th>
                      <th className="py-2 pr-2 font-medium">Price</th>
                      <th className="py-2 font-medium">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.observations.map((o, i) => (
                      <tr key={i} className="border-t">
                        <td className="py-2 pr-2 text-muted-foreground">
                          {new Date(o.observed_at).toLocaleString()}
                        </td>
                        <td className="py-2 pr-2 font-medium">
                          {formatPrice(o.amount, o.currency ?? history.currency)}
                        </td>
                        <td className="py-2 text-muted-foreground">{o.source ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}

      {history && history.observations.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No offers loaded"
            description="This product has no recorded offers yet. Use Search to find it and return here for history."
          />
        </div>
      ) : null}
    </PageContainer>
  );
}

function AnalyticsMetrics({ analytics, currency }: { analytics: PriceAnalytics; currency?: string | null }) {
  return (
    <>
      <AnalyticsRow
        label="Status"
        value={
          <Badge variant={analytics.status === "available" ? "success" : "secondary"}>
            {analytics.status === "available" ? "Available" : "Insufficient history"}
          </Badge>
        }
      />
      <AnalyticsRow label="Observations" value={String(analytics.observation_count)} />
      <AnalyticsRow
        label="Current price"
        value={analytics.current_price != null ? formatPrice(analytics.current_price, currency) : "—"}
      />
      <AnalyticsRow
        label="Change"
        value={
          <PriceChange current={analytics.current_price} previous={analytics.previous_price} />
        }
      />
      <AnalyticsRow
        label="Lowest observed"
        value={analytics.lowest_observed != null ? formatPrice(analytics.lowest_observed, currency) : "—"}
      />
      <AnalyticsRow
        label="Highest observed"
        value={analytics.highest_observed != null ? formatPrice(analytics.highest_observed, currency) : "—"}
      />
      <AnalyticsRow
        label="Average observed"
        value={analytics.average_observed != null ? formatPrice(analytics.average_observed, currency) : "—"}
      />
      {analytics.trend ? <AnalyticsRow label="Trend" value={analytics.trend} /> : null}
    </>
  );
}