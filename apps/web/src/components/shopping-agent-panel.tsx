"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatPrice } from "@/components/price";
import { Loader2, MessageSquare, Search, Sparkles } from "lucide-react";
import { shoppingSearch, shoppingChat } from "@/lib/api";
import { VoiceInput } from "@/components/voice-input";
import { ImageUpload } from "@/components/image-upload";
import { SibtBadge } from "@/components/sibt-badge";
import type { ShoppingAgentResponse } from "@/lib/types";

type ViewState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "result"; data: ShoppingAgentResponse }
  | { kind: "error"; message: string };

export function ShoppingAgentPanel() {
  const [view, setView] = useState<ViewState>({ kind: "idle" });
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"search" | "chat">("search");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [conversation, setConversation] = useState<Array<{ role: string; text: string }>>([]);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setView({ kind: "loading" });
    try {
      const data =
        mode === "chat" ? await shoppingChat(q, sessionId) : await shoppingSearch(q);
      if (mode === "chat") {
        setSessionId(data.session_id ?? undefined);
        if (data.conversation?.length) setConversation(data.conversation);
      }
      setView({ kind: "result", data });
    } catch (err) {
      setView({
        kind: "error",
        message: err instanceof Error ? err.message : "Could not reach the PricePilot agent.",
      });
    }
  }

  function handleTranscript(text: string) {
    setQuery(text);
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button
          size="sm"
          variant={mode === "search" ? "default" : "outline"}
          onClick={() => setMode("search")}
        >
          <Search className="mr-1 h-3 w-3" /> Search
        </Button>
        <Button
          size="sm"
          variant={mode === "chat" ? "default" : "outline"}
          onClick={() => setMode("chat")}
        >
          <MessageSquare className="mr-1 h-3 w-3" /> Chat
        </Button>
      </div>

      <form onSubmit={run} className="flex max-w-2xl gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            mode === "chat"
              ? 'Try: "under 2 euros", "only sidi", "cheaper", "more results"'
              : 'e.g. "good 55 inch Samsung TV under 700"'
          }
          className="h-12 flex-1 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Ask the shopping agent"
        />
        <VoiceInput onTranscript={handleTranscript} />
        <Button type="submit" size="lg" disabled={view.kind === "loading"}>
          {view.kind === "loading" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {mode === "chat" ? "Send" : "Ask PricePilot"}
        </Button>
      </form>

      <ImageUpload onResult={(data) => setView({ kind: "result", data })} />

      {mode === "chat" && conversation.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Conversation</CardTitle>
          </CardHeader>
          <CardContent className="max-h-48 space-y-2 overflow-y-auto">
            {conversation.map((m, i) => (
              <div key={i} className={`text-sm ${m.role === "user" ? "text-right font-medium" : "text-muted-foreground"}`}>
                {m.text}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {view.kind === "loading" ? (
        <Card>
          <CardContent className="flex items-center gap-3 p-6 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            Researching products, prices, reviews, and sellers…
          </CardContent>
        </Card>
      ) : null}

      {view.kind === "error" ? (
        <Card className="border-destructive/40">
          <CardContent className="p-6 text-sm text-destructive">{view.message}</CardContent>
        </Card>
      ) : null}

      {view.kind === "result" ? <AgentResults data={view.data} /> : null}
    </div>
  );
}

function AgentResults({ data }: { data: ShoppingAgentResponse }) {
  const products = data.products ?? [];
  const recs = data.recommendations ?? [];
  const noProducts = products.length === 0;

  return (
    <div className="space-y-4">
      {data.intent ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Interpreted intent</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <IntentChips intent={data.intent} />
          </CardContent>
        </Card>
      ) : null}

      {data.answer ? (
        <Card className="border-primary/30">
          <CardContent className="flex items-start gap-3 p-6">
            <Sparkles className="mt-0.5 h-5 w-5 text-primary" />
            <div>
              <p className="font-medium">Recommendation</p>
              <p className="mt-1 text-sm text-muted-foreground">{data.answer}</p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {data.refinements?.length ? (
        <Card>
          <CardContent className="space-y-0.5 p-6 text-xs text-muted-foreground">
            {data.refinements.map((r, i) => (
              <p key={i}>understood: {r.note}</p>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {data.semantic ? (
        <p className="text-xs text-muted-foreground">
          semantic search: <strong>{data.semantic}</strong>{" "}
          {data.semantic === "keyword" ? "— embeddings not configured (falling back to keyword matching)" : ""}
        </p>
      ) : null}

      {data.warnings?.length ? (
        <Card>
          <CardContent className="space-y-1 p-6 text-xs text-muted-foreground">
            {data.warnings.map((w, i) => (
              <p key={i}>• {w}</p>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {noProducts ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            No products were returned — the search provider may be rate-limited or returned no
            results for this query.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {products.slice(0, 8).map((p) => {
            const rec = recs.find((r) => r.product_id === p.canonical_product_id);
            const deal = data.deal_scores?.[p.canonical_product_id];
            const price = data.price_analysis?.[p.canonical_product_id];
            const seller = data.seller_analysis?.[p.canonical_product_id];
            const review = data.review_analysis?.[p.canonical_product_id];
            const sibt = data.sibt?.[p.canonical_product_id];
            const forecast = data.forecasts?.[p.canonical_product_id];
            const best = price?.lowest_offer ?? p.price_insight?.current ?? null;
            return (
              <Card key={p.canonical_product_id}>
                <CardContent className="p-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <SibtBadge sibt={sibt} />
                        <h3 className="font-semibold">{p.name}</h3>
                        {rec && !rec.matches_hard_constraints ? (
                          <Badge variant="warning">outside budget</Badge>
                        ) : null}
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {p.variant?.quantity_unit
                          ? `pack: ${p.variant.quantity_unit}`
                          : p.category ?? p.brand}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-semibold">
                        {best != null
                          ? formatPrice(best, price?.currency ?? rec?.currency ?? undefined)
                          : "no price"}
                      </p>
                      {deal?.score != null ? (
                        <Badge variant="success" className="mt-1">
                          Deal Score {Math.round(deal.score)} · {deal.label}
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="mt-1">
                          insufficient data
                        </Badge>
                      )}
                    </div>
                  </div>

                  {sibt ? (
                    <ul className="mt-3 space-y-1 rounded-md border bg-muted/20 p-2 text-xs text-muted-foreground">
                      {sibt.reasons.map((r, i) => (
                        <li key={i}>• {r}</li>
                      ))}
                    </ul>
                  ) : null}

                  {rec?.reasons?.length ? (
                    <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                      {rec.reasons.map((r, i) => (
                        <li key={i}>• {r}</li>
                      ))}
                    </ul>
                  ) : null}

                  {p.offers.length > 0 ? (
                    <div className="mt-3 grid gap-1 rounded-md border bg-muted/30 p-2 text-xs">
                      {p.offers.map((o, i) => (
                        <div key={i} className="flex items-center justify-between gap-2">
                          <span className="truncate">{o.provider || o.data_source}</span>
                          <span>
                            {o.price_amount != null ? formatPrice(o.price_amount, o.price_currency) : "no price"}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  <Separator className="my-3" />
                  <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
                    <span>
                      seller: <strong>{seller?.label ?? "insufficient_data"}</strong>
                    </span>
                    <span>
                      price: <strong>{price?.price_position ?? "insufficient_history"}</strong>
                    </span>
                    <span>
                      reviews:{" "}
                      <strong>
                        {review?.status === "available"
                          ? `${review.review_count ?? 0} reviews`
                          : "unavailable"}
                      </strong>
                    </span>
                    {forecast && forecast.status === "available" ? (
                      <span>
                        forecast:{" "}
                        <strong>
                          {forecast.forecast_next != null ? formatPrice(forecast.forecast_next) : "—"} ({formatPrice(forecast.lower_bound ?? 0)}–{formatPrice(forecast.upper_bound ?? 0)})
                        </strong>
                      </span>
                    ) : null}
                    {forecast && forecast.status === "insufficient_history" ? (
                      <span>
                        forecast: <strong>insufficient history</strong>
                      </span>
                    ) : null}
                    {deal?.components ? (
                      <span>components: {Object.values(deal.components).slice(0, 3).map((v) => Number(v).toFixed(0)).join(" / ")}</span>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function IntentChips({ intent }: { intent: NonNullable<ShoppingAgentResponse["intent"]> }) {
  const chips: Array<{ label: string; value?: string | number | null }> = [
    { label: "category", value: intent.category },
    { label: "brands", value: intent.brands?.join(", ") },
    { label: "budget", value: intent.budget_max != null ? `≤ ${intent.budget_max}` : undefined },
    { label: "currency", value: intent.currency },
    { label: "use case", value: intent.use_case },
    { label: "condition", value: intent.condition },
    { label: "urgency", value: intent.urgency },
    { label: "required", value: intent.required_features?.join(", ") },
    { label: "preferred", value: intent.preferred_features?.join(", ") },
  ].filter((c) => c.value);

  if (!chips.length) {
    return <p className="text-muted-foreground">Nothing specific was detected — staying broad.</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((c) => (
        <Badge key={c.label} variant="secondary">
          {c.label}: {c.value}
        </Badge>
      ))}
    </div>
  );
}