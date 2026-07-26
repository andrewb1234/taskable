import type { CSSProperties, MouseEvent } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  GitBranch,
  RefreshCcw,
  ScanEye,
  ShieldCheck,
} from "lucide-react";
import { MouvadahLockup } from "@/components/brand/mouvadah-brand";
import { TechnicalLabel } from "@/components/ui/technical-label";

const lifecycle = [
  { code: "01", label: "Intent", detail: "A bounded outcome" },
  { code: "02", label: "Safe claim", detail: "Dependencies satisfied" },
  { code: "03", label: "Execution", detail: "One accountable worker" },
  { code: "04", label: "Evidence", detail: "Checks and source refs" },
  { code: "05", label: "Review", detail: "Human judgment stays visible" },
  { code: "06", label: "Handoff", detail: "Recoverable project state" },
] as const;

const projectProof = [
  {
    label: "Outcome",
    value: "Ship the authenticated project workbench",
    detail: "Bound to one reviewable ticket",
  },
  {
    label: "Ownership",
    value: "One agent · lease active",
    detail: "The second worker sees that the ticket is already claimed",
  },
  {
    label: "Dependencies",
    value: "Prerequisites complete",
    detail: "Only ready work can be claimed",
  },
  {
    label: "Evidence",
    value: "Tests · source refs · pull request",
    detail: "The delivery record stays outside the transcript",
  },
  {
    label: "Blocker",
    value: "Human review required",
    detail: "The reason and owner remain visible",
  },
  {
    label: "Next safe action",
    value: "Review evidence, then merge",
    detail: "A new session can resume from this state",
  },
] as const;

const narratives = [
  {
    number: "01",
    icon: GitBranch,
    title: "Parallel work without guesswork",
    copy: "Dependency-aware readiness, atomic claims, and worker leases make it clear what can start—and who owns it.",
  },
  {
    number: "02",
    icon: BookOpenCheck,
    title: "Knowledge with provenance",
    copy: "Keep durable decisions connected to evidence while tickets and pull requests remain the execution record.",
  },
  {
    number: "03",
    icon: ScanEye,
    title: "Human review stays first-class",
    copy: "Review gates, blockers, and merge links remain legible instead of disappearing inside an agent transcript.",
  },
  {
    number: "04",
    icon: RefreshCcw,
    title: "Handoffs designed for recovery",
    copy: "Leases, targeted realtime updates, and scoped context help the next person or agent resume from verified state.",
  },
] as const;

