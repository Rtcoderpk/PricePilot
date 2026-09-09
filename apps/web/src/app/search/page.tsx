import { notFound } from "next/navigation";
import { PageContainer } from "@/components/container";
import { SearchForm } from "@/components/search-form";
import { SearchResults } from "@/components/search-results";
import { ErrorState } from "@/components/states";
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

  let data: SearchResponse | null = null;
  let error: { code: string; message: string } | null = null;

  try {
    data = await searchProducts(query);
  } catch (e) {
    if (e instanceof ApiError) {
      error = { code: e.code, message: e.message };
    } else {
      error = { code: "network", message: "Could not reach the PricePilot API." };
    }
  }

  return (
    <PageContainer>
      <div className="mb-4 flex flex-col items-center gap-3">
        <SearchForm initialQuery={query} />
      </div>

      {error ? (
        <div className="mt-6">
          <ErrorState
            title={error.message}
            description={
              error.code === "provider_unavailable"
                ? "The search provider is not configured. Add a provider to get results."
                : "Please try again in a moment."
            }
          />
        </div>
      ) : data ? (
        <SearchResults data={data} hasFixtures={data.products.some((p) => p.is_fixture)} />
      ) : null}
    </PageContainer>
  );
}