"use client";

import { useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatPrice } from "@/components/price";
import { VoiceInput } from "@/components/voice-input";
import { EmptyState, ErrorState } from "@/components/states";
import { LiveAgentConsole } from "@/components/live-agent-console";
import { ImagePlus, Sparkles, Trophy, Tag, Star, ExternalLink, ShieldCheck, CheckCircle, ShoppingBag, Building2 } from "lucide-react";
import { researchText, researchRoute, researchImage } from "@/lib/api";
import type {
  ResearchResponse,
  ResearchSupplier,
  ResearchComparisonOption,
} from "@/lib/api";

type Mode = "retail" | "wholesale";

type ViewState =
  | { kind: "idle" }
  | { kind: "loading"; stage: number }
  | { kind: "result"; data: ResearchResponse }
  | { kind: "error"; message: string };

export function SupplierResearchPanel() {
  const [view, setView] = useState<ViewState>({ kind: "idle" });
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("wholesale");
  const [quantity, setQuantity] = useState<string>("");
  const [destination, setDestination] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function simulateProgressAndRun(fetcher: () => Promise<ResearchResponse>) {
    setBusy(true);
    setView({ kind: "loading", stage: 0 });

    const timer1 = setTimeout(() => setView({ kind: "loading", stage: 1 }), 300);
    const timer2 = setTimeout(() => setView({ kind: "loading", stage: 2 }), 700);
    const timer3 = setTimeout(() => setView({ kind: "loading", stage: 3 }), 1200);
    const timer4 = setTimeout(() => setView({ kind: "loading", stage: 4 }), 1600);

    try {
      const data = await fetcher();
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
      setView({ kind: "result", data });
    } catch (err) {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
      setView({ kind: "error", message: err instanceof Error ? err.message : "Research failed." });
    } finally {
      setBusy(false);
    }
  }

  function buildFullPrompt(baseText: string): string {
    const parts = [baseText];
    if (mode === "wholesale") {
      parts.push("wholesale bulk supplier");
    } else {
      parts.push("retail buy 1 store");
    }
    if (quantity) parts.push(`quantity ${quantity}`);
    if (destination) parts.push(`in ${destination}`);
    return parts.join(" ");
  }

  async function onTextSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || busy) return;
    const fullText = buildFullPrompt(q);
    simulateProgressAndRun(() => researchText(fullText));
  }

  async function onVoice(text: string) {
    if (!text || busy) return;
    setQuery(text);
    const fullText = buildFullPrompt(text);
    simulateProgressAndRun(() => researchRoute(fullText, "voice"));
  }

  async function onImageFile(file: File | undefined) {
    if (!file || busy) return;
    simulateProgressAndRun(() => researchImage(file));
  }

  return (
    <div className="space-y-6">
      {/* Mode Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-card/60 p-4 shadow-sm backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant={mode === "retail" ? "default" : "outline"}
            className="h-10 px-4 text-xs font-semibold"
            onClick={() => setMode("retail")}
          >
            <ShoppingBag className="mr-1.5 h-3.5 w-3.5" /> Retail — Buy 1 / Small Quantity
          </Button>
          <Button
            type="button"
            variant={mode === "wholesale" ? "default" : "outline"}
            className="h-10 px-4 text-xs font-semibold"
            onClick={() => setMode("wholesale")}
          >
            <Building2 className="mr-1.5 h-3.5 w-3.5" /> Wholesale — Bulk / Business Purchase
          </Button>
        </div>
        <Badge variant="outline" className="text-xs">
          Mode: <span className="ml-1 uppercase font-bold text-primary">{mode}</span>
        </Badge>
      </div>

      {/* Input area */}
      <Card className="border-primary/20 bg-card/60 backdrop-blur-sm shadow-md">
        <CardContent className="space-y-4 p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold tracking-tight">AI Product & Supplier Console</h2>
            <Badge variant="outline" className="text-xs">Live Multi-Search Engine</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Upload an image, record voice, or enter any product request (laptops, GPUs, clothing, tools, wholesale).
          </p>

          <form onSubmit={onTextSubmit} className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-[260px] flex-1">
                <label htmlFor="research-query" className="sr-only">Product request</label>
                <Input
                  id="research-query"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={mode === "wholesale" ? 'e.g. "ASUS RTX 4070 12GB GPU 50 units"' : 'e.g. "MacBook Pro M3 16GB"'}
                  className="h-12 text-sm bg-background/80"
                />
              </div>
              <VoiceInput onTranscript={onVoice} />
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-12 w-12"
                onClick={() => fileRef.current?.click()}
                title="Upload product image"
                aria-label="Upload product image"
              >
                <ImagePlus className="h-5 w-5" />
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => onImageFile(e.target.files?.[0])}
              />
              <Button type="submit" className="h-12 px-6 font-medium" disabled={busy || !query.trim()}>
                <Sparkles className="mr-2 h-4 w-4" /> Research Product
              </Button>
            </div>

            {/* Additional Intent Parameters */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 pt-2 border-t text-xs">
              <div>
                <label className="text-muted-foreground font-medium mb-1 block">Quantity (Units)</label>
                <Input
                  type="number"
                  placeholder="e.g. 100"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
              <div>
                <label className="text-muted-foreground font-medium mb-1 block">Destination Country</label>
                <Input
                  type="text"
                  placeholder="e.g. Pakistan or USA"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Real-time Agent Console */}
      {view.kind === "loading" ? (
        <LiveAgentConsole activeStageIndex={view.stage} />
      ) : null}

      {view.kind === "error" ? (
        <ErrorState title="Could not complete research" description={view.message} />
      ) : null}

      {view.kind === "idle" && !busy ? (
        <EmptyState
          title="Autonomous AI Product Research Engine"
          description="Select Retail or Wholesale mode, upload a photo, speak, or type to query real live search engines and verified page evidence."
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
    <div className="space-y-6">
      {data.notice ? (
        <p className="text-xs text-muted-foreground bg-muted/40 p-3 rounded-lg border">{data.notice}</p>
      ) : null}

      {/* Product identified */}
      {data.product_understanding ? (
        <Card className="border-border/60">
          <CardTitle className="px-6 pt-5 text-base font-semibold">Product Intelligence Summary</CardTitle>
          <CardContent className="p-6 pt-2 text-sm text-muted-foreground flex flex-wrap gap-4">
            {Object.entries(data.product_understanding)
              .filter(([k, v]) => v && typeof v !== "object")
              .map(([k, v]) => (
                <div key={k} className="rounded-md border bg-muted/30 px-3 py-1.5 text-xs">
                  <span className="text-muted-foreground capitalize">{k.replace("_", " ")}: </span>
                  <strong className="text-foreground">{String(v)}</strong>
                </div>
              ))}
          </CardContent>
        </Card>
      ) : null}

      {noResults ? (
        <EmptyState
          title="Insufficient Live Data"
          description="No verified supplier or product results were retrieved for this request. PricePilot never fabricates products or suppliers."
        />
      ) : (
        <>
          {/* 3 Core Dominant Recommendation Winners */}
          {rec ? <DominantWinners rec={rec} data={data} /> : null}

          {/* Supplier Results Table */}
          <div className="space-y-3">
            <h3 className="text-lg font-semibold tracking-tight">Retrieved Supplier Sources ({data.suppliers.length})</h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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

function DominantWinners({
  rec,
  data,
}: {
  rec: NonNullable<ResearchResponse["recommendation"]>;
  data: ResearchResponse;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold tracking-tight flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" /> AI Recommendation Winners
        </h3>
        {rec.confidence ? (
          <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20">
            Confidence Score: {Math.round(rec.confidence * 100)}%
          </Badge>
        ) : null}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {/* BEST SUPPLIER */}
        <Card className="border-amber-500/40 bg-gradient-to-b from-amber-500/10 to-transparent relative overflow-hidden shadow-md">
          <CardContent className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-500 flex items-center gap-1.5">
                <Trophy className="h-4 w-4" /> Best Supplier
              </span>
              <Badge variant="warning" className="text-[10px]">VERIFIED</Badge>
            </div>
            {rec.best_supplier ? (
              <>
                <h4 className="font-semibold text-base line-clamp-1">{rec.best_supplier.supplier || "Verified Supplier"}</h4>
                <p className="text-xs text-muted-foreground line-clamp-2">{rec.best_supplier.product}</p>
                <div className="pt-2 border-t flex items-center justify-between text-sm">
                  <span className="font-bold text-foreground">
                    {rec.best_supplier.unit_price != null ? formatPrice(rec.best_supplier.unit_price, rec.best_supplier.currency) : "Price on request"}
                  </span>
                  {rec.best_supplier.url ? (
                    <a
                      href={rec.best_supplier.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary font-medium flex items-center gap-1 hover:underline"
                    >
                      Source <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Insufficient supplier data</p>
            )}
          </CardContent>
        </Card>

        {/* CHEAPEST VERIFIED */}
        <Card className="border-emerald-500/40 bg-gradient-to-b from-emerald-500/10 to-transparent relative overflow-hidden shadow-md">
          <CardContent className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-500 flex items-center gap-1.5">
                <Tag className="h-4 w-4" /> Cheapest Verified
              </span>
              <Badge variant="success" className="text-[10px]">LOWEST PRICE</Badge>
            </div>
            {rec.cheapest_option ? (
              <>
                <h4 className="font-semibold text-base line-clamp-1">{rec.cheapest_option.supplier || "Supplier"}</h4>
                <p className="text-xs text-muted-foreground line-clamp-2">{rec.cheapest_option.product}</p>
                <div className="pt-2 border-t flex items-center justify-between text-sm">
                  <span className="font-bold text-emerald-500">
                    {rec.cheapest_option.unit_price != null ? formatPrice(rec.cheapest_option.unit_price, rec.cheapest_option.currency) : "n/a"}
                  </span>
                  {rec.cheapest_option.url ? (
                    <a
                      href={rec.cheapest_option.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary font-medium flex items-center gap-1 hover:underline"
                    >
                      Source <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Insufficient price data</p>
            )}
          </CardContent>
        </Card>

        {/* BEST VALUE */}
        <Card className="border-blue-500/40 bg-gradient-to-b from-blue-500/10 to-transparent relative overflow-hidden shadow-md">
          <CardContent className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-500 flex items-center gap-1.5">
                <Star className="h-4 w-4" /> Best Value
              </span>
              <Badge variant="info" className="text-[10px]">OPTIMAL MATCH</Badge>
            </div>
            {rec.best_value ? (
              <>
                <h4 className="font-semibold text-base line-clamp-1">{rec.best_value.supplier || "Supplier"}</h4>
                <p className="text-xs text-muted-foreground line-clamp-2">{rec.best_value.product}</p>
                <div className="pt-2 border-t flex items-center justify-between text-sm">
                  <span className="font-bold text-foreground">
                    {rec.best_value.unit_price != null ? formatPrice(rec.best_value.unit_price, rec.best_value.currency) : "n/a"}
                  </span>
                  {rec.best_value.url ? (
                    <a
                      href={rec.best_value.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary font-medium flex items-center gap-1 hover:underline"
                    >
                      Source <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Insufficient match data</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Reasoning list */}
      {rec.reasoning?.length ? (
        <Card className="bg-muted/20 border-border/40">
          <CardContent className="p-4 space-y-1.5 text-xs text-muted-foreground">
            <p className="font-semibold text-foreground text-xs uppercase tracking-wide">Why These Won:</p>
            {rec.reasoning.map((r, i) => (
              <p key={i} className="flex items-start gap-1.5">
                <CheckCircle className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
                <span>{r}</span>
              </p>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
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
  const badgeVariant =
    verification?.state === "verified"
      ? ("success" as const)
      : verification?.state === "partially_verified"
        ? ("warning" as const)
        : ("secondary" as const);

  return (
    <Card className="hover:border-primary/40 transition-colors shadow-sm">
      <CardContent className="flex flex-col justify-between h-full p-5 space-y-3 text-sm">
        <div className="space-y-1.5">
          <div className="flex items-start justify-between gap-2">
            <span className="font-semibold line-clamp-1">{s.supplier || "Supplier"}</span>
            <Badge variant={badgeVariant} className="text-[10px]">
              {verification?.state ?? "unverified"}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground line-clamp-2">{s.product || s.title}</p>
        </div>

        <div className="space-y-2 pt-2 border-t text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Price:</span>
            <strong className="text-foreground">
              {s.price != null ? formatPrice(s.price, s.currency) : "Not available"}
            </strong>
          </div>
          {s.moq != null ? (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">MOQ:</span>
              <span>{s.moq} units</span>
            </div>
          ) : null}
          {s.availability ? (
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Availability:</span>
              <span className="capitalize">{s.availability.replace("_", " ")}</span>
            </div>
          ) : null}

          {(flags?.is_cheapest || flags?.is_best_value || flags?.is_best_supplier) ? (
            <div className="flex flex-wrap gap-1 pt-1">
              {flags.is_cheapest ? <Badge variant="success" className="text-[10px]">Cheapest</Badge> : null}
              {flags.is_best_value ? <Badge variant="info" className="text-[10px]">Best Value</Badge> : null}
              {flags.is_best_supplier ? <Badge variant="warning" className="text-[10px]">Best Supplier</Badge> : null}
            </div>
          ) : null}
        </div>

        {s.url ? (
          <a
            href={s.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-primary font-medium hover:underline pt-1"
          >
            <ShieldCheck className="h-3.5 w-3.5" /> View Verified Source <ExternalLink className="h-3 w-3" />
          </a>
        ) : null}
      </CardContent>
    </Card>
  );
}
