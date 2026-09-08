"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { preferencesGet, preferencesUpdate } from "@/lib/api";
import type { UserPreferences } from "@/lib/api";

const CONDITIONS = ["new", "refurbished", "any"];

export default function SettingsPage() {
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // local form state
  const [brands, setBrands] = useState("");
  const [budget, setBudget] = useState("");
  const [stores, setStores] = useState("");
  const [condition, setCondition] = useState<string[]>([]);
  const [priceVsQuality, setPriceVsQuality] = useState("");
  const [currency, setCurrency] = useState("");
  const [locale, setLocale] = useState("");

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
    // fetch-on-mount only
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
    <div className="mx-auto max-w-3xl px-4 py-10">
      <PageHeader
        title="Settings & preferences"
        description="Brands, budget, preferred stores, condition, and price-vs-quality weighting."
      />

      {!loaded ? <p className="mt-6 text-sm text-muted-foreground">Loading…</p> : null}
      {error ? (
        <Card className="mt-4 border-destructive/40">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}
      {loaded && !prefs ? (
        <Card className="mt-4">
          <CardContent className="p-6 text-sm text-muted-foreground">
            No preferences saved yet. These settings personalize shopping recommendations.
          </CardContent>
        </Card>
      ) : null}

      <form onSubmit={save} className="mt-6 space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Preferences</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">Preferred brands (comma-separated)</span>
              <Input value={brands} onChange={(e) => setBrands(e.target.value)} placeholder="e.g. Acme, Globex" />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Max budget (0 clears)</span>
                <Input value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="e.g. 500" inputMode="decimal" />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Currency code</span>
                <Input value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="e.g. USD" maxLength={3} />
              </label>
            </div>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">Preferred stores (comma-separated)</span>
              <Input value={stores} onChange={(e) => setStores(e.target.value)} placeholder="e.g. Store A, Store B" />
            </label>
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
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Price vs quality (0–1)</span>
                <Input
                  value={priceVsQuality}
                  onChange={(e) => setPriceVsQuality(e.target.value)}
                  placeholder="e.g. 0.7"
                  inputMode="decimal"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-muted-foreground">Shopping locale</span>
                <Input value={locale} onChange={(e) => setLocale(e.target.value)} placeholder="e.g. en-US" />
              </label>
            </div>
          </CardContent>
        </Card>

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save preferences"}
          </Button>
          {saved ? <span className="text-sm text-muted-foreground">Saved.</span> : null}
        </div>
      </form>
    </div>
  );
}