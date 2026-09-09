"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageContainer } from "@/components/container";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { AlertCard } from "@/components/alert-card";
import { ErrorState, EmptyState, LoadingBlock } from "@/components/states";
import { alertsList, alertMark, monitoringStatus } from "@/lib/api";
import type { AlertItem } from "@/lib/api";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [monitorInfo, setMonitorInfo] = useState<{ enabled: boolean; provider: string } | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [a, mon] = await Promise.all([alertsList(onlyUnread), monitoringStatus()]);
        setAlerts(a);
        setMonitorInfo(mon);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load alerts.");
      } finally {
        setLoading(false);
      }
    })();
  }, [onlyUnread]);

  async function mark(id: string, status: "read" | "dismissed") {
    try {
      await alertMark(id, status);
      setAlerts((prev) => (status === "dismissed" ? prev.filter((a) => a.id !== id) : prev.map((a) => (a.id === id ? { ...a, status } : a))));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update alert.");
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Price alerts"
        description="Real alerts from real price events — never fabricated."
      />

      {monitorInfo ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Monitoring: <strong>{monitorInfo.enabled ? "enabled" : "disabled"}</strong> · provider:{" "}
          {monitorInfo.provider}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          variant={onlyUnread ? "default" : "outline"}
          onClick={() => setOnlyUnread(!onlyUnread)}
        >
          {onlyUnread ? "Show all" : "Unread only"}
        </Button>
      </div>

      {loading ? (
        <div className="mt-6">
          <LoadingBlock lines={4} />
        </div>
      ) : null}
      {error ? (
        <div className="mt-6">
          <ErrorState title="Could not load alerts" description={error} />
        </div>
      ) : null}

      {!loading && !error ? (
        <div className="mt-6 space-y-2">
          {alerts.map((a) => (
            <AlertCard
              key={a.id}
              alert={a}
              action={
                a.status === "unread" ? (
                  <div className="flex flex-col items-end gap-1">
                    <Button size="sm" variant="ghost" onClick={() => mark(a.id, "read")}>
                      Mark read
                    </Button>
                    <Button size="sm" variant="ghost" className="text-destructive" onClick={() => mark(a.id, "dismissed")}>
                      Dismiss
                    </Button>
                  </div>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => mark(a.id, "dismissed")}>
                    Dismiss
                  </Button>
                )
              }
            />
          ))}

          {alerts.length === 0 ? (
            <EmptyState
              title="No alerts yet"
              description={
                monitorInfo && !monitorInfo.enabled
                  ? "Monitoring is disabled or unavailable. No alerts have been generated."
                  : "Track a product and wait for a real price change — alerts appear here when they fire."
              }
              action={
                <Link href="/track" className="text-sm font-medium text-primary underline underline-offset-2">
                  Track a product
                </Link>
              }
            />
          ) : null}
        </div>
      ) : null}
    </PageContainer>
  );
}