"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatPrice, BestPrice } from "@/components/price";
import { SibtBadge } from "@/components/sibt-badge";
import { CheckCircle2, CircleSlash, Info } from "lucide-react";
import type { ProductResult, Recommendation, NonProductDetail, SibtDetail, ForecastDetail } from "@/lib/types";

interface Props {
  product: ProductResult;
  recommendation?: Recommendation | null;
  deal?: NonProductDetail | null;
  price?: NonProductDetail | null;
  seller?: NonProductDetail | null;
  review?: NonProductDetail | null;
  sibt?: SibtDetail | null;
  forecast?: ForecastDetail | null;
}

/** Verified vs insufficient label. Never claims data exists when it doesn't. */
function VerifiedLabel({ verified }: { verified: boolean }) {
  return verified ? (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-700">
      <CheckCircle2 aria-hidden className="h-3 w-3" /> verified
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium text-muted-foreground">
      <CircleSlash aria-hidden className="h-3 w-3" /> insufficient/unavailable
    </span>
  );
}

export function ShoppingAgentProductCard({
  product,
  recommendation,
  deal,
  price,
  seller,
  review,
  sibt,
  forecast,
}: Props) {
  const best = price?.lowest_offer ?? product.price_insight?.current ?? null;
  const currency = price?.currency ?? product.price_insight?.currency ?? "USD";
  const hasDeal = deal?.score != null;
  const hasReview = Boolean(review?.status === "available");
  const hasSeller = Boolean(seller?.label && seller.label !== "insufficient_data");
  const hasPrice = Boolean(price?.price_position && price.price_position !== "insufficient_history");
  const hasForecast = Boolean(forecast?.status === "available");

  return (
    <Card>
      <CardContent className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <SibtBadge sibt={sibt} />
              <h3 className="font-semibold">{product.name}</h3>
              {recommendation && !recommendation.matches_hard_constraints ? (
                <Badge variant="warning">outside budget</Badge>
              ) : null}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {product.variant?.quantity_unit ? `pack: ${product.variant.quantity_unit}` : product.category ?? product.brand}
            </p>
          </div>
          <div className="text-right">
            <BestPrice
            price={
              product.price_insight ?? {
                current: best,
                lowest_90d: null,
                avg_90d: null,
                sample_count: 0,
                currency,
              }
            }
          />
            {hasDeal ? (
              <Badge variant="success" className="mt-1">
                Deal Score {Math.round(deal!.score!)} · {deal!.label}
              </Badge>
            ) : (
              <Badge variant="secondary" className="mt-1">
                insufficient data
              </Badge>
            )}
          </div>
        </div>

        {/* SIBT reasons */}
        {sibt && sibt.reasons.length > 0 ? (
          <ul className="mt-3 space-y-1 rounded-md border bg-muted/20 p-2 text-xs text-muted-foreground">
            {sibt.reasons.map((r, i) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        ) : null}

        {/* Recommendation reasons */}
        {recommendation?.reasons?.length ? (
          <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
            {recommendation.reasons.map((r, i) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        ) : null}

        <Separator className="my-3" />

        {/* Evidence grid — every cell labeled verified or insufficient */}
        <dl className="grid gap-x-6 gap-y-2 text-xs text-muted-foreground sm:grid-cols-2">
          <EvidenceRow label="Price" verified={hasPrice}>
            {hasPrice ? price!.price_position : "insufficient history"}
            <VerifiedLabel verified={hasPrice} />
          </EvidenceRow>
          <EvidenceRow label="Seller" verified={hasSeller}>
            {hasSeller ? seller!.label : "insufficient data"}
            <VerifiedLabel verified={hasSeller} />
          </EvidenceRow>
          <EvidenceRow label="Reviews" verified={hasReview}>
            {hasReview ? `${review!.review_count ?? 0} reviews` : "unavailable"}
            <VerifiedLabel verified={hasReview} />
          </EvidenceRow>
          <EvidenceRow label="Forecast" verified={hasForecast}>
            {hasForecast && forecast!.forecast_next != null
              ? `${formatPrice(forecast!.forecast_next)} (${formatPrice(forecast!.lower_bound ?? 0)}–${formatPrice(forecast!.upper_bound ?? 0)})`
              : forecast?.status === "insufficient_history"
                ? "insufficient history"
                : "unavailable"}
            <VerifiedLabel verified={hasForecast} />
          </EvidenceRow>
        </dl>

        {/* Offers */}
        {product.offers.length > 0 ? (
          <div className="mt-3 grid gap-1 rounded-md border bg-muted/30 p-2 text-xs">
            {product.offers.map((o, i) => (
              <div key={i} className="flex items-center justify-between gap-2">
                <span className="truncate">{o.provider || o.data_source}</span>
                <span>{o.price_amount != null ? formatPrice(o.price_amount, o.price_currency) : "no price"}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 flex items-center gap-1 text-xs text-muted-foreground">
            <Info aria-hidden className="h-3 w-3" /> No offers returned.
          </p>
        )}

        <div className="mt-3 flex justify-end">
          <Link
            href={`/product/${product.canonical_product_id}`}
            className="text-xs font-medium text-primary underline underline-offset-2"
          >
            View detail →
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

function EvidenceRow({ label, verified, children }: { label: string; verified: boolean; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0">{label}</dt>
      <dd className="flex flex-wrap items-center justify-end gap-1.5 text-right font-medium text-foreground">
        {children}
      </dd>
    </div>
  );
}