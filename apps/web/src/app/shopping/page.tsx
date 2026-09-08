import { PageHeader } from "@/components/page-header";

export default function ShoppingPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="AI shopping assistant"
        description="Ask follow-up questions and refine your search over a live session."
        phase="Phase 4"
      />
      <p className="mt-2 text-sm text-muted-foreground">
        The multi-turn assistant relies on the agent graph and structured AI output
        (Phase 4). It will surface here when available.
      </p>
    </div>
  );
}