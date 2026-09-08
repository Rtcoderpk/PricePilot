import { PageHeader } from "@/components/page-header";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="Settings & preferences"
        description="Brands, budget, preferred stores, condition, and price-vs-quality weighting."
        phase="Auth deferred"
      />
      <p className="mt-2 text-sm text-muted-foreground">
        Preferences and profiles require user accounts (auth lands after Phase 1).
      </p>
    </div>
  );
}