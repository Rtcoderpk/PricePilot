import { PageHeader } from "@/components/page-header";

export default function AlertsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Price alerts"
        description="Get notified when a product hits your target price or drops a percentage."
        phase="Phase 5"
      />
      <p className="mt-2 text-sm text-muted-foreground">
        Creating alerts requires tracked products and the alert worker (Phase 5).
      </p>
    </div>
  );
}