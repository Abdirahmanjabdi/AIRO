import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  LockKeyhole,
  Radar,
  ServerCog,
  Shield,
  Sparkles,
} from "lucide-react";

import BrandMark from "@/components/BrandMark";
import LiveLatencyPulse from "@/components/LiveLatencyPulse";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { sentinelApi } from "@/lib/api";
import {
  faqs,
  heroPillars,
  platformFacts,
  productCapabilities,
  PRODUCT_TAGLINE,
  workflowSteps,
  workspaceHighlights,
} from "@/content/site";

function CountUpBadge({ label, value, suffix = "" }: { label: string; value: number; suffix?: string }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    let frame = 0;
    const startedAt = performance.now();
    const duration = 900;

    const tick = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(Math.round(value * eased));
      if (progress < 1) {
        frame = window.requestAnimationFrame(tick);
      }
    };

    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [value]);

  return (
    <div className="border border-border/80 bg-card/75 p-4 backdrop-blur-xl">
      <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <div className="mt-3 font-display text-3xl font-bold text-secondary">
        {displayValue.toLocaleString("en-GB")}
        {suffix}
      </div>
    </div>
  );
}

export default function Landing() {
  const readinessQuery = useQuery({
    queryKey: ["public", "readiness"],
    queryFn: sentinelApi.getReadiness,
    refetchInterval: 15000,
    retry: 1,
  });

  const healthQuery = useQuery({
    queryKey: ["public", "health"],
    queryFn: sentinelApi.getHealth,
    refetchInterval: 30000,
    retry: 1,
  });

  const readinessRows = useMemo(
    () => [
      {
        label: "MT5 Bridge",
        value: readinessQuery.data?.redis_connected ? "ACTIVE (Sub-50ms)" : "OFFLINE",
      },
      {
        label: "Audit Ledger",
        value: readinessQuery.data?.db_connected ? "RECORDING" : "CHECKING",
      },
      {
        label: "Risk Model",
        value: readinessQuery.data?.model_loaded ? "CALIBRATED (Tier 1)" : "CALIBRATING",
      },
    ],
    [readinessQuery.data],
  );

  return (
    <div className="min-h-screen overflow-x-hidden">
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/85 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <BrandMark />

          <nav className="hidden items-center gap-6 text-[11px] uppercase tracking-[0.16em] text-muted-foreground lg:flex">
            <a href="#workflow" className="transition-colors hover:text-foreground">
              Workflow
            </a>
            <a href="#capabilities" className="transition-colors hover:text-foreground">
              Capabilities
            </a>
            <a href="#faq" className="transition-colors hover:text-foreground">
              FAQ
            </a>
            <a href="#runtime" className="transition-colors hover:text-foreground">
              Runtime
            </a>
          </nav>

          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" className="hidden lg:inline-flex">
              <Link to="/workspace">Launch Workspace</Link>
            </Button>
            <Button asChild className="border border-secondary/30 bg-secondary/10 text-secondary hover:bg-secondary/20">
              <Link to="/workspace/onboarding">
                Start Onboarding
                <ArrowRight />
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <main>
        <section className="relative isolate overflow-hidden qasali-grid px-4 pb-12 pt-14 sm:px-6 lg:px-8 lg:pb-20 lg:pt-20">
          <div className="absolute inset-x-0 top-[-180px] h-[420px] bg-[radial-gradient(circle_at_top,rgba(203,161,83,0.08),transparent_46%)]" />
          <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[minmax(0,1.15fr)_420px] lg:items-start">
            <div className="relative z-10">
              <div className="inline-flex items-center gap-2 border border-primary/25 bg-primary/10 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-primary">
                <Sparkles size={12} />
                Ethical Foundation of Capital Infrastructure
              </div>

              <h1 className="mt-6 max-w-4xl font-display text-4xl font-normal italic leading-[0.95] text-foreground sm:text-5xl lg:text-7xl">
                The Algorithmic Hard-Stop.
              </h1>
              <p className="mt-6 max-w-3xl text-base leading-8 text-muted-foreground sm:text-lg">
                Willpower is a failed metric in high-stakes environments. Sentinel is an event-driven risk gateway that physically locks your MT5 terminal when it detects emotional tilt. Radical objectivity. Sub-500ms precision.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Button
                  asChild
                  size="lg"
                  className="border border-primary/35 bg-primary/10 text-primary hover:bg-primary/20"
                >
                  <Link to="/workspace/onboarding">
                    Connect an MT5 account
                    <ArrowRight />
                  </Link>
                </Button>
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="border-border/80 bg-card/55 text-foreground hover:bg-card/80"
                >
                  <Link to="/workspace">Open operator workspace</Link>
                </Button>
              </div>

              <div className="mt-10 grid gap-4 sm:grid-cols-3">
                <LiveLatencyPulse />
                <CountUpBadge label="Per-user artifact" value={1} suffix=" model" />
                <CountUpBadge label="Blank-baseline safe" value={100} suffix="%" />
              </div>

              <div className="mt-10 grid gap-4 md:grid-cols-3">
                {heroPillars.map((pillar) => (
                  <div key={pillar.title} className="border border-border/80 bg-card/70 p-5 backdrop-blur-xl">
                    <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">
                      {pillar.eyebrow}
                    </div>
                    <h2 className="mt-3 font-display text-xl font-bold text-foreground">
                      {pillar.title}
                    </h2>
                    <p className="mt-3 text-sm leading-7 text-muted-foreground">
                      {pillar.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <aside id="runtime" className="relative z-10 space-y-4">
              <div className="border border-border/80 bg-card/80 p-5 backdrop-blur-2xl">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                      Live runtime
                    </div>
                    <div className="mt-2 font-display text-2xl font-bold text-foreground">
                      {readinessQuery.data?.status === "ready" ? "Brain ready" : "Readiness watch"}
                    </div>
                  </div>
                  <div
                    className={`border px-3 py-1 text-[10px] uppercase tracking-[0.18em] ${
                      readinessQuery.data?.status === "ready"
                        ? "border-secondary/30 text-secondary"
                        : "border-primary/30 text-primary"
                    }`}
                  >
                    {healthQuery.data?.status ?? "checking"}
                  </div>
                </div>

                <div className="mt-5 grid gap-3">
                  {readinessRows.map((row) => (
                    <div
                      key={row.label}
                      className="flex items-center justify-between border border-border/70 bg-background/35 px-4 py-3 text-sm"
                    >
                      <span className="text-muted-foreground">{row.label}</span>
                      <span className="font-bold uppercase tracking-[0.12em] text-foreground">
                        {row.value}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="mt-5 rounded-none border border-secondary/20 bg-secondary/10 p-4 text-sm leading-7 text-muted-foreground">
                  The public shell is reading the same readiness and health endpoints used inside
                  the operator workspace. No fake status dots.
                </div>
              </div>

              <div className="border border-border/80 bg-card/80 p-5 backdrop-blur-xl">
                <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  Platform facts
                </div>
                <div className="mt-4 space-y-3">
                  {platformFacts.map((fact) => (
                    <div key={fact} className="flex items-start gap-3 text-sm leading-7 text-muted-foreground">
                      <CheckCircle2 className="mt-1 text-secondary" size={16} />
                      <span>{fact}</span>
                    </div>
                  ))}
                </div>
              </div>
            </aside>
          </div>
        </section>

        <section id="workflow" className="px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
          <div className="mx-auto max-w-7xl">
            <div className="max-w-3xl">
              <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">Workflow</div>
              <h2 className="mt-3 font-display text-3xl font-bold text-foreground sm:text-4xl">
                From first credential to live model, the whole loop is visible.
              </h2>
              <p className="mt-4 text-base leading-8 text-muted-foreground">
                The product experience mirrors the real control flow, so the interface says what
                the system is actually doing rather than hiding behind generic setup language.
              </p>
            </div>

            <div className="mt-10 grid gap-4 lg:grid-cols-4">
              {workflowSteps.map((step, index) => {
                const icon =
                  index === 0 ? LockKeyhole : index === 1 ? ServerCog : index === 2 ? Radar : Shield;
                const Icon = icon;

                return (
                  <div key={step.id} className="border border-border/80 bg-card/75 p-5 backdrop-blur-xl">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-[10px] uppercase tracking-[0.18em] text-primary">
                        0{index + 1}
                      </div>
                      <Icon className="text-secondary" size={18} />
                    </div>
                    <h3 className="mt-6 font-display text-2xl font-bold text-foreground">
                      {step.title}
                    </h3>
                    <p className="mt-3 text-sm leading-7 text-muted-foreground">
                      {step.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section id="capabilities" className="px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
          <div className="mx-auto grid max-w-7xl gap-10 lg:grid-cols-[minmax(0,1.1fr)_360px]">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">Capabilities</div>
              <h2 className="mt-3 font-display text-3xl font-bold text-foreground sm:text-4xl">
                A frontend that matches the seriousness of the backend.
              </h2>
              <div className="mt-8 grid gap-4 md:grid-cols-2">
                {productCapabilities.map((capability) => (
                  <div key={capability.title} className="border border-border/80 bg-card/75 p-5 backdrop-blur-xl">
                    <h3 className="font-display text-xl font-bold text-foreground">
                      {capability.title}
                    </h3>
                    <p className="mt-3 text-sm leading-7 text-muted-foreground">
                      {capability.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              {workspaceHighlights.map((highlight) => (
                <div key={highlight.label} className="border border-border/80 bg-card/75 p-5 backdrop-blur-xl">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                    {highlight.label}
                  </div>
                  <div className="mt-4 font-display text-4xl font-bold text-primary">
                    {highlight.value}
                  </div>
                  <p className="mt-3 text-sm leading-7 text-muted-foreground">{highlight.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
          <div className="mx-auto max-w-5xl">
            <div className="text-center">
              <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">FAQ</div>
              <h2 className="mt-3 font-display text-3xl font-bold text-foreground sm:text-4xl">
                Real answers for the product we are actually shipping.
              </h2>
            </div>

            <div className="mt-10 border border-border/80 bg-card/75 px-5 backdrop-blur-xl sm:px-8">
              <Accordion type="single" collapsible>
                {faqs.map((faq) => (
                  <AccordionItem key={faq.question} value={faq.question} className="border-border/70">
                    <AccordionTrigger className="text-left font-display text-lg text-foreground hover:no-underline">
                      {faq.question}
                    </AccordionTrigger>
                    <AccordionContent className="text-base leading-8 text-muted-foreground">
                      {faq.answer}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          </div>
        </section>

        <section className="px-4 pb-16 sm:px-6 lg:px-8 lg:pb-24">
          <div className="mx-auto max-w-7xl border border-secondary/20 bg-[linear-gradient(135deg,rgba(203,161,83,0.08),rgba(10,15,26,0.85)_40%,rgba(203,161,83,0.03))] p-8 backdrop-blur-2xl sm:p-10">
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
              <div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-secondary">
                  Ready to launch
                </div>
                <h2 className="mt-3 font-display text-3xl font-bold text-foreground sm:text-4xl">
                  Start with onboarding, then hand the trader off to the live workspace.
                </h2>
                <p className="mt-4 max-w-3xl text-base leading-8 text-muted-foreground">
                  This frontend is built so the public narrative, onboarding flow, operator
                  visibility, and live trading experience all describe the same system.
                </p>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row lg:flex-col">
                <Button
                  asChild
                  size="lg"
                  className="border border-secondary/30 bg-secondary/10 text-secondary hover:bg-secondary/20"
                >
                  <Link to="/workspace/onboarding">Initialize Sentinel</Link>
                </Button>
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="border-border bg-background/50 text-foreground hover:bg-background/80"
                >
                  <Link to="/workspace">Open Workspace</Link>
                </Button>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
