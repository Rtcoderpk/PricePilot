"use client";

import { useEffect, useState } from "react";
import { PageContainer } from "@/components/container";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ErrorState, LoadingBlock } from "@/components/states";
import { CheckCircle2 } from "lucide-react";
import { preferencesGet, preferencesUpdate } from "@/lib/api";
import type { UserPreferences } from "@/lib/api";

const CONDITIONS = ["new", "refurbished", "any"];
const CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD"];

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [brands, setBrands] = useState("");
  const [budget, setBudget] = useState("");
  const [stores, setStores] = useState("");
  const [condition, setCondition] = useState<string[]>([]);
  const [priceVsQuality, setPriceVsQuality] = useState("");
  const [currency, setCurrency] = useState("");
  const [locale, setLocale] = useState("");
  const [emailAlerts, setEmailAlerts] = useState(false);

  function hydrate(p: UserPreferences | null) {
    if (!p) return;
    setBrands((p.preferred_brands ?? []).join(", "));
    setBudget(p.max_budget != null ? String(p.max_budget) : "");
    setStores((p.preferred_stores ?? []).join(", "));
    setCondition(p.preferred_condition ?? []);
    setPriceVsQuality(p.price_vs_quality != null ? String(p.price_vs_quality) : "");
    setCurrency(p.currency_code ?? "");
    setLocale(p.shopping_locale ?? "");
  }

  useEffect(() => {
    (async () => {
      try {
        const { preferences } = await preferencesGet();
        setPrefs(preferences);
        hydrate(preferences);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load preferences.");
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  function toggleCondition(c: string) {
    setCondition((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setError(null);
    const fields: Partial<UserPreferences> = {
      preferred_brands: brands.split(",").map((s) => s.trim()).filter(Boolean),
      max_budget: budget ? parseFloat(budget) : null,
      preferred_stores: stores.split(",").map((s) => s.trim()).filter(Boolean),
      preferred_condition: condition,
      price_vs_quality: priceVsQuality ? parseFloat(priceVsQuality) : null,
      currency_code: currency || null,
      shopping_locale: locale || null,
    };
    try {
      const { preferences } = await preferencesUpdate(fields);
      setPrefs(preferences);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageContainer>
      <PageHeader
        title="Settings & preferences"
        description="Shopping and monitoring preferences that personalize PricePilot."
      />

      {!loaded ? (
        <div className="mt-6">
          <LoadingBlock lines={4} />
        </div>
      ) : null}

      {error ? (
        <div className="mt-4">
          <ErrorState title="Could not load preferences" description={error} />
        </div>
      ) : null}

      {loaded ? (
        <form onSubmit={save} className="mt-6 space-y-4">
          {/* Shopping preferences */}
          <Card>
            <CardHeader>
              <CardTitle>Shopping preferences</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="space-y-1">
                <Label htmlFor="brands" className="text-xs font-medium text-muted-foreground">
                  Preferred brands (comma-separated)
                </Label>
                <Input id="brands" value={brands} onChange={(e) => setBrands(e.target.value)} placeholder="e.g. Acme, Globex" />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="budget" className="text-xs font-medium text-muted-foreground">
                    Max budget (0 clears)
                  </Label>
                  <Input id="budget" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="e.g. 500" inputMode="decimal" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs font-medium text-muted-foreground">Currency</Label>
                  <Select value={currency || undefined} onValueChange={setCurrency}>
                    <SelectTrigger aria-label="Preferred currency" className="w-full">
                      <SelectValue placeholder="e.g. USD" />
                    </SelectTrigger>
                    <SelectContent>
                      {CURRENCIES.map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-1">
                <Label htmlFor="stores" className="text-xs font-medium text-muted-foreground">
                  Preferred stores (comma-separated)
                </Label>
                <Input id="stores" value={stores} onChange={(e) => setStores(e.target.value)} placeholder="e.g. Store A, Store B" />
              </div>

              <div>
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Preferred condition</span>
                <div className="flex flex-wrap gap-2">
                  {CONDITIONS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => toggleCondition(c)}
                      className={`rounded-full border px-3 py-1 text-xs ${condition.includes(c) ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label htmlFor="pvq" className="text-xs font-medium text-muted-foreground">
                    Price vs quality (0–1)
                  </Label>
                  <Input id="pvq" value={priceVsQuality} onChange={(e) => setPriceVsQuality(e.target.value)} placeholder="e.g. 0.7" inputMode="decimal" />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="locale" className="text-xs font-medium text-muted-foreground">
                    Shopping locale
                  </Label>
                  <Input id="locale" value={locale} onChange={(e) => setLocale(e.target.value)} placeholder="e.g. en-US" />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Monitoring preferences */}
          <Card>
            <CardHeader>
              <CardTitle>Monitoring & notifications</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-center justify-between rounded-md border p-3">
                <div>
                  <p className="font-medium">Email alert delivery</p>
                  <p className="text-xs text-muted-foreground">
                    Requires an SMTP provider to be configured server-side. Until then, alerts persist in-app only.
                  </p>
                </div>
                <Switch checked={emailAlerts} onCheckedChange={setEmailAlerts} aria-label="Email alert delivery" />
              </div>
              <p className="text-xs text-muted-foreground">
                Note: external email delivery is available only when the API has SMTP configured. In-app alerts always record.
              </p>
            </CardContent>
          </Card>

          {/* Account / session */}
          <Card>
            <CardHeader>
              <CardTitle>Account & session</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              <p className="text-muted-foreground">
                Authentication is deferred. Identity is a per-browser demo user (UUID) while real account auth is wired in a
                later phase. No account is created beyond your local preferences.
              </p>
            </CardContent>
          </Card>

          <div className="flex items-center gap-3">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save preferences"}
            </Button>
            {saved ? (
              <span className="inline-flex items-center gap-1 text-sm text-emerald-700" role="status">
                <CheckCircle2 aria-hidden className="h-4 w-4" /> Saved.
              </span>
            ) : null}
          </div>
        </form>
      ) : null}
    </PageContainer>
  );
}