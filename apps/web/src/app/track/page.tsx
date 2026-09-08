import { PageHeader } from "@/components/page-header";

export default function TrackPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Tracked products"
        description="Watch products and monitor their prices over time."
        phase="Phase 5"
      />
      <p className="mt-2 text-sm text-muted-foreground">
        Price tracking, price lists, and alerts are planned for Phase 5 (worker + Redis).
        Nothing is tracked yet.
      </p>
    </div>
  );
}