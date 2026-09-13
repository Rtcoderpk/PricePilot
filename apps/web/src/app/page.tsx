import Link from "next/link";
import { ArrowRight, Search, Sparkles, Scale, CheckCircle2, ShieldCheck, Cpu, Layers } from "lucide-react";
import { Container } from "@/components/container";
import { SearchForm } from "@/components/search-form";
import { Hero3D } from "@/components/hero-3d";

const WORKFLOW = [
  { icon: Search, title: "Query or Upload", desc: "Upload a photo, speak, or type any product (laptops, GPUs, clothing, wholesale)." },
  { icon: Sparkles, title: "AI Multi-Search", desc: "Autonomous agent searches public retailers, wholesale platforms, and B2B directories." },
  { icon: Scale, title: "Canonical Match", desc: "Identifies equivalent models, landed prices, MOQs, and verifies supplier evidence." },
  { icon: CheckCircle2, title: "3 Core Winners", desc: "Outputs Best Supplier 🏆, Cheapest Verified 💰, and Best Value ⭐ with sources." },
];

const FEATURES = [
  {
    title: "Autonomous Product Research",
    desc: "Understands specs, models, brands, and categories across any physical product.",
  },
  {
    title: "Multi-Category Search",
    desc: "Queries retail stores, marketplaces, wholesale suppliers, and manufacturers in parallel.",
  },
  {
    title: "Zero Fake Data",
    desc: "Only retrieves real, live prices and suppliers with direct verifiable source URLs.",
  },
  {
    title: "Supplier Trust Scoring",
    desc: "Evaluates supplier evidence, URL validity, availability, and business history.",
  },
  {
    title: "Land Price Analysis",
    desc: "Calculates total landed cost, currency consistency, and bulk quantity discounts.",
  },
  {
    title: "Live Agent Pipeline",
    desc: "Watch the AI agent progress through image vision, search, matching, and scoring.",
  },
];

export default function Home() {
  return (
    <div className="relative overflow-hidden">
      <Hero3D />

      <Container className="py-12 sm:py-16">
        {/* Hero */}
        <section className="flex flex-col items-center gap-6 py-8 text-center sm:py-14">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 text-xs font-semibold text-primary backdrop-blur-md">
            <Sparkles aria-hidden className="h-3.5 w-3.5" />
            Autonomous AI Product & Supplier Research Engine
          </div>
          <h1 className="max-w-4xl text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl bg-gradient-to-r from-foreground via-foreground/90 to-muted-foreground bg-clip-text text-transparent">
            Real-Time AI Shopping & Wholesale Intelligence.
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground">
            PricePilot understands any product request, searches verified retail & wholesale suppliers,
            matches canonical products, and delivers 3 core evidence-backed recommendations.
          </p>
          <div className="w-full max-w-2xl mt-2 shadow-2xl rounded-2xl border border-primary/20 bg-card/70 p-2 backdrop-blur-lg">
            <SearchForm />
          </div>
          <div className="flex flex-wrap justify-center gap-2 text-xs text-muted-foreground mt-2">
            <span>Popular searches:</span>
            <Link href="/research" className="font-medium text-primary underline underline-offset-2">
              ASUS RTX 4070 GPU
            </Link>{" "}
            ·{" "}
            <Link href="/research" className="font-medium text-primary underline underline-offset-2">
              MacBook Pro M3
            </Link>{" "}
            ·{" "}
            <Link href="/research" className="font-medium text-primary underline underline-offset-2">
              Wholesale Nike Shoes
            </Link>
          </div>
        </section>

        {/* Workflow */}
        <section aria-label="How PricePilot works" className="py-10">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {WORKFLOW.map((step, i) => (
              <div key={step.title} className="relative flex flex-col items-start gap-3 rounded-xl border border-border/60 bg-card/50 p-6 backdrop-blur-sm shadow-sm hover:border-primary/40 transition-colors">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <step.icon aria-hidden className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-base">
                    <span className="mr-1.5 text-primary/80">0{i + 1}.</span>
                    {step.title}
                  </h3>
                  <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Features */}
        <section aria-label="Features" className="py-10">
          <div className="text-center space-y-2 mb-8">
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Engineered for Verifiable Product Intelligence</h2>
            <p className="text-sm text-muted-foreground">Every recommendation is backed by real live source links and evidence.</p>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-xl border border-border/50 bg-card/40 p-6 backdrop-blur-sm">
                <h3 className="font-semibold text-base flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
                  {f.title}
                </h3>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="py-12 text-center">
          <Link
            href="/research"
            className="inline-flex items-center gap-2.5 rounded-lg bg-primary px-8 py-3.5 text-base font-semibold text-primary-foreground shadow-xl transition-all hover:bg-primary/90 hover:scale-105"
          >
            <Sparkles aria-hidden className="h-5 w-5" />
            Launch AI Product Research Lab
            <ArrowRight aria-hidden className="h-5 w-5" />
          </Link>
        </section>
      </Container>
    </div>
  );
}
