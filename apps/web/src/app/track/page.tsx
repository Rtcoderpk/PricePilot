"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageContainer } from "@/components/container";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatPrice } from "@/components/price";
import { PriceChange } from "@/components/price-change";
import { TrackingStatusBadge } from "@/components/tracking-status";
import { ErrorState, LoadingBlock, EmptyState } from "@/components/states";
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
  const [confirmRemove, setConfirmRemove] = useState<TrackingItem | null>(null);

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
    (async () => {
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
    })();
    // fetch-on-mount only
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!newProductId.trim()) return;
    const target = newTarget ? parseFloat(newTarget) : undefined;
    try {
      await trackingCreate({ product_id: newProductId.trim(), target_price: target ?? null });
      setNewProductId("");
      setNewTarget("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not track product.");
    }
    load();
  }

  async function togglePause(t: TrackingItem) {
    setBusyId(t.id);
    try {
      await trackingUpdate(t.id, { paused: !t.paused });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update tracking.");
    }
    setBusyId(null);
    load();
  }

  async function confirmAndRemove() {
    if (!confirmRemove) return;
    setBusyId(confirmRemove.id);
    try {
      await trackingDelete(confirmRemove.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not remove tracking.");
    }
    setBusyId(null);
    setConfirmRemove(null);
    load();
  }

  const providerAvailable = monitorInfo?.provider === "available";

  return (
    <PageContainer>
      <PageHeader
        title="Tracked products"
        description="Watch products, set a target price, and get alerts on real price moves."
      />

      {monitorInfo ? (
        <Card className="mt-4">
          <CardContent className="flex flex-wrap items-center gap-3 p-4 text-sm">
            <span>
              Monitoring: <strong>{monitorInfo.enabled ? "enabled" : "disabled"}</strong>
            </span>
            <Badge variant={providerAvailable ? "success" : "destructive"}>
              provider: {monitorInfo.provider}
            </Badge>
            {monitorInfo.message ? <span className="text-muted-foreground">— {monitorInfo.message}</span> : null}
          </CardContent>
        </Card>
      ) : null}

      {error ? (
        <div className="mt-4">
          <ErrorState title="Could not load tracking" description={error} />
        </div>
      ) : null}

      {/* Add form */}
      <form onSubmit={add} className="mt-6 flex max-w-2xl flex-wrap items-end gap-3">
        <div className="min-w-[200px] flex-1">
          <Label htmlFor="product-id" className="mb-1 block text-xs font-medium text-muted-foreground">
            Product ID
          </Label>
          <Input id="product-id" value={newProductId} onChange={(e) => setNewProductId(e.target.value)} placeholder="pp_gtin_..." />
        </div>
        <div className="w-32">
          <Label htmlFor="target-price" className="mb-1 block text-xs font-medium text-muted-foreground">
            Target price
          </Label>
          <Input id="target-price" value={newTarget} onChange={(e) => setNewTarget(e.target.value)} placeholder="optional" inputMode="decimal" />
        </div>
        <Button type="submit" disabled={!newProductId.trim()}>
          Track
        </Button>
      </form>

      {loading ? (
        <div className="mt-6">
          <LoadingBlock lines={4} />
        </div>
      ) : null}

      {!loading && tracks.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title="Nothing tracked yet"
            description="Add a canonical product ID above. Track a product to collect price history and alerts over time."
            action={
              <Link href="/search" className="text-sm font-medium text-primary underline underline-offset-2">
                Search for products
              </Link>
            }
          />
        </div>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {tracks.map((t) => (
            <Card key={t.id}>
              <CardContent className="flex flex-col gap-2 p-5 text-sm">
                <div className="flex items-start justify-between gap-2">
                  <Link href={`/product/${t.product_id}`} className="line-clamp-2 font-medium hover:underline">
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
                  <span>{t.current_price != null ? formatPrice(t.current_price, t.target_currency) : "no price yet"}</span>
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
                    last observed: {new Date(t.last_observed_at).toLocaleString()}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">not yet observed</p>
                )}

                <div className="flex gap-2 pt-1">
                  <Button size="sm" variant="outline" disabled={busyId === t.id} onClick={() => togglePause(t)}>
                    {t.paused ? "Resume" : "Pause"}
                  </Button>
                  <Button size="sm" variant="destructive" disabled={busyId === t.id} onClick={() => setConfirmRemove(t)}>
                    Remove
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Remove confirmation */}
      <Dialog open={confirmRemove != null} onOpenChange={(open) => !open && setConfirmRemove(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove tracking?</DialogTitle>
            <DialogDescription>
              Stop monitoring “{confirmRemove?.name}” and remove its price history from your tracking list. Alerts for this
              product will no longer be generated.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmRemove(null)}>
              Cancel
            </Button>
            <Button variant="destructive" disabled={busyId === confirmRemove?.id} onClick={confirmAndRemove}>
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}