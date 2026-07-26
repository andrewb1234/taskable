import { TechnicalLabel } from "@/components/ui/technical-label";

const snapshots = [
  {
    label: "State A · Parallel",
    title: "Two agents, two owned tickets.",
    facts: [
      ["Knowledge", "K-18 Current"],
      ["#42", "Agent 1 · lease active"],
      ["#43", "Agent 2 · lease active"],
    ],
  },
  {
    label: "State B · Recovery",
    title: "One lease expires; context remains.",
    facts: [
      ["#42", "Delivery ready · Agent 1"],
      ["#43", "Expired → requeued"],
      ["Prior work", "Branch and evidence retained"],
    ],
  },
  {
    label: "State C · Stable",
    title: "Recovered work becomes durable knowledge.",
    facts: [
      ["#42 + #43", "Done · reviewed"],
      ["Knowledge", "K-19 Current"],
      ["Ownership", "No stale leases"],
    ],
  },
] as const;

const events = [
  {
    time: "14:00",
    event: "Context loaded",
    detail: "Retry policy and sources",
    actor: "Agents 1 + 2",
    mutation: "No mutation",
    proof: "Checkpoint K-18",
  },
  {
    time: "14:02",
    event: "Parallel claims committed",
    detail: "#42 implementation · #43 regression coverage",
    actor: "Agent 1 → #42 · Agent 2 → #43",
    mutation: "TODO → IN PROGRESS",
    proof: "Worker IDs + lease boundaries",
  },
  {
    time: "14:08",
    event: "Last valid heartbeat on #43",
    detail: "No later extension arrives",
    actor: "Agent 2",
    mutation: "Lease extended once",
    proof: "Last known active lease",
  },
  {
    time: "14:18",
    event: "Agent 1 finishes #42; lease #43 expires",
    detail: "The expired worker cannot extend its old lease",
    actor: "Agent 1 · Agent 2 unavailable",
    mutation: "#42 → REVIEW · #43 stale",
    proof: "Completion + expiry timestamps",
  },
  {
    time: "14:19",
    event: "Expired work requeued",
    detail: "Worker and lease are cleared",
    actor: "Recovery worker",
    mutation: "#43 → TODO",
    proof: "TICKET_REQUEUED",
  },
  {
    time: "14:20",
    event: "Fresh claim on recovered work",
    detail: "Prior branch and evidence remain linked",
    actor: "Agent 1",
    mutation: "#43 → IN PROGRESS",
    proof: "TICKET_CLAIMED",
  },
  {
    time: "14:31",
    event: "Recovered delivery enters review",
    detail: "Implementation, checks, and policy alignment",
    actor: "Agent 1 → Agent 3",
    mutation: "#43 → REVIEW",
    proof: "PRs + tests + source refs",
  },
  {
    time: "14:38",
    event: "Review accepted; knowledge leaf written",
    detail: "The verified retry outcome becomes durable context",
    actor: "Agent 3",
    mutation: "#42 + #43 → DONE · K-19 → CURRENT",
    proof: "Outcome + recovery history",
  },
] as const;

