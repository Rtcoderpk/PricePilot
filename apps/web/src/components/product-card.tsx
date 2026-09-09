"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ProductImage } from "@/components/product-image";
import { BestPrice, formatPrice } from "@/components/price";
import { PriceChange } from "@/components/price-change";
import { ChevronDown, ChevronUp, ExternalLink, Scale, ShoppingCart, Star, TrendingDown } from "lucide-react";
import type { ProductResult } from "@/lib/types";

interface ProductCardProps {
  product: ProductResult;
  onCompare?: (id: string) => void;
  /** multi-select compare mode used on /search */
  selected?: boolean;
  onToggleCompare?: (id: string) => void;
  hasFixtures?: boolean;
}

export function ProductCard({ product, onCompare, selected, onToggleCompare, hasFixtures }: ProductCardProps) {
  const [compareOpen, setCompareOpen] = useState(false);
  const { offers, price_insight, is_fixture, variant, match_method, match_confidence } = product;
  const best = price_insight?.current ?? null;
  const priced = offers.filter((o) => o.price_amount != null);
  const pricedSorted = [...priced].sort((a, b) => (a.price_amount ?? 0) - (b.price_amount ?? 0));
  const second = pricedSorted[1]?.price_amount ?? null;
  const providers = [...new Set(offers.map((o) => o.data_source || o.provider))];
  const minOffer = pricedSorted[0]?.price_amount ?? null;
  const maxOffer = pricedSorted.length > 1 ? pricedSorted[pricedSorted.length - 1].price_amount : null;

  const variantLabel = variant?.quantity_unit
    ? ` (${variant.quantity_unit})`
    : variant?.quantity
      ? ` (${variant.quantity})`
      : variant?.color
        ? ` (${String(variant.color)})`
        : "";

  const showCompare = priced.length > 1;
  const isDemo = hasFixtures || is_fixture;

  return (
    <Card className="flex h-full flex-col transition-shadow hover:shadow-md">
      <CardHeader className="flex-row items-start gap-4 space-y-0">
        <ProductImage src={product.image_url} alt={product.name} />
        <div className="min-w-0 flex-1">
          <CardTitle className="line-clamp-2 text-base">
            {product.name}
            {variantLabel}
          </CardTitle>
          <CardDescription className="mt-1 line-clamp-2">
            {product.brand ?? product.category ?? "—"}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        {/* Price + badge row */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <BestPrice price={price_insight} />
          <div className="flex flex-wrap items-center gap-1.5">
            {providers.length > 0 ? (
              <Badge variant="secondary">
                {providers.length} store{providers.length > 1 ? "s" : ""}
              </Badge>
            ) : null}
            {isDemo ? <Badge variant="warning">demo data</Badge> : null}
          </div>
        </div>

        {/* Price range (when multiple real offers) */}
        {showCompare && minOffer != null ? (
          <p className="text-xs text-muted-foreground">
            Range: {formatPrice(minOffer, price_insight?.currency)}{" "}
            {maxOffer != null && maxOffer !== minOffer ? <>– {formatPrice(maxOffer, price_insight?.currency)}</> : null}
            {second != null && second !== minOffer ? (
              <span className="ml-2 inline-flex items-center gap-1 text-emerald-700">
                <TrendingDown aria-hidden className="h-3 w-3" /> save{" "}
                {formatPrice((price_insight?.current ?? second) - minOffer, price_insight?.currency)}
              </span>
            ) : null}
          </p>
        ) : null}

        {/* Price trend from real history (if available) */}
        {price_insight?.sample_count != null && price_insight.sample_count >= 2 ? (
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            Price trend:
            <PriceChange
              current={price_insight.current}
              previous={price_insight.avg_90d}
            />
            <span className="text-[10px]">(vs 90d avg)</span>
          </p>
        ) : null}

        {/* Compare stores toggle */}
        {showCompare ? (
          <button
            type="button"
            onClick={() => setCompareOpen((v) => !v)}
            className="flex items-center gap-1 text-xs font-medium text-primary"
            aria-expanded={compareOpen}
          >
            {compareOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {compareOpen ? "Hide prices" : "Compare stores"}
          </button>
        ) : null}

        {compareOpen && (
          <ul className="space-y-1 rounded-md border bg-muted/30 p-2 text-xs">
            {pricedSorted.map((o, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span className="truncate">{o.provider || o.data_source}</span>
                <span className="font-medium">
                  {o.price_amount != null ? formatPrice(o.price_amount, o.price_currency) : "no price"}
                </span>
              </li>
            ))}
          </ul>
        )}

        {match_method && match_method !== "provider" ? (
          <p className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Star aria-hidden className="h-3 w-3" />
            grouped by: {match_method}
            {match_confidence != null ? ` · ${Math.round(match_confidence * 100)}%` : ""}
          </p>
        ) : null}

        {/* Actions */}
        <div className="mt-auto flex items-center gap-2 pt-2">
          {onToggleCompare ? (
            <Button
              size="sm"
              variant={selected ? "default" : "outline"}
              onClick={() => onToggleCompare(product.canonical_product_id)}
            >
              <Scale aria-hidden className="mr-1 h-3 w-3" /> {selected ? "Selected" : "Compare"}
            </Button>
          ) : onCompare ? (
            <Button size="sm" variant="outline" onClick={() => onCompare(product.canonical_product_id)}>
              <Scale aria-hidden className="mr-1 h-3 w-3" /> Compare
            </Button>
          ) : null}
          {offers[0]?.url ? (
            <Button size="sm" variant="outline" asChild>
              <a href={offers[0].url} target="_blank" rel="noopener noreferrer">
                <ExternalLink aria-hidden className="mr-1 h-3 w-3" /> View
              </a>
            </Button>
          ) : null}
          <Button size="sm" variant="ghost" asChild>
            <a href={`/product/${product.canonical_product_id}`}>
              <ShoppingCart aria-hidden className="mr-1 h-3 w-3" /> Details
            </a>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}