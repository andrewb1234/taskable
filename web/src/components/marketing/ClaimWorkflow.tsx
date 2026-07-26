import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Pause, Play, RotateCcw } from "lucide-react";
import readyWork from "@/assets/landing-claim-workflow/01-both-ready.webp";
import claimCommitted from "@/assets/landing-claim-workflow/02-claim-committed.webp";
import workRerouted from "@/assets/landing-claim-workflow/03-work-rerouted.webp";
import { TechnicalLabel } from "@/components/ui/technical-label";

const stages = [
  {
    title: "Both agents select the checkout fix.",
    detail: "One shared ready queue. No private coordination.",
  },
  {
    title: "Two claim requests converge on ticket #2.",
    detail: "Both workers saw the same dependency-safe task.",
  },
  {
    title: "agent-cobalt becomes the owner.",
    detail: "The active lease is immediately visible in the workbench.",
  },
  {
    title: "agent-ember receives a 409 conflict.",
    detail: "Ticket #2 keeps one recorded owner.",
  },
  {
    title: "agent-ember takes the next ready task.",
    detail: "Two valuable tasks now have distinct accountable workers.",
  },
] as const;

interface ClaimEvent {
  showAt: number;
  time: string;
  label: string;
  detail: string;
  tone?: "success" | "conflict" | "reroute";
}

const events: readonly ClaimEvent[] = [
  {
    showAt: 1,
    time: "14:02",
    label: "agent-cobalt → claim #2",
    detail: "Fix duplicate checkout submission",
  },
  {
    showAt: 2,
    time: "14:02",
    label: "200 · owner committed",
    detail: "Lease active for agent-cobalt",
    tone: "success",
  },
  {
    showAt: 2,
    time: "14:03",
    label: "agent-ember → claim #2",
    detail: "Same ticket, independent worker",
  },
  {
    showAt: 3,
    time: "14:03",
    label: "409 · already claimed",
    detail: "Current owner remains visible",
    tone: "conflict",
  },
  {
    showAt: 4,
    time: "14:04",
    label: "agent-ember → claim #3",
    detail: "Next ready task",
    tone: "reroute",
  },
  {
    showAt: 4,
    time: "14:04",
    label: "200 · owner committed",
    detail: "Two tasks, two accountable workers",
    tone: "success",
  },
] as const;

const stageDurations = [1350, 1600, 1600, 1700, 3600] as const;

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return reduced;
}

