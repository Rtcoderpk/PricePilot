import { PageHeader } from "@/components/page-header";

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Dashboard"
        description="Tracked products, price drops, active alerts, recent searches, recommended deals."
        phase="Phase 6"
      />
      <p className="mt-2 text-sm text-muted-foreground">
        The personalized dashboard lands in Phase 6, once tracking, alerts, and
        recommendations exist.
      </p>
    </div>
  );
}