import { PageHeader } from "@/components/page-header";

export const dynamic = "force-dynamic";

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ ids?: string }>;
}) {
  const { ids } = await searchParams;
  const idList = (ids ?? "").split(",").filter(Boolean).slice(0, 4);
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Compare products"
        description="Side-by-side comparison of price, total cost, specs, reviews, seller, and an AI recommendation."
        phase="Phase 4"
      />
      {idList.length > 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          Comparing {idList.length} product(s): comparison engine lands in Phase 4.
        </p>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">
          Select products from a search to compare them here.
        </p>
      )}
    </div>
  );
}