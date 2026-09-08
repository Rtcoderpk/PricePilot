"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { alertsList, alertMark } from "@/lib/api";
import { monitoringStatus } from "@/lib/api";
import type { AlertItem } from "@/lib/api";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [monitorInfo, setMonitorInfo] = useState<{ enabled: boolean; provider: string } | null>(null);

  async function load() {
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
  }

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
    await alertMark(id, status);
    load();
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Price alerts"
        description="Real alerts from real price events — never fabricated."
      />

      {monitorInfo ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Monitoring: <strong>{monitorInfo.enabled ? "enabled" : "disabled"}</strong> · provider: {monitorInfo.provider}
        </p>
      ) : null}

      <div className="mt-4 flex items-center gap-3">
        <Button
          size="sm"
          variant={onlyUnread ? "default" : "outline"}
          onClick={() => setOnlyUnread(!onlyUnread)}
        >
          {onlyUnread ? "Show all" : "Unread only"}
        </Button>
      </div>

      {loading ? <p className="mt-6 text-sm text-muted-foreground">Loading…</p> : null}
      {error ? (
        <Card className="mt-4 border-destructive/40">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <div className="mt-6 space-y-2">
        {alerts.map((a) => (
          <Card key={a.id} className={a.status === "unread" ? "border-primary/40" : ""}>
            <CardContent className="flex items-start justify-between gap-4 p-5 text-sm">
              <div>
                <div className="flex items-center gap-2 font-medium">
                  {a.title}
                  <Badge variant="secondary">{a.kind}</Badge>
                </div>
                <p className="mt-1 text-muted-foreground">{a.body}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {new Date(a.created_at ?? "").toLocaleString()}
                  {a.product_id ? <span className="ml-2">product: {a.product_id.slice(0, 12)}…</span> : null}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <Badge variant={a.status === "unread" ? "default" : "secondary"}>{a.status}</Badge>
                {a.status === "unread" ? (
                  <Button size="sm" variant="ghost" onClick={() => mark(a.id, "read")}>
                    Mark read
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ))}

        {alerts.length === 0 && !loading ? (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              {monitorInfo && !monitorInfo.enabled
                ? "Monitoring is disabled or unavailable. No alerts have been generated."
                : "No alerts yet. Track a product and wait for a price change."}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
