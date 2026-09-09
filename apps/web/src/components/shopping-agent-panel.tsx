"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { formatPrice } from "@/components/price";
import { SibtBadge } from "@/components/sibt-badge";
import { VoiceInput } from "@/components/voice-input";
import { ImageUpload } from "@/components/image-upload";
import { EmptyState, ErrorState, ProviderUnavailable, LoadingBlock } from "@/components/states";
import { ShoppingAgentProductCard } from "@/components/shopping-product-card";
import { Loader2, MessageSquare, Sparkles } from "lucide-react";
import { shoppingSearch, shoppingChat } from "@/lib/api";
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
      const data = mode === "chat" ? await shoppingChat(q, sessionId) : await shoppingSearch(q);
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

  const isUnavailable =
    view.kind === "result" && view.data.status === "provider_unavailable";

  return (
    <div className="space-y-4">
      {/* Mode + input */}
      <div className="space-y-3">
        <Tabs value={mode} onValueChange={(v) => setMode(v as "search" | "chat")}>
          <TabsList>
            <TabsTrigger value="search">
              <Sparkles aria-hidden className="mr-1.5 h-3.5 w-3.5" /> Search
            </TabsTrigger>
            <TabsTrigger value="chat">
              <MessageSquare aria-hidden className="mr-1.5 h-3.5 w-3.5" /> Chat
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <form onSubmit={run} className="flex flex-wrap items-center gap-2">
          <div className="min-w-[240px] flex-1">
            <label htmlFor="shopping-query" className="sr-only">
              Ask the shopping agent
            </label>
            <Input
              id="shopping-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                mode === "chat"
                  ? 'Try: "under 2 euros", "only sidi", "cheaper", "more results"'
                  : 'e.g. "good 55 inch Samsung TV under 700"'
              }
              className="h-12"
              aria-label="Ask the shopping agent"
            />
          </div>
          <VoiceInput onTranscript={handleTranscript} />
          <Button type="submit" size="lg" disabled={view.kind === "loading"}>
            {view.kind === "loading" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {mode === "chat" ? "Send" : "Ask PricePilot"}
          </Button>
        </form>

        <ImageUpload onResult={(data) => setView({ kind: "result", data })} />
      </div>

      {/* Conversation transcript (chat) */}
      {mode === "chat" && conversation.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Conversation</CardTitle>
          </CardHeader>
          <CardContent className="max-h-48 space-y-2 overflow-y-auto">
            {conversation.map((m, i) => (
              <div
                key={i}
                className={`text-sm ${m.role === "user" ? "text-right font-medium" : "text-muted-foreground"}`}
              >
                {m.text}
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {/* Loading skeletons */}
      {view.kind === "loading" ? (
        <Card>
          <CardContent className="p-6">
            <LoadingBlock lines={4} />
            <p className="mt-3 text-sm text-muted-foreground">
              Researching products, prices, reviews, and sellers — only real data is used.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {/* Error */}
      {view.kind === "error" ? (
        <div>
          <ErrorState title="The agent could not complete the request" description={view.message} />
        </div>
      ) : null}

      {/* Provider unavailable (honest) */}
      {isUnavailable ? (
        <div>
          <ProviderUnavailable description="The search provider could not supply results for this request. No products are displayed." />
        </div>
      ) : null}

      {/* Results */}
      {view.kind === "result" && !isUnavailable ? <AgentResults data={view.data} /> : null}
    </div>
  );
}

function AgentResults({ data }: { data: ShoppingAgentResponse }) {
  const products = data.products ?? [];
  const recs = data.recommendations ?? [];
  const noProducts = products.length === 0;
  const providerErrors = data.provider_errors ?? [];

  return (
    <div className="space-y-4">
      {/* Intent */}
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

      {/* Recommendation callout */}
      {data.answer ? (
        <Card className="border-primary/30 bg-primary/[0.03]">
          <CardContent className="flex items-start gap-3 p-6">
            <Sparkles className="mt-0.5 h-5 w-5 text-primary" aria-hidden />
            <div>
              <p className="font-medium">Recommendation</p>
              <p className="mt-1 text-sm text-muted-foreground">{data.answer}</p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Refinements (chat) */}
      {data.refinements?.length ? (
        <Card>
          <CardContent className="space-y-1 p-4 text-xs text-muted-foreground">
            {data.refinements.map((r, i) => (
              <p key={i}>understood: {r.note}</p>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {/* Semantic status */}
      {data.semantic ? (
        <p className="text-xs text-muted-foreground">
          semantic search: <strong>{data.semantic}</strong>{" "}
          {data.semantic === "keyword"
            ? "— embeddings not configured (falling back to keyword matching)"
            : ""}
        </p>
      ) : null}

      {/* Provider errors / warnings */}
      {data.warnings?.length || providerErrors.length ? (
        <Card>
          <CardContent className="space-y-1 p-4 text-xs text-muted-foreground">
            {providerErrors.map((w, i) => (
              <p key={`pe-${i}`}>provider: {w}</p>
            ))}
            {data.warnings?.map((w, i) => (
              <p key={`w-${i}`}>• {w}</p>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {/* Empty (no products, no provider errors) */}
      {noProducts && providerErrors.length === 0 ? (
        <div>
          <EmptyState
            title="No products were returned"
            description="The search provider may be rate-limited or returned no results for this query."
          />
        </div>
      ) : null}

      {/* Products */}
      {products.length > 0 ? (
        <div className="space-y-3">
          {products.slice(0, 8).map((p) => {
            const rec = recs.find((r) => r.product_id === p.canonical_product_id);
            const deal = data.deal_scores?.[p.canonical_product_id];
            const price = data.price_analysis?.[p.canonical_product_id];
            const seller = data.seller_analysis?.[p.canonical_product_id];
            const review = data.review_analysis?.[p.canonical_product_id];
            const sibt = data.sibt?.[p.canonical_product_id];
            const forecast = data.forecasts?.[p.canonical_product_id];
            return (
              <ShoppingAgentProductCard
                key={p.canonical_product_id}
                product={p}
                recommendation={rec}
                deal={deal}
                price={price}
                seller={seller}
                review={review}
                sibt={sibt}
                forecast={forecast}
              />
            );
          })}
        </div>
      ) : null}
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

export function formatShoppingPrice(v: number | null | undefined): string {
  return v != null ? formatPrice(v) : "—";
}