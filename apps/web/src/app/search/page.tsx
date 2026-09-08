import { notFound } from "next/navigation";
import { SearchForm } from "@/components/search-form";
import { ProductCard } from "@/components/product-card";
import { CompareBar } from "@/components/compare-bar";
import { Badge } from "@/components/ui/badge";
import { AlertCircle } from "lucide-react";
import { ApiError, searchProducts } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

interface SearchPageProps {
  searchParams: Promise<{ q?: string }>;
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const { q } = await searchParams;
  const query = (q ?? "").trim();
  if (!query) notFound();

  let data: SearchResponse;
  let error: { code: string; message: string } | null = null;

  try {
    data = await searchProducts(query);
  } catch (e) {
    if (e instanceof ApiError) {
      error = { code: e.code, message: e.message };
    } else {
      error = { code: "network", message: "Could not reach the PricePilot API." };
    }
    return (
      <div className="mx-auto max-w-6xl px-4 py-10">
        <SearchForm initialQuery={query} />
        <div className="mt-10 flex flex-col items-center gap-2 rounded-lg border border-dashed p-10 text-center">
          <AlertCircle className="h-8 w-8 text-destructive" />
          <p className="font-medium">{error.message}</p>
          <p className="text-sm text-muted-foreground">
            {error.code === "provider_unavailable"
              ? "The search provider is not configured. Add a provider to get results."
              : "Please try again in a moment."}
          </p>
        </div>
      </div>
    );
  }

  const hasFixtures = data.products.some((p) => p.is_fixture);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8 flex flex-col items-center gap-3">
        <SearchForm initialQuery={query} />
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          {data.total} result{data.total === 1 ? "" : "s"} ·{" "}
          {data.providers.map((p) => (
            <Badge key={p.name} variant={p.availability === "available" ? "secondary" : "destructive"}>
              {p.name}: {p.availability}
            </Badge>
          ))}
        </div>
        {data.notice ? <p className="text-xs text-muted-foreground">{data.notice}</p> : null}
      </div>

      {data.products.length === 0 ? (
        <div className="mt-10 flex flex-col items-center gap-2 rounded-lg border border-dashed p-10 text-center">
          <p className="font-medium">No products found</p>
          <p className="text-sm text-muted-foreground">
            {data.notice ?? "Try a different search term."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.products.map((p) => (
            <ProductCard key={p.canonical_product_id} product={p} hasFixtures={hasFixtures} />
          ))}
        </div>
      )}

      <CompareBar ids={data.products.slice(0, 3).map((p) => p.canonical_product_id)} />
    </div>
  );
}