function ProjectProof() {
  return (
    <figure
      id="project-proof"
      data-testid="landing-project-proof"
      className="relative overflow-hidden border border-border bg-surface"
      aria-labelledby="lifecycle-title"
    >
      <div className="border-b border-border p-5 sm:p-7">
        <div>
          <TechnicalLabel>Guided execution example</TechnicalLabel>
          <h2
            id="lifecycle-title"
            className="mt-3 max-w-3xl text-2xl font-semibold tracking-tight sm:text-3xl"
          >
            Two agents choose the same ticket. Mouvadah keeps one accountable
            path.
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            The first atomic claim wins. Everyone else sees the owner,
            dependencies, evidence, blocker, and next safe action—without
            reconstructing state from an agent transcript.
          </p>
        </div>
      </div>

      <div className="p-5 sm:p-7">
        <TechnicalLabel>What the project knows now</TechnicalLabel>
        <dl className="mt-4 grid gap-px border border-border bg-border sm:grid-cols-2">
          {projectProof.map((item) => (
            <div
              key={item.label}
              className="min-w-0 bg-surface p-4"
              data-testid={`proof-${item.label.toLowerCase().replaceAll(" ", "-")}`}
            >
              <dt className="font-mono text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-brand-brass">
                {item.label}
              </dt>
              <dd className="mt-2 text-sm font-semibold">{item.value}</dd>
              <dd className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {item.detail}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      <figcaption className="border-t border-border">
        <details className="group">
          <summary className="focus-ring flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-semibold marker:content-none sm:px-7">
            How this state was reached
            <span className="text-xs font-normal text-muted-foreground group-open:hidden">
              Show
            </span>
            <span className="hidden text-xs font-normal text-muted-foreground group-open:inline">
              Hide
            </span>
          </summary>
        <ol
            className="relative grid gap-px border-t border-border bg-border p-px sm:grid-cols-3 xl:grid-cols-6"
          aria-label="Execution lifecycle"
        >
          {lifecycle.map((item) => (
            <li key={item.label} className="bg-surface p-3">
              <span className="font-mono text-[0.65rem] text-brand-brass">
                {item.code}
              </span>
              <span className="ml-2 text-xs font-semibold">{item.label}</span>
              <span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground">
                {item.detail}
              </span>
            </li>
          ))}
        </ol>
        </details>
      </figcaption>
    </figure>
  );
}

export function LandingPage({ onOpenApp }: { onOpenApp: () => void }) {
  const openApp = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    onOpenApp();
  };

  return (
    <div
      data-surface="marketing"
      className="min-h-screen overflow-x-hidden bg-background text-foreground"
    >
      <a
        href="#landing-main"
        className="focus-ring fixed left-4 top-4 z-50 -translate-y-24 rounded-sm bg-brand-paper px-4 py-3 text-sm font-semibold text-brand-ink transition-transform focus:translate-y-0"
      >
        Skip to main content
      </a>
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
          <a href="/" aria-label="Mouvadah home" className="focus-ring rounded-sm">
            <MouvadahLockup />
          </a>
          <nav aria-label="Primary" className="flex items-center gap-3 sm:gap-6">
            <a
              href="https://github.com/andrewb1234/taskable"
              className="focus-ring transition-fast hidden min-h-11 items-center rounded-sm text-xs text-muted-foreground hover:text-foreground sm:inline-flex"
            >
              Source
            </a>
            <a
              href="/app"
              onClick={openApp}
              className="focus-ring transition-fast inline-flex items-center gap-2 rounded-sm border border-brand-brass/70 px-3 py-2 text-xs font-semibold text-foreground hover:bg-brand-brass hover:text-brand-brass-foreground"
            >
              Open app
              <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </a>
          </nav>
        </div>
      </header>

      <main id="landing-main" tabIndex={-1}>
        <section className="mx-auto grid max-w-[1440px] gap-12 px-5 py-16 sm:px-8 sm:py-20 lg:grid-cols-[0.72fr_1.28fr] lg:px-12 lg:py-20">
          <div className="motion-enter">
            <TechnicalLabel>Shared project state</TechnicalLabel>
            <h1 className="mt-8 max-w-4xl text-[clamp(3.4rem,8vw,7.5rem)] font-semibold leading-[0.84] tracking-[-0.075em]">
              What are
              <br />
              you doing?
            </h1>
            <p className="mt-9 max-w-xl text-lg leading-relaxed text-muted-foreground sm:text-xl">
              Know what every human and agent is doing—and why.
            </p>
            <p className="mt-4 max-w-xl text-sm leading-relaxed text-foreground/80 sm:text-base">
              Mouvadah gives software teams one reviewable record of agent
              work—who owns it, what unblocked it, what proves it, and what can
              safely happen next.
            </p>
            <div className="mt-10 flex flex-col gap-3 sm:flex-row">
              <a
                href="/app"
                onClick={openApp}
                className="focus-ring transition-fast inline-flex items-center justify-center gap-3 rounded-sm bg-primary px-5 py-3.5 text-sm font-semibold text-primary-foreground hover:bg-brand-brass hover:text-brand-brass-foreground"
              >
                Sign in to your workspace
                <ArrowRight className="h-4 w-4" aria-hidden />
              </a>
              <a
                href="#project-proof"
                className="focus-ring transition-fast inline-flex items-center justify-center gap-3 rounded-sm border border-border px-5 py-3.5 text-sm font-semibold hover:border-brand-brass hover:text-brand-brass"
              >
                See an example project state
              </a>
            </div>
            <a
              href="https://github.com/andrewb1234/taskable#readme"
              className="focus-ring mt-4 inline-flex min-h-11 items-center rounded-sm text-xs text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground"
            >
              Read documentation
            </a>
          </div>

          <div
            className="motion-enter"
            style={{ "--motion-delay": "120ms" } as CSSProperties}
          >
            <ProjectProof />
          </div>
        </section>

        <section className="border-y border-border">
          <div className="mx-auto max-w-[1440px] px-5 sm:px-8 lg:px-12">
            <div className="grid border-x border-border lg:grid-cols-[0.7fr_1.3fr]">
              <div className="border-b border-border p-6 sm:p-10 lg:border-b-0 lg:border-r lg:p-12">
                <TechnicalLabel>Why Mouvadah</TechnicalLabel>
                <h2 className="mt-5 text-3xl font-semibold tracking-tight sm:text-5xl">
                  A workbench for accountable collaboration.
                </h2>
                <p className="mt-6 max-w-md leading-relaxed text-muted-foreground">
                  Not another broad tracker. Not an agent runtime. A durable
                  shared state and memory layer around the work your tools
                  already do.
                </p>
              </div>
              <ol>
                {narratives.map((item) => {
                  const Icon = item.icon;
                  return (
                    <li
                      key={item.number}
                      className="grid gap-5 border-b border-border p-6 last:border-b-0 sm:grid-cols-[3rem_1fr_auto] sm:items-start sm:p-8"
                    >
                      <span className="font-mono text-xs text-brand-brass">
                        {item.number}
                      </span>
                      <div>
                        <h3 className="text-lg font-semibold">{item.title}</h3>
                        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                          {item.copy}
                        </p>
                      </div>
                      <Icon className="h-5 w-5 text-muted-foreground" aria-hidden />
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-[1440px] gap-12 px-5 py-24 sm:px-8 lg:grid-cols-2 lg:px-12 lg:py-36">
          <div>
            <TechnicalLabel>Trust is a product surface</TechnicalLabel>
            <h2 className="mt-5 max-w-xl text-3xl font-semibold tracking-tight sm:text-5xl">
              Current claims, clearly bounded.
            </h2>
          </div>
          <div className="border border-border bg-surface">
            {[
              {
                icon: ShieldCheck,
                title: "Workspace-scoped access",
                copy: "Object access is evaluated within the active workspace boundary.",
              },
              {
                icon: GitBranch,
                title: "Reviewable delivery",
                copy: "Tickets keep dependencies, blockers, claims, and pull-request state visible.",
              },
              {
                icon: RefreshCcw,
                title: "Recoverable coordination",
                copy: "Leases and targeted synchronization support safe recovery from interrupted work.",
              },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.title}
                  className="grid grid-cols-[auto_1fr] gap-4 border-b border-border p-5 last:border-b-0 sm:p-6"
                >
                  <Icon className="mt-0.5 h-5 w-5 text-brand-brass" aria-hidden />
                  <div>
                    <h3 className="text-sm font-semibold">{item.title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                      {item.copy}
                    </p>
                  </div>
                </div>
              );
            })}
            <p className="border-t border-border p-5 font-mono text-[0.68rem] leading-relaxed text-muted-foreground sm:p-6">
              No compliance, SLA, exactly-once delivery, multi-instance
              availability, or production disaster-recovery claim is implied.
            </p>
          </div>
        </section>

        <section className="border-t border-border bg-surface">
          <div className="mx-auto flex max-w-[1440px] flex-col items-start justify-between gap-10 px-5 py-20 sm:px-8 lg:flex-row lg:items-end lg:px-12 lg:py-28">
            <div>
              <TechnicalLabel>Return to known state</TechnicalLabel>
              <h2 className="mt-5 max-w-3xl text-4xl font-semibold tracking-tight sm:text-6xl">
                See the work. Review the evidence. Resume safely.
              </h2>
            </div>
            <a
              href="/app"
              onClick={openApp}
              className="focus-ring transition-fast inline-flex shrink-0 items-center gap-3 rounded-sm bg-brand-brass px-5 py-3.5 text-sm font-semibold text-brand-brass-foreground hover:bg-primary hover:text-primary-foreground"
            >
              Open or sign in
              <ArrowRight className="h-4 w-4" aria-hidden />
            </a>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1440px] flex-col gap-5 px-5 py-8 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
          <MouvadahLockup size="sm" />
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            <a
              href="/app"
              onClick={openApp}
              className="focus-ring inline-flex min-h-11 items-center rounded-sm hover:text-foreground"
            >
              Sign in
            </a>
            <a
              href="https://github.com/andrewb1234/taskable"
              className="focus-ring inline-flex min-h-11 items-center rounded-sm hover:text-foreground"
            >
              GitHub source
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
