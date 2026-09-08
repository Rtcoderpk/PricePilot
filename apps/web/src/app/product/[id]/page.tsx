import { PageHeader } from "@/components/page-header";

export const dynamic = "force-dynamic";

export default async function ProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title={`Product #${id.slice(0, 12)}`}
        description="Product detail — offers, price history, reviews, seller intelligence, and BUY/WAIT/AVOID."
        phase="Phase 2+"
      />
      <p className="mt-2 text-sm text-muted-foreground">
        The full product detail surface (offers across stores, total cost, price history,
        review intelligence, BUY/WAIT/AVOID) is built out in Phase 2–4. Live provider
        results are available from the{" "}
        <a className="underline" href="/search?q=nutella">
          search page
        </a>
        .
      </p>
    </div>
  );
}