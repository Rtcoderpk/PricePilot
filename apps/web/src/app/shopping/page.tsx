import { PageHeader } from "@/components/page-header";
import { ShoppingAgentPanel } from "@/components/shopping-agent-panel";

export default function ShoppingPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <PageHeader
        title="AI shopping assistant"
        description="Tell PricePilot what you want; it researches providers, analyzes price/seller/reviews, and ranks an explainable recommendation."
      />
      <div className="mt-6">
        <ShoppingAgentPanel />
      </div>
    </div>
  );
}