export function ClaimWorkflow() {
  const rootRef = useRef<HTMLElement>(null);
  const reducedMotion = useReducedMotion();
  const [stage, setStage] = useState(0);
  const [paused, setPaused] = useState(false);
  const [inView, setInView] = useState(true);
  const [documentVisible, setDocumentVisible] = useState(
    () => document.visibilityState === "visible",
  );

  useEffect(() => {
    if (!reducedMotion) return;
    setStage(stages.length - 1);
    setPaused(false);
  }, [reducedMotion]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      ([entry]) => setInView(entry.isIntersecting),
      { threshold: 0.12 },
    );
    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const update = () =>
      setDocumentVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);

  useEffect(() => {
    if (reducedMotion || paused || !inView || !documentVisible) return;
    const timer = window.setTimeout(() => {
      setStage((current) => (current + 1) % stages.length);
    }, stageDurations[stage]);
    return () => window.clearTimeout(timer);
  }, [documentVisible, inView, paused, reducedMotion, stage]);

  const activeImage = stage < 2 ? 0 : stage < 4 ? 1 : 2;
  const currentStage = stages[stage];

  const advanceOrReplay = () => {
    if (reducedMotion) {
      setStage((current) => (current + 1) % stages.length);
      return;
    }
    setStage(0);
    setPaused(false);
  };

  return (
    <figure
      ref={rootRef}
      id="claim-workflow"
      data-testid="landing-claim-workflow"
      className="relative overflow-hidden border border-border bg-surface"
      aria-labelledby="claim-workflow-title"
    >
      <div className="border-b border-border p-5 sm:p-7">
        <TechnicalLabel>Real workflow · Northstar Commerce</TechnicalLabel>
        <h2
          id="claim-workflow-title"
          className="mt-3 max-w-3xl text-2xl font-semibold tracking-[-0.025em] sm:text-3xl"
        >
          The race, resolved in six events.
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Two agents independently choose an urgent checkout defect. The
          workbench shows the human-readable state; the claim ledger shows
          exactly how ownership changed.
        </p>
      </div>

      <div className="grid min-w-0 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="relative aspect-square min-w-0 overflow-hidden border-b border-border bg-brand-ink lg:border-b-0 lg:border-r">
          {[
            readyWork,
            claimCommitted,
            workRerouted,
          ].map((source, index) => (
            <img
              key={source}
              src={source}
              width={680}
              height={680}
              alt=""
              aria-hidden="true"
              draggable={false}
              decoding="async"
              fetchPriority={index === 0 ? "high" : "auto"}
              className={`absolute inset-0 h-full w-full object-cover ${
                reducedMotion
                  ? "transition-none"
                  : "transition-[opacity,transform] duration-500 ease-out"
              } ${
                activeImage === index
                  ? "scale-100 opacity-100"
                  : "scale-[1.012] opacity-0"
              }`}
            />
          ))}
          <div className="absolute left-3 top-3 border border-border/80 bg-brand-ink/95 px-2.5 py-1.5 font-mono text-[0.625rem] uppercase tracking-[0.12em] text-muted-foreground">
            Live product capture
          </div>
        </div>

        <aside
          aria-label="Claim event ledger"
          className="flex min-w-0 flex-col bg-brand-ink p-4 sm:p-5"
        >
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Claim responses</h3>
            <span className="font-mono text-[0.625rem] uppercase tracking-[0.12em] text-muted-foreground">
              Act {Math.max(1, stage)} of 4
            </span>
          </div>

          <ol className="mt-4 flex-1">
            {events.map((event, index) => {
              const revealed = reducedMotion || stage >= event.showAt;
              const tone =
                event.tone === "success"
                  ? "text-status-done-foreground"
                  : event.tone === "conflict"
                    ? "text-status-blocked-foreground"
                    : event.tone === "reroute"
                      ? "text-actor-agent-foreground"
                      : "text-foreground";
              return (
                <li
                  key={`${event.time}-${event.label}`}
                  className={`grid grid-cols-[2.75rem_1fr] gap-2 border-t border-border/60 py-2.5 ${
                    reducedMotion
                      ? "transition-none"
                      : "transition-[opacity,transform] duration-300 ease-out"
                  } ${
                    revealed
                      ? "translate-x-0 opacity-100"
                      : "translate-x-1.5 opacity-25"
                  }`}
                  aria-current={
                    stage === event.showAt &&
                    (index === 0 || events[index - 1].showAt < event.showAt)
                      ? "step"
                      : undefined
                  }
                >
                  <time className="font-mono text-[0.625rem] text-muted-foreground">
                    {event.time}
                  </time>
                  <div className="min-w-0">
                    <span
                      className={`block font-mono text-[0.625rem] font-semibold leading-relaxed ${tone}`}
                    >
                      {event.label}
                    </span>
                    <span className="mt-0.5 block text-[0.6875rem] leading-relaxed text-muted-foreground">
                      {event.detail}
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>

          <div
            role="status"
            aria-live="polite"
            className={`mt-4 border p-3 ${
              reducedMotion
                ? "transition-none"
                : "transition-colors duration-300"
            } ${
              stage === stages.length - 1
                ? "border-status-done-border/70 bg-status-done/10"
                : "border-border bg-surface"
            }`}
          >
            <div className="flex items-start gap-2">
              {stage === stages.length - 1 && (
                <CheckCircle2
                  className="mt-0.5 h-4 w-4 shrink-0 text-status-done-foreground"
                  aria-hidden
                />
              )}
              <div>
                <strong className="block text-xs leading-snug">
                  {currentStage.title}
                </strong>
                <span className="mt-1 block text-[0.6875rem] leading-relaxed text-muted-foreground">
                  {currentStage.detail}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={advanceOrReplay}
              className="focus-ring transition-fast inline-flex min-h-11 items-center gap-2 rounded-sm border border-border px-3 text-xs font-semibold hover:border-brand-brass hover:text-brand-brass"
            >
              {reducedMotion ? (
                <Play className="h-3.5 w-3.5" aria-hidden />
              ) : (
                <RotateCcw className="h-3.5 w-3.5" aria-hidden />
              )}
              {reducedMotion ? "Next state" : "Replay"}
            </button>
            {!reducedMotion && (
              <button
                type="button"
                onClick={() => setPaused((current) => !current)}
                className="focus-ring transition-fast inline-flex min-h-11 items-center gap-2 rounded-sm px-3 text-xs font-semibold text-muted-foreground hover:text-foreground"
                aria-pressed={paused}
              >
                {paused ? (
                  <Play className="h-3.5 w-3.5" aria-hidden />
                ) : (
                  <Pause className="h-3.5 w-3.5" aria-hidden />
                )}
                {paused ? "Resume" : "Pause"}
              </button>
            )}
          </div>
        </aside>
      </div>

      <figcaption className="sr-only">
        In an isolated Northstar Commerce workspace, agent-cobalt and
        agent-ember both attempt to claim ticket 2, Fix duplicate checkout
        submission. agent-cobalt&apos;s conditional claim succeeds and its
        active lease becomes visible. agent-ember receives a 409 already
        claimed response, then claims ticket 3, Add idempotency regression
        coverage. The final workbench shows two tasks with two distinct owners.
      </figcaption>
    </figure>
  );
}
