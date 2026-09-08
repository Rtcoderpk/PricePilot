import { PageHeader } from "@/components/page-header";

export default function HistoryPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Price history"
        description="Charts of recorded prices for tracked products — only data that actually exists."
        phase="Phase 5"
      />
      <p className="mt-2 text-sm text-muted-foreground">
        History requires the platform&apos;s own price polling over time (Phase 5). No
        fabricated history is shown.
      </p>
    </div>
  );
}