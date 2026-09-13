"use client";

import { CheckCircle2, Loader2, Sparkles, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export type AgentStage = {
  id: string;
  label: string;
  status: "pending" | "active" | "completed" | "failed";
  details?: string;
};

const STAGES: Omit<AgentStage, "status">[] = [
  { id: "understanding", label: "Product Understanding & Vision" },
  { id: "search_retail", label: "Searching Retail Sources" },
  { id: "search_suppliers", label: "Searching Wholesale & Suppliers" },
  { id: "matching", label: "Canonical Product Matching" },
  { id: "verification", label: "Verifying Supplier Trust & Evidence" },
  { id: "recommendation", label: "Calculating Core Recommendations" },
];

export function LiveAgentConsole({ activeStageIndex }: { activeStageIndex: number }) {
  return (
    <div className="rounded-xl border border-primary/20 bg-card/80 p-5 shadow-lg backdrop-blur-md">
      <div className="flex items-center justify-between border-b pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary animate-pulse" />
          <h3 className="font-semibold text-sm tracking-wide">
            Autonomous AI Agent Pipeline
          </h3>
        </div>
        <Badge variant="outline" className="text-xs bg-primary/10 text-primary border-primary/30">
          REAL-TIME EXECUTION
        </Badge>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {STAGES.map((s, idx) => {
          const isCompleted = idx < activeStageIndex;
          const isActive = idx === activeStageIndex;
          return (
            <div
              key={s.id}
              className={`flex items-center gap-3 rounded-lg border p-3 text-xs transition-all ${
                isActive
                  ? "border-primary bg-primary/5 text-foreground shadow-sm"
                  : isCompleted
                  ? "border-muted bg-muted/20 text-muted-foreground"
                  : "border-border/40 text-muted-foreground/60 opacity-60"
              }`}
            >
              {isCompleted ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              ) : isActive ? (
                <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
              ) : (
                <div className="h-4 w-4 rounded-full border border-muted-foreground/30 shrink-0" />
              )}
              <div className="font-medium truncate">{s.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
