"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PriceChart } from "@/components/price-chart";
import { formatPrice } from "@/components/price";
import { priceHistory, trackingList } from "@/lib/api";

export default function HistoryPage() {
  const [tracks, setTracks] = useState<Awaited<ReturnType<typeof trackingList>>>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof priceHistory>> | null>(null);
  const [status, setStatus] = useState<string>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // fetch-on-mount: setState only happens after the awaited fetch resolves
    (async () => {
      try {
        const t = await trackingList();
        setTracks(t);
        if (t.length) {
          setSelected(t[0].product_id);
          const h = await priceHistory(t[0].product_id);
          setHistory(h);
          setStatus("ok");
        } else {
          setStatus("no_tracking");
        }
      } catch (e) {
        setStatus("error");
        setError(e instanceof Error ? e.message : "Could not load history.");
      }
    })();
  }, []);

  async function select(productId: string) {
    setSelected(productId);
    setStatus("loading");
    try {
      const h = await priceHistory(productId);
      setHistory(h);
      setStatus("ok");
    } catch {
      setStatus("error");
      setError("Could not load history for this product.");
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Price history"
        description="Real recorded observations for tracked products — never synthetic."
      />

      {status === "loading" ? <p className="mt-6 text-sm text-muted-foreground">Loading…</p> : null}
      {status === "no_tracking" ? (
        <Card className="mt-6">
          <CardContent className="p-6 text-sm text-muted-foreground">
            No products are tracked yet. Track a product to collect price history over time.
          </CardContent>
        </Card>
      ) : null}
      {status === "error" ? (
        <Card className="mt-6 border-destructive/40">
          <CardContent className="p-6 text-sm text-destructive">{error ?? "Failed to load history."}</CardContent>
        </Card>
      ) : null}

      {status === "ok" && history ? (
        <div className="mt-6 space-y-4">
          <div className="flex flex-wrap gap-2">
            {tracks.map((t) => (
              <button
                key={t.id}
                onClick={() => select(t.product_id)}
                className={`rounded-full border px-3 py-1 text-xs ${selected === t.product_id ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
              >
                {t.name}
              </button>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardContent className="space-y-2 p-6 text-sm">
                <h3 className="font-semibold">Analytics</h3>
                <AnalyticsRow label="Status" value={history.analytics.status === "available" ? "Available" : "Insufficient history"} />
                <AnalyticsRow label="Observations" value={String(history.analytics.observation_count)} />
                <AnalyticsRow
                  label="Current price"
                  value={
                    history.analytics.current_price != null
                      ? formatPrice(history.analytics.current_price, history.currency ?? undefined)
                      : "—"
                  }
                />
                <AnalyticsRow
                  label="Change"
                  value={
                    history.analytics.percentage_change != null
                      ? `${history.analytics.percentage_change > 0 ? "+" : ""}${history.analytics.percentage_change}%`
                      : "—"
                  }
                />
                <AnalyticsRow
                  label="Lowest observed"
                  value={
                    history.analytics.lowest_observed != null
                      ? formatPrice(history.analytics.lowest_observed, history.currency ?? undefined)
                      : "—"
                  }
                />
                <AnalyticsRow
                  label="Highest observed"
                  value={
                    history.analytics.highest_observed != null
                      ? formatPrice(history.analytics.highest_observed, history.currency ?? undefined)
                      : "—"
                  }
                />
                {history.analytics.trend ? (
                  <div className="flex items-center gap-2 pt-1">
                    <span className="text-muted-foreground">Trend:</span>
                    <Badge variant={history.analytics.trend === "down" ? "success" : "secondary"}>
                      {history.analytics.trend}
                    </Badge>
                  </div>
                ) : null}
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-6">
                <h3 className="mb-2 font-semibold">Chart</h3>
                <PriceChart points={history.observations} currency={history.currency} />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardContent className="p-6">
              <h3 className="mb-2 font-semibold">Observations</h3>
              {history.observations.length === 0 ? (
                <p className="text-sm text-muted-foreground">No observations recorded yet for this product.</p>
              ) : (
                <div className="max-h-72 space-y-1 overflow-y-auto text-xs">
                  {history.observations.map((o, i) => (
                    <div key={i} className="flex items-center justify-between rounded bg-muted/30 px-2 py-1">
                      <span>{new Date(o.observed_at).toLocaleString()}</span>
                      <span className="font-medium">
                        {formatPrice(o.amount, o.currency)}
                        {o.source ? <span className="ml-2 text-muted-foreground">({o.source})</span> : null}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

function AnalyticsRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
