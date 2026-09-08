"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SearchForm({ initialQuery = "" }: { initialQuery?: string }) {
  const router = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(false);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    router.push(`/search?q=${encodeURIComponent(q)}`);
    setLoading(false);
  }

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-xl gap-2">
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder='e.g. "best laptop for AI development under $1000"'
        className="h-12"
        aria-label="Search products"
        disabled={loading}
      />
      <Button type="submit" size="lg" disabled={loading} aria-label="Search">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
        <span className="sr-only">Search</span>
      </Button>
    </form>
  );
}