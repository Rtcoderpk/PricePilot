"use client";

import { useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatPrice } from "@/components/price";
import { VoiceInput } from "@/components/voice-input";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/states";
import { Upload, ImagePlus, Sparkles } from "lucide-react";
import { researchText, researchRoute, researchImage } from "@/lib/api";
import type {
  ResearchResponse,
  ResearchSupplier,
  ResearchComparisonOption,
} from "@/lib/api";

const PROGRESS = [
  "Understanding product…",
  "Searching suppliers…",
  "Verifying results…",
  "Comparing prices…",
  "Preparing recommendation…",
];

type ViewState =
  | { kind: "idle" }
  | { kind: "loading"; stage: number }
  | { kind: "result"; data: ResearchResponse }
  | { kind: "error"; message: string };

export function SupplierResearchPanel() {
  const [view, setView] = useState<ViewState>({ kind: "idle" });
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function setLoading(stage = 0) {
    setView({ kind: "loading", stage });
  }

  async function onTextSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || busy) return;
    setBusy(true);
    setLoading(0);
    try {
      const data = await researchText(q);
      setView({ kind: "result", data });
    } catch (err) {
      setView({ kind: "error", message: err instanceof Error ? err.message : "Research failed." });
    } finally {
      setBusy(false);
    }
  }

  async function onVoice(text: string) {
    if (!text || busy) return;
    setQuery(text);
    setBusy(true);
    setLoading(0);
    try {
      const data = await researchRoute(text, "voice");
      setView({ kind: "result", data });
    } catch (err) {
      setView({ kind: "error", message: err instanceof Error ? err.message : "Voice research failed." });
    } finally {
      setBusy(false);
    }
  }

  async function onImageFile(file: File | undefined) {
    if (!file || busy) return;
    setBusy(true);
    setLoading(0);
    try {
      const data = await researchImage(file);
      setView({ kind: "result", data });
    } catch (err) {
      setView({ kind: "error", message: err instanceof Error ? err.message : "Image research failed." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Input area */}
      <Card>
        <CardContent className="space-y-3 p-5">
          <p className="text-sm text-muted-foreground">
            Upload a product photo, speak, or type what you&apos;re looking for.
          </p>
          <form onSubmit={onTextSubmit} className="flex flex-wrap items-center gap-2">
            <div className="min-w-[220px] flex-1">
              <label htmlFor="research-query" className="sr-only">Product request</label>
              <Input
                id="research-query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder='e.g. "100 black Nike running shoes from wholesale suppliers"'
                className="h-11"
              />
            </div>
            <VoiceInput onTranscript={onVoice} />
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => fileRef.current?.click()}
              title="Upload product image"
              aria-label="Upload product image"
            >
              <ImagePlus className="h-4 w-4" />
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => onImageFile(e.target.files?.[0])}
            />
            <Button type="submit" disabled={busy || !query.trim()}>
              <Sparkles className="mr-1 h-4 w-4" /> Research
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Loading — honest progress */}
      {view.kind === "loading" ? (
        <Card>
          <CardContent className="space-y-2 p-6">
            <LoadingBlock lines={3} />
            <p className="text-sm text-muted-foreground">{PROGRESS[view.stage]}</p>
          </CardContent>
        </Card>
      ) : null}

      {view.kind === "error" ? (
        <ErrorState title="Could not complete the research" description={view.message} />
      ) : null}

      {view.kind === "idle" && !busy ? (
        <EmptyState
          title="Tell PricePilot what you need — text, voice, or a photo"
          description="It will search real suppliers, verify results, compare options, and recommend the best/cheapest/best-value."
        />
      ) : null}

      {view.kind === "result" ? <Results data={view.data} /> : null}
    </div>
  );
}

