import { PageContainer } from "@/components/container";
import { PageHeader } from "@/components/page-header";
import { SupplierResearchPanel } from "@/components/supplier-research-panel";

export default function ResearchPage() {
  return (
    <PageContainer>
      <PageHeader
        title="Product research"
        description="Upload a product photo, speak, or type what you need. PricePilot searches real suppliers, verifies results, and recommends the best option."
      />
      <div className="mt-6">
        <SupplierResearchPanel />
      </div>
    </PageContainer>
  );
}