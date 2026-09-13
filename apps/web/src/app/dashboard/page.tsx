"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageContainer } from "@/components/container";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatPrice } from "@/components/price";
import { PriceChange } from "@/components/price-change";
import { TrackingStatusBadge } from "@/components/tracking-status";
import { ErrorState, LoadingBlock } from "@/components/states";
import { AlertCard, AlertKindBadge } from "@/components/alert-card";
import { alertsList, monitoringStatus, trackingList } from "@/lib/api";
import type { AlertItem, TrackingItem } from "@/lib/api";

export default function DashboardPage() {
  const [tracks, setTracks] = useState<TrackingItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [monitorInfo, setMonitorInfo] = useState<{
    enabled: boolean;
    provider: string;
    tracked_products: number;
    message?: string | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [tRes, aRes, monRes] = await Promise.allSettled([
          trackingList(),
          alertsList(true),
          monitoringStatus(),
        ]);

        if (tRes.status === "fulfilled") setTracks(tRes.value);
        if (aRes.status === "fulfilled") setAlerts(aRes.value);
        if (monRes.status === "fulfilled") setMonitorInfo(monRes.value);

        if (tRes.status === "rejected" && aRes.status === "rejected" && monRes.status === "rejected") {
          const firstErr = tRes.reason;
          setError(firstErr instanceof Error ? firstErr.message : "Failed to load dashboard data.");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load dashboard.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const active = tracks.filter((t) => !t.paused).length;
  const paused = tracks.length - active;
  const providerAvailable = monitorInfo?.provider === "available";

  return (
    <PageContainer>
      <PageHeader
        title="Dashboard"
        description="Tracked products, price moves, and alerts — all from real observations."
      />

      {loading ? (
        <div className="mt-6">
          <LoadingBlock lines={5} />
        </div>
      ) : null}

      {error ? (
        <div className="mt-6">
          <ErrorState title="Could not load your dashboard" description={error} />
        </div>
      ) : null}

      {!loading && !error ? (
        <>
          {/* Stat cards */}
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <Card>
              <CardContent className="p-5 text-sm">
                <p className="text-muted-foreground">Tracking</p>
                <p className="mt-1 text-2xl font-bold">{tracks.length}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {active} active · {paused} paused
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5 text-sm">
                <p className="text-muted-foreground">Unread alerts</p>
                <p className="mt-1 text-2xl font-bold">{alerts.length}</p>
                <Link href="/alerts" className="mt-1 inline-block text-xs underline underline-offset-2">
                  View alerts
                </Link>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5 text-sm">
                <p className="text-muted-foreground">Monitoring</p>
                <p className="mt-1 text-2xl font-bold">
                  <Badge variant={providerAvailable ? "success" : "warning"}>
                    {providerAvailable ? "available" : "unavailable"}
                  </Badge>
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {monitorInfo?.enabled ? "enabled" : "disabled"}
                </p>
              </CardContent>
            </Card>
          </div>

          {monitorInfo?.message ? (
            <p className="mt-4 text-xs text-muted-foreground">— {monitorInfo.message}</p>
          ) : null}

          {/* Tracked products */}
          <div className="mt-8">
            <h2 className="text-lg font-semibold">Tracked products</h2>
            {tracks.length === 0 ? (
              <Card className="mt-3">
                <CardContent className="p-6 text-sm text-muted-foreground">
                  No products are tracked yet.{" "}
                  <Link href="/track" className="underline underline-offset-2">
                    Track a product
                  </Link>{" "}
                  to start collecting price history and alerts.
                </CardContent>
              </Card>
            ) : (
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {tracks.map((t) => (
                  <Card key={t.id}>
                    <CardContent className="flex flex-col gap-2 p-5 text-sm">
                      <div className="flex items-start justify-between gap-2">
                        <Link
                          href={`/product/${t.product_id}`}
                          className="line-clamp-2 font-medium hover:underline"
                        >
                          {t.name}
                        </Link>
                        <TrackingStatusBadge
                          paused={t.paused}
                          movement={t.movement}
                          observationCount={t.observation_count}
                          monitoringEnabled={monitorInfo?.enabled}
                          providerAvailable={providerAvailable}
                        />
                      </div>
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>
                          {t.current_price != null ? formatPrice(t.current_price, t.target_currency) : "no price yet"}
                        </span>
                        {t.current_price != null && t.previous_price != null ? (
                          <PriceChange current={t.current_price} previous={t.previous_price} />
                        ) : null}
                      </div>
                      {t.target_price != null ? (
                        <p className="text-xs text-muted-foreground">
                          target: {formatPrice(t.target_price, t.target_currency)}
                        </p>
                      ) : null}
                      {t.last_observed_at ? (
                        <p className="text-xs text-muted-foreground">
                          observed {new Date(t.last_observed_at).toLocaleDateString()}
                        </p>
                      ) : null}
                      <div className="mt-1 flex gap-2">
                        <Link
                          href={`/history`}
                          className="text-xs font-medium text-primary underline underline-offset-2"
                        >
                          History
                        </Link>
                        <Link
                          href={`/track`}
                          className="text-xs font-medium text-primary underline underline-offset-2"
                        >
                          Manage
                        </Link>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* Recent alerts */}
          <div className="mt-8">
            <h2 className="text-lg font-semibold">Recent price alerts</h2>
            {alerts.length === 0 ? (
              <Card className="mt-3">
                <CardContent className="p-6 text-sm text-muted-foreground">
                  No unread alerts. Alert events fire on real price changes for tracked products.
                </CardContent>
              </Card>
            ) : (
              <div className="mt-3 space-y-2">
                {alerts.slice(0, 5).map((a) => (
                  <AlertCard key={a.id} alert={a} />
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </PageContainer>
  );
}

export { AlertKindBadge };