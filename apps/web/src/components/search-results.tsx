"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ProductCard } from "@/components/product-card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/states";
import type { SearchResponse, ProductResult } from "@/lib/types";

type SortKey = "relevance" | "price_asc" | "price_desc";

function priceOf(p: ProductResult): number {
  return p.price_insight?.current ?? Number.POSITIVE_INFINITY;
}

export function SearchResults({ data, hasFixtures }: { data: SearchResponse; hasFixtures: boolean }) {
  const [sort, setSort] = useState<SortKey>("relevance");
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);

  function toggleSelected(id: string) {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 4) return prev;
      return [...prev, id];
    });
  }

  const products = useMemo(() => {
    let list = [...data.products];
    if (onlyAvailable) {
      list = list.filter((p) => p.offers.some((o) => o.price_amount != null));
    }
    if (sort === "price_asc") list.sort((a, b) => priceOf(a) - priceOf(b));
    else if (sort === "price_desc") list.sort((a, b) => priceOf(b) - priceOf(a));
    return list;
  }, [data.products, sort, onlyAvailable]);

  return (
    <div>
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>
            {data.total} result{data.total === 1 ? "" : "s"}
          </span>
          {data.providers.map((p) => (
            <Badge key={p.name} variant={p.availability === "available" ? "secondary" : "destructive"}>
              {p.name}: {p.availability}
            </Badge>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={onlyAvailable ? "default" : "outline"}
            onClick={() => setOnlyAvailable((v) => !v)}
          >
            Available only
          </Button>
          <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
            <SelectTrigger aria-label="Sort results" className="h-9 w-40 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="relevance">Relevance</SelectItem>
              <SelectItem value="price_asc">Price: low → high</SelectItem>
              <SelectItem value="price_desc">Price: high → low</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {data.notice ? <p className="mt-3 text-xs text-muted-foreground">{data.notice}</p> : null}

      {/* Results */}
      {products.length === 0 ? (
        <div className="mt-8">
          <EmptyState
            title={data.products.length === 0 ? "No products found" : "No products match the current filters"}
            description={
              data.products.length === 0
                ? data.notice ?? "Try a different search term."
                : "Try clearing the 'Available only' filter."
            }
          />
        </div>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => (
            <ProductCard
              key={p.canonical_product_id}
              product={p}
              hasFixtures={hasFixtures}
              selected={selected.includes(p.canonical_product_id)}
              onToggleCompare={toggleSelected}
            />
          ))}
        </div>
      )}

      {/* Floating compare bar */}
      {selected.length >= 1 ? (
        <div className="fixed bottom-20 left-1/2 z-40 -translate-x-1/2 rounded-lg border bg-card p-3 shadow-lg md:bottom-6">
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {selected.length} selected {selected.length > 1 ? "(max 4)" : "— select up to 4"}
            </span>
            {selected.length > 1 ? (
              <Button size="sm" asChild>
                <Link href={`/compare?ids=${selected.map(encodeURIComponent).join(",")}`}>Compare</Link>
              </Button>
            ) : null}
            <Button size="sm" variant="ghost" onClick={() => setSelected([])}>
              Clear
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}