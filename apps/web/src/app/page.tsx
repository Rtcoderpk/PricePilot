import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { SearchForm } from "@/components/search-form";

const features = [
  {
    title: "AI shopping",
    desc: "Tell PricePilot what you want — budgets, brands, specs — it does the research.",
  },
  {
    title: "Price comparison",
    desc: "Offers from searched stores on one card, so you see who's cheapest.",
  },
  {
    title: "BUY / WAIT / AVOID",
    desc: "An explainable recommendation over real price/review/seller signals.",
  },
  {
    title: "Price intelligence",
    desc: "Current vs historical averages, lowest-known, discount analysis.",
  },
  {
    title: "Review intelligence",
    desc: "Theme extraction from permitted review sources, never fabricated.",
  },
  {
    title: "Price alerts",
    desc: "Trigger when a tracked product drops to your target.",
  },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-16">
      <section className="flex flex-col items-center gap-6 py-12 text-center">
        <Badge variant="secondary" className="mb-2">
          Autonomous AI shopping agent
        </Badge>
        <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
          Tell PricePilot what you want to buy.
        </h1>
        <p className="max-w-xl text-lg text-muted-foreground">
          It researches products, compares stores, analyzes prices and reviews, and gives
          you an explainable recommendation.
        </p>
        <SearchForm />
        <p className="text-xs text-muted-foreground">
          Try:{" "}
          <Link href="/search?q=nutella" className="underline">
            nutella
          </Link>{" "}
          ·{" "}
          <Link href="/search?q=olive+oil" className="underline">
            olive oil
          </Link>
        </p>
      </section>

      <section className="grid gap-4 py-8 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((f) => (
          <Card key={f.title}>
            <CardContent className="p-6">
              <h3 className="font-semibold">{f.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{f.desc}</p>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}