export function ProjectStateLedger() {
  return (
    <figure
      id="project-state-ledger"
      data-testid="landing-project-state-ledger"
      className="overflow-hidden border border-border bg-surface"
      aria-labelledby="project-state-ledger-title"
    >
      <header className="border-b border-border p-5 sm:p-7">
        <TechnicalLabel>
          Illustrative project record · Northstar Commerce
        </TechnicalLabel>
        <h2
          id="project-state-ledger-title"
          className="mt-3 max-w-3xl text-2xl font-semibold tracking-[-0.025em] sm:text-3xl"
        >
          When a worker disappears, the project does not.
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Context enables parallel work. Leases bound ownership. Review turns
          the recovered outcome into durable knowledge.
        </p>
      </header>

      <div
        className="grid gap-px bg-border md:grid-cols-3"
        aria-label="Project state snapshots"
      >
        {snapshots.map((snapshot) => (
          <section
            key={snapshot.label}
            className="min-w-0 bg-brand-ink p-4 sm:p-5"
          >
            <p className="font-mono text-[0.625rem] font-semibold uppercase tracking-[0.11em] text-brand-brass">
              {snapshot.label}
            </p>
            <h3 className="mt-3 min-h-0 text-sm font-semibold leading-snug md:min-h-10">
              {snapshot.title}
            </h3>
            <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 text-[0.6875rem] leading-relaxed">
              {snapshot.facts.map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="m-0 min-w-0 text-right font-medium text-foreground">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>

      <section aria-labelledby="recovery-ledger-title">
        <div className="flex items-center justify-between gap-4 border-y border-border bg-brand-ink px-4 py-3 sm:px-5">
          <h3 id="recovery-ledger-title" className="text-xs font-semibold">
            Project-state ledger
          </h3>
          <span className="font-mono text-[0.625rem] uppercase tracking-[0.1em] text-status-done-foreground">
            Stable at 14:38
          </span>
        </div>

        <div
          className="hidden grid-cols-[3.2rem_minmax(8rem,1.2fr)_minmax(7rem,0.85fr)_minmax(8rem,1fr)_minmax(8rem,1fr)] gap-3 border-b border-border bg-surface-subtle px-4 py-2.5 font-mono text-[0.5625rem] font-semibold uppercase tracking-[0.09em] text-muted-foreground sm:grid sm:px-5"
          aria-hidden="true"
        >
          <span>Time</span>
          <span>Recorded event</span>
          <span>Actor</span>
          <span>State mutation</span>
          <span>Durable proof</span>
        </div>

        <ol aria-label="Recovery event ledger">
          {events.map((event) => (
            <li
              key={`${event.time}-${event.event}`}
              className="grid min-w-0 grid-cols-[3.2rem_minmax(0,1fr)] gap-x-3 gap-y-3 border-b border-border/70 px-4 py-3.5 last:border-b-0 sm:grid-cols-[3.2rem_minmax(8rem,1.2fr)_minmax(7rem,0.85fr)_minmax(8rem,1fr)_minmax(8rem,1fr)] sm:px-5"
            >
              <time className="font-mono text-[0.625rem] text-muted-foreground">
                {event.time}
              </time>
              <div className="min-w-0">
                <strong className="block text-[0.6875rem] leading-snug">
                  {event.event}
                </strong>
                <span className="mt-1 block text-[0.625rem] leading-relaxed text-muted-foreground">
                  {event.detail}
                </span>
              </div>
              <LedgerDatum label="Actor" value={event.actor} />
              <LedgerDatum label="State mutation" value={event.mutation} />
              <LedgerDatum label="Durable proof" value={event.proof} proof />
            </li>
          ))}
        </ol>
      </section>

      <figcaption className="grid grid-cols-[auto_minmax(0,1fr)] gap-3 border-t border-border bg-brand-ink p-4 font-mono text-[0.625rem] leading-relaxed text-muted-foreground sm:p-5">
        <span className="text-status-blocked-foreground">Boundary</span>
        <span>
          Leases prevent indefinite stale ownership. A fresh worker must still
          inspect existing code, external side effects, and evidence; this is
          not an exactly-once execution claim.
        </span>
      </figcaption>
    </figure>
  );
}

function LedgerDatum({
  label,
  value,
  proof = false,
}: {
  label: string;
  value: string;
  proof?: boolean;
}) {
  return (
    <div className="col-start-2 min-w-0 sm:col-start-auto">
      <span className="mb-1 block font-mono text-[0.5625rem] uppercase tracking-[0.08em] text-muted-foreground sm:sr-only">
        {label}
      </span>
      <span
        className={`block break-words text-[0.625rem] leading-relaxed ${
          proof
            ? "font-mono text-status-done-foreground"
            : "text-foreground/85"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
