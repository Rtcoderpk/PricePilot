"use client";

import { useEffect, useState } from "react";
import { PageContainer } from "@/components/container";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PriceChart } from "@/components/price-chart";
import { formatPrice } from "@/components/price";
import { PriceChange } from "@/components/price-change";
import { AnalyticsRow } from "@/components/analytics-row";
import { ErrorState, InsufficientData, LoadingBlock, EmptyState } from "@/components/states";
import { priceHistory, trackingList } from "@/lib/api";
import type { HistoryObservation } from "@/lib/api";

type Range = "all" | 30 | 90;

const RANGE_DAYS: Record<Range, number | null> = { all: null, 30: 30, 90: 90 };

export default function HistoryPage() {
  const [tracks, setTracks] = useState<Awaited<ReturnType<typeof trackingList>>>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof priceHistory>> | null>(null);
  const [status, setStatus] = useState<string>("loading");
  const [error, setError] = useState<string | null>(null);
  const [range, setRange] = useState<Range>("all");
  const [cutoffAt, setCutoffAt] = useState<number | null>(null); // ms; set on user range change only

  useEffect(() => {
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

  // Range filtering is only ever applied to REAL observations. If the chosen
  // range leaves fewer than 2 points, we show the honest insufficient state.
  const filtered = (() => {
    if (!history) return [] as HistoryObservation[];
    if (cutoffAt == null) return history.observations;
    return history.observations.filter((o) => new Date(o.observed_at).getTime() >= cutoffAt);
  })();

  return (
    <PageContainer>
      <PageHeader
        title="Price history"
        description="Real recorded observations for tracked products — never synthetic."
      />

      {status === "loading" ? (
        <div className="mt-6">
          <LoadingBlock lines={4} />
        </div>
      ) : null}

      {status === "no_tracking" ? (
        <div className="mt-6">
          <EmptyState
            title="No products are tracked yet"
            description="Track a product to collect price history over time."
          />
        </div>
      ) : null}

      {status === "error" ? (
        <div className="mt-6">
          <ErrorState title="Could not load history" description={error ?? undefined} />
        </div>
      ) : null}

      {status === "ok" && history ? (
        <div className="mt-6 space-y-4">
          {/* Product selector */}
          <div className="flex flex-wrap gap-2">
            {tracks.map((t) => (
              <Button
                key={t.id}
                size="sm"
                variant={selected === t.product_id ? "default" : "outline"}
                onClick={() => select(t.product_id)}
              >
                {t.name}
              </Button>
            ))}
          </div>

          {/* Range control (only shown when there is history) */}
          {history.observations.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-muted-foreground">Range:</span>
              {(["all", 30, 90] as Range[]).map((r) => {
                const days = RANGE_DAYS[r];
                return (
                  <Button
                    key={r}
                    size="sm"
                    variant={range === r ? "default" : "outline"}
                    onClick={() => {
                      setRange(r);
                      setCutoffAt(days == null ? null : Date.now() - days * 24 * 60 * 60 * 1000);
                    }}
                  >
                    {r === "all" ? "All" : `${r}d`}
                  </Button>
                );
              })}
            </div>
          ) : null}

          {filtered.length < 2 ? (
            <div className="mt-4">
              <InsufficientData
                title={history.observations.length < 2 ? "Not enough historical data yet" : "No observations in this range"}
                description={
                  history.observations.length < 2
                    ? "Price history is collected over time as real observations. Once enough samples exist, charts and analytics will appear here."
                    : "There are no recorded observations within the selected time range."
                }
              />
            </div>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardContent className="space-y-2 p-6 text-sm">
                    <h3 className="font-semibold">Analytics</h3>
                    <AnalyticsRow
                      label="Status"
                      value={
                        <Badge variant={history.analytics.status === "available" ? "success" : "secondary"}>
                          {history.analytics.status === "available" ? "Available" : "Insufficient history"}
                        </Badge>
                      }
                    />
                    <AnalyticsRow label="Observations" value={String(history.analytics.observation_count)} />
                    <AnalyticsRow
                      label="Current price"
                      value={
                        history.analytics.current_price != null
                          ? formatPrice(history.analytics.current_price, history.currency)
                          : "—"
                      }
                    />
                    <AnalyticsRow
                      label="Change"
                      value={<PriceChange current={history.analytics.current_price} previous={history.analytics.previous_price} />}
                    />
                    <AnalyticsRow
                      label="Lowest observed"
                      value={
                        history.analytics.lowest_observed != null
                          ? formatPrice(history.analytics.lowest_observed, history.currency)
                          : "—"
                      }
                    />
                    <AnalyticsRow
                      label="Highest observed"
                      value={
                        history.analytics.highest_observed != null
                          ? formatPrice(history.analytics.highest_observed, history.currency)
                          : "—"
                      }
                    />
                    <AnalyticsRow
                      label="Average observed"
                      value={
                        history.analytics.average_observed != null
                          ? formatPrice(history.analytics.average_observed, history.currency)
                          : "—"
                      }
                    />
                    {history.analytics.trend ? (
                      <div className="flex items-center justify-between gap-4">
                        <span className="text-sm text-muted-foreground">Trend</span>
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
                    <PriceChart points={filtered} currency={history.currency} />
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardContent className="p-6">
                  <h3 className="mb-2 font-semibold">Observations</h3>
                  {filtered.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No observations recorded yet for this product.</p>
                  ) : (
                    <div className="max-h-72 overflow-y-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="uppercase text-muted-foreground">
                          <tr>
                            <th className="py-2 pr-4 font-medium">When</th>
                            <th className="py-2 pr-4 font-medium">Price</th>
                            <th className="py-2 font-medium">Source</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filtered.map((o, i) => (
                            <tr key={i} className="border-t">
                              <td className="py-2 pr-4 text-muted-foreground">{new Date(o.observed_at).toLocaleString()}</td>
                              <td className="py-2 pr-4 font-medium">{formatPrice(o.amount, o.currency)}</td>
                              <td className="py-2 text-muted-foreground">{o.source ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      ) : null}
    </PageContainer>
  );
}