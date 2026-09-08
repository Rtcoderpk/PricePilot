"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatPrice } from "@/components/price";
import {
  trackingList,
  trackingCreate,
  trackingUpdate,
  trackingDelete,
  monitoringStatus,
} from "@/lib/api";
import type { TrackingItem } from "@/lib/api";

export default function TrackPage() {
  const [tracks, setTracks] = useState<TrackingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [monitorInfo, setMonitorInfo] = useState<{
    enabled: boolean;
    provider: string;
    message?: string | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newProductId, setNewProductId] = useState("");
  const [newTarget, setNewTarget] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [t, mon] = await Promise.all([trackingList(), monitoringStatus()]);
      setTracks(t);
      setMonitorInfo(mon);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load tracking.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // fetch-on-mount: setState only happens after the awaited fetch resolves
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!newProductId.trim()) return;
    const target = newTarget ? parseFloat(newTarget) : undefined;
    await trackingCreate({ product_id: newProductId.trim(), target_price: target ?? null });
    setNewProductId("");
    setNewTarget("");
    load();
  }

  async function togglePause(t: TrackingItem) {
    setBusyId(t.id);
    await trackingUpdate(t.id, { paused: !t.paused });
    setBusyId(null);
    load();
  }

  async function remove(t: TrackingItem) {
    if (!confirm(`Remove tracking for "${t.name}"?`)) return;
    setBusyId(t.id);
    await trackingDelete(t.id);
    setBusyId(null);
    load();
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Tracked products"
        description="Track products and get price-drop / target alerts. Provider status shown below."
      />

      {monitorInfo ? (
        <Card className="mt-4">
          <CardContent className="flex items-center gap-3 p-4 text-sm">
            <span>
              Monitoring: <strong>{monitorInfo.enabled ? "enabled" : "disabled"}</strong>
            </span>
            <Badge variant={monitorInfo.provider === "available" ? "secondary" : "destructive"}>
              provider: {monitorInfo.provider}
            </Badge>
            {monitorInfo.message ? (
              <span className="text-muted-foreground">— {monitorInfo.message}</span>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <form onSubmit={add} className="mt-6 flex max-w-2xl items-end gap-3">
        <div className="flex-1">
          <label className="mb-1 block text-xs font-medium text-muted-foreground">Product ID</label>
          <Input value={newProductId} onChange={(e) => setNewProductId(e.target.value)} placeholder="pp_gtin_..." />
        </div>
        <div className="w-32">
          <label className="mb-1 block text-xs font-medium text-muted-foreground">Target price</label>
          <Input value={newTarget} onChange={(e) => setNewTarget(e.target.value)} placeholder="optional" />
        </div>
        <Button type="submit">Track</Button>
      </form>

      {loading ? <p className="mt-4 text-sm text-muted-foreground">Loading…</p> : null}
      {error ? (
        <Card className="mt-4 border-destructive/40">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {tracks.map((t) => (
          <Card key={t.id}>
            <CardContent className="flex flex-col gap-2 p-5 text-sm">
              <div className="flex items-start justify-between">
                <div className="font-medium">{t.name}</div>
                {t.paused ? <Badge variant="warning">paused</Badge> : <Badge variant="secondary">active</Badge>}
              </div>
              {t.target_price != null ? (
                <p className="text-muted-foreground">
                  target: {formatPrice(t.target_price, t.target_currency ?? undefined)}
                </p>
              ) : null}
              {t.last_observed_at ? (
                <p className="text-xs text-muted-foreground">
                  last observed: {new Date(t.last_observed_at).toLocaleString()}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">not yet observed</p>
              )}
              <div className="flex gap-2 pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busyId === t.id}
                  onClick={() => togglePause(t)}
                >
                  {t.paused ? "Resume" : "Pause"}
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={busyId === t.id}
                  onClick={() => remove(t)}
                >
                  Remove
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {tracks.length === 0 && !loading ? (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              No products are tracked. Add one above using a canonical product ID.
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