function Results({ data }: { data: ResearchResponse }) {
  const rec = data.recommendation;
  const noResults = !data.suppliers || data.suppliers.length === 0;

  return (
    <div className="space-y-4">
      {data.notice ? (
        <p className="text-xs text-muted-foreground">{data.notice}</p>
      ) : null}

      {/* Product understood */}
      {data.product_understanding ? (
        <Card>
          <CardTitle className="px-5 pt-4 text-base">Product identified</CardTitle>
          <CardContent className="text-sm text-muted-foreground">
            {Object.entries(data.product_understanding)
              .filter(([k, v]) => v && typeof v !== "object")
              .slice(0, 8)
              .map(([k, v]) => (
                <span key={k} className="mr-3 inline-flex items-center gap-1">
                  <span>{k}:</span> <strong>{String(v)}</strong>
                </span>
              ))}
          </CardContent>
        </Card>
      ) : null}

      {/* Eng directory */}
      {noResults ? (
        <EmptyState
          title="No verified results found"
          description="No supplier/product data was retrieved for this request. Only real retrieved data is shown — nothing is fabricated."
        />
      ) : (
        <>
          {/* Recommendation */}
          {rec ? <Recommendation rec={rec} data={data} /> : null}

          {/* Supplier results */}
          <div>
            <h3 className="mb-2 text-base font-semibold">Suppliers found ({data.suppliers.length})</h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.suppliers.map((s, i) => (
                <SupplierCard key={i} s={s} verification={data.verifications[i]} flags={data.comparison[i]} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Recommendation({ rec, data }: { rec: NonNullable<ResearchResponse["recommendation"]>; data: ResearchResponse }) {
  const rows: Array<{ label: string; opt?: ResearchComparisonOption | null; emoji: string }> = [
    { label: "Best Supplier", opt: rec.best_supplier, emoji: "🏆" },
    { label: "Cheapest", opt: rec.cheapest_option, emoji: "💰" },
    { label: "Best Value", opt: rec.best_value, emoji: "⭐" },
  ];
  return (
    <Card className="border-primary/30">
      <CardContent className="space-y-3 p-5">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <h3 className="text-base font-semibold">Recommendation</h3>
          {rec.confidence ? <Badge variant="secondary">confidence {Math.round(rec.confidence * 100)}%</Badge> : null}
        </div>
        {rows.map(({ label, opt, emoji }) => (
          <div key={label}>
            <p className="text-sm font-medium">{emoji} {label}</p>
            {opt ? (
              <p className="mt-0.5 text-sm text-muted-foreground">
                {opt.supplier || opt.product || "option"} ·{" "}
                {opt.unit_price != null ? formatPrice(opt.unit_price, opt.currency) : "price n/a"} ·
                MOQ {opt.moq ?? "n/a"} · {opt.verification}
                {opt.url ? (
                  <a href={opt.url} target="_blank" rel="noopener noreferrer" className="ml-1 underline">
                    source
                  </a>
                ) : null}
              </p>
            ) : (
              <p className="mt-0.5 text-sm text-muted-foreground">Not available</p>
            )}
          </div>
        ))}
        {rec.reasoning?.length ? (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {rec.reasoning.map((r, i) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        ) : null}
        {data.currency_conflict ? (
          <p className="text-xs text-amber-600">Prices are in different currencies and were not directly compared.</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function SupplierCard({
  s,
  verification,
  flags,
}: {
  s: ResearchSupplier;
  verification?: { state: string };
  flags?: ResearchComparisonOption;
}) {
  const badge =
    verification?.state === "verified"
      ? ("success" as const)
      : verification?.state === "partially_verified"
        ? ("warning" as const)
        : ("secondary" as const);
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 p-4 text-sm">
        <div className="flex items-start justify-between gap-2">
          <span className="font-medium">{s.supplier || s.product || s.title}</span>
          <Badge variant={badge}>{verification?.state ?? "unverified"}</Badge>
        </div>
        <p className="text-xs text-muted-foreground">{s.product || s.title}</p>
        <p>
          Price:{" "}
          <strong>{s.price != null ? formatPrice(s.price, s.currency) : "Not available"}</strong>
          {s.moq != null ? <span className="ml-2 text-xs">MOQ {s.moq}</span> : null}
        </p>
        {(flags?.is_cheapest || flags?.is_best_value || flags?.is_best_supplier) ? (
          <div className="flex flex-wrap gap-1">
            {flags.is_cheapest ? <Badge variant="success">cheapest</Badge> : null}
            {flags.is_best_value ? <Badge variant="info">best value</Badge> : null}
            {flags.is_best_supplier ? <Badge variant="warning">best supplier</Badge> : null}
          </div>
        ) : null}
        {s.availability ? <p className="text-xs text-muted-foreground">Availability: {s.availability}</p> : null}
        {s.url ? (
          <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-xs text-primary underline underline-offset-2">
            View product (source)
          </a>
        ) : null}
      </CardContent>
    </Card>
  );
}