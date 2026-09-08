"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ProductImage } from "@/components/product-image";
import { BestPrice, formatPrice } from "@/components/price";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { ProductResult } from "@/lib/types";

interface ProductCardProps {
  product: ProductResult;
  onCompare?: (id: string) => void;
  hasFixtures?: boolean;
}

export function ProductCard({ product, onCompare, hasFixtures }: ProductCardProps) {
  const [compareOpen, setCompareOpen] = useState(false);
  const { offers, price_insight, is_fixture, variant, match_method, match_confidence } = product;
  const best = price_insight?.current ?? null;
  const priced = offers.filter((o) => o.price_amount != null);
  const providers = [...new Set(offers.map((o) => o.data_source || o.provider))];

  const variantLabel = variant?.quantity_unit
    ? ` (${variant.quantity_unit})`
    : variant?.quantity
      ? ` (${variant.quantity})`
      : variant?.color
        ? ` (${String(variant.color)})`
        : "";

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
        <div className="flex flex-wrap items-center gap-2">
          <BestPrice price={price_insight} />
          {providers.length > 0 && (
            <Badge variant="secondary">
              {providers.length} store{providers.length > 1 ? "s" : ""}
            </Badge>
          )}
          {hasFixtures || is_fixture ? (
            <Badge variant="warning">demo data</Badge>
          ) : (
            <Badge variant="outline">{offers[0]?.provider ?? "provider"}</Badge>
          )}
        </div>

        {priced.length > 1 ? (
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
            {offers.map((o, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span className="truncate">{o.provider || o.data_source}</span>
                <span className="font-medium">
                  {o.price_amount != null ? formatPrice(o.price_amount, o.price_currency) : "no price"}
                </span>
              </li>
            ))}
          </ul>
        )}

        {match_method && match_method !== "provider" && (
          <p className="text-[10px] text-muted-foreground">
            grouped by: {match_method}
            {match_confidence != null ? ` · ${Math.round(match_confidence * 100)}%` : ""}
          </p>
        )}

        <div className="mt-auto flex items-center gap-2">
          {onCompare ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onCompare(product.canonical_product_id)}
            >
              Compare
            </Button>
          ) : null}
          {offers[0]?.url ? (
            <Button size="sm" variant="outline" asChild>
              <a href={offers[0].url} target="_blank" rel="noopener noreferrer">
                View product
              </a>
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}