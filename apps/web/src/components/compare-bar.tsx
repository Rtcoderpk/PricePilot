"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export function CompareBar({ ids }: { ids: string[] }) {
  if (ids.length < 2) return null;
  const href = `/compare?ids=${ids.map(encodeURIComponent).join(",")}`;
  return (
    <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg border bg-card p-3 shadow-lg">
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{ids.length} selected</span>
        <Button size="sm" asChild>
          <Link href={href}>Compare</Link>
        </Button>
      </div>
    </div>
  );
}