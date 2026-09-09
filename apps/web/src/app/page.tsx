import Link from "next/link";
import { ArrowRight, Search, Sparkles, Scale, CheckCircle2 } from "lucide-react";
import { Container } from "@/components/container";
import { SearchForm } from "@/components/search-form";

const WORKFLOW = [
  { icon: Search, title: "Tell us", desc: "Describe what you want — budget, brand, specs, use case." },
  { icon: Sparkles, title: "Research", desc: "We query real providers and analyze offers, prices, and reviews." },
  { icon: Scale, title: "Compare", desc: "One product, every store, side-by-side — best price and total cost." },
  { icon: CheckCircle2, title: "Decide", desc: "An explainable BUY / WAIT / AVOID recommendation with reasons." },
];

const FEATURES = [
  {
    title: "AI shopping",
    desc: "Natural-language requests with budgets, brands, and specs — we do the research.",
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
    desc: "Current vs historical averages, lowest-known, and honest trend analytics.",
  },
  {
    title: "Price alerts",
    desc: "Trigger when a tracked product drops to your target — never fabricated.",
  },
  {
    title: "Monitoring",
    desc: "Real observations collected over time power history, charts, and alerts.",
  },
];

export default function Home() {
  return (
    <Container className="py-12 sm:py-16">
      {/* Hero */}
      <section className="flex flex-col items-center gap-6 py-8 text-center sm:py-12">
        <span className="inline-flex items-center gap-2 rounded-full border bg-secondary/50 px-3 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles aria-hidden className="h-3.5 w-3.5 text-primary" />
          Autonomous AI shopping agent
        </span>
        <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
          Tell PricePilot what you want to buy.
        </h1>
        <p className="max-w-xl text-lg text-muted-foreground">
          It researches products, compares stores, analyzes prices and reviews, and gives
          you an explainable recommendation.
        </p>
        <div className="w-full max-w-xl">
          <SearchForm />
        </div>
        <p className="text-xs text-muted-foreground">
          Try:{" "}
          <Link href="/search?q=nutella" className="underline underline-offset-2">
            nutella
          </Link>{" "}
          ·{" "}
          <Link href="/search?q=olive+oil" className="underline underline-offset-2">
            olive oil
          </Link>
        </p>
      </section>

      {/* Workflow */}
      <section aria-label="How PricePilot works" className="py-8">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {WORKFLOW.map((step, i) => (
            <div key={step.title} className="relative flex flex-col items-start gap-3 rounded-lg border bg-card p-5">
              <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
                <step.icon aria-hidden className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold">
                  <span className="mr-1.5 text-muted-foreground">{i + 1}.</span>
                  {step.title}
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Example request:{" "}
          <Link href="/shopping" className="font-medium text-primary underline underline-offset-2">
            “Find me the best 256GB camera”
          </Link>
        </p>
      </section>

      {/* Features */}
      <section aria-label="Features" className="py-8">
        <h2 className="text-xl font-semibold tracking-tight">Everything you need to buy right</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-lg border bg-card p-6">
              <h3 className="font-semibold">{f.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="py-8 text-center">
        <Link
          href="/shopping"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Sparkles aria-hidden className="h-4 w-4" />
          Try the AI shopping assistant
          <ArrowRight aria-hidden className="h-4 w-4" />
        </Link>
      </section>
    </Container>
  );
}