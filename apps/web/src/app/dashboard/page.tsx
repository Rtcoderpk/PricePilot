"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatPrice } from "@/components/price";
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
        const [t, a, mon] = await Promise.all([trackingList(), alertsList(true), monitoringStatus()]);
        setTracks(t);
        setAlerts(a);
        setMonitorInfo(mon);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load dashboard.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const active = tracks.filter((t) => !t.paused).length;
  const paused = tracks.length - active;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Dashboard"
        description="Tracked products, price drops, active alerts, recent searches, recommended deals."
      />

      {loading ? <p className="mt-6 text-sm text-muted-foreground">Loading…</p> : null}
      {error ? (
        <Card className="mt-4 border-destructive/40">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {!loading && !error ? (
        <>
          {/* stat cards */}
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
                <Link href="/alerts" className="mt-1 inline-block text-xs underline">
                  View alerts
                </Link>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5 text-sm">
                <p className="text-muted-foreground">Monitoring</p>
                <p className="mt-1 text-2xl font-bold">
                  <Badge variant={monitorInfo?.provider === "available" ? "success" : "warning"}>
                    {monitorInfo?.provider ?? "?"}
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

          {/* tracked products */}
          <div className="mt-8">
            <h2 className="text-lg font-semibold">Tracked products</h2>
            {tracks.length === 0 ? (
              <Card className="mt-3">
                <CardContent className="p-6 text-sm text-muted-foreground">
                  No products are tracked yet.{" "}
                  <Link href="/track" className="underline">
                    Track a product
                  </Link>{" "}
                  to start collecting price history and alerts.
                </CardContent>
              </Card>
            ) : (
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {tracks.map((t) => (
                  <Card key={t.id}>
                    <CardContent className="flex items-start justify-between gap-2 p-5 text-sm">
                      <div>
                        <div className="font-medium">{t.name}</div>
                        {t.target_price != null ? (
                          <p className="text-muted-foreground">
                            target: {formatPrice(t.target_price, t.target_currency ?? undefined)}
                          </p>
                        ) : (
                          <p className="text-muted-foreground">no target price</p>
                        )}
                        {t.last_observed_at ? (
                          <p className="mt-1 text-xs text-muted-foreground">
                            observed {new Date(t.last_observed_at).toLocaleDateString()}
                          </p>
                        ) : null}
                      </div>
                      {t.paused ? <Badge variant="warning">paused</Badge> : null}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* recent alerts */}
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
                  <Card key={a.id}>
                    <CardContent className="flex items-start justify-between gap-3 p-4 text-sm">
                      <div>
                        <div className="font-medium">
                          {a.title}
                          <Badge variant="secondary" className="ml-2">
                            {a.kind}
                          </Badge>
                        </div>
                        <p className="mt-1 text-muted-foreground">{a.body}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {new Date(a.created_at ?? "").toLocaleString()}
                        </p>
                      </div>
                      <Link href="/alerts" className="text-xs underline">
                        Manage
                      </Link>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}