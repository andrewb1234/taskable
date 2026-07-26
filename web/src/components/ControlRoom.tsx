import { useEffect, useMemo } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  Bot,
  CircleAlert,
  CircleCheck,
  Clock3,
  GitBranch,
  Loader2,
  RefreshCcw,
} from "lucide-react";
import { useWorkspace } from "@/context/WorkspaceContext";
import { useAsync } from "@/hooks/useAsync";
import {
  getProject,
  listKnowledgeNodesAll,
  listProjectProposals,
  listProjectTickets,
  listSessions,
  listSubprojects,
} from "@/lib/api";
import type {
  AgentSession,
  KnowledgeNode,
  KnowledgeProposal,
  Project,
  SSEPayload,
  Subproject,
  TicketAssignee,
  TicketRef,
  TicketStatus,
} from "@/types";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/ui/surface";
import { TechnicalLabel } from "@/components/ui/technical-label";
import {
  AssigneeIndicator,
  TicketStatusIndicator,
} from "@/components/ui/state-indicator";

interface ControlRoomProps {
  projectId: number;
  lastEvent: SSEPayload | null;
}

const ticketStatuses: TicketStatus[] = [
  "TODO",
  "IN_PROGRESS",
  "BLOCKED",
  "REVIEW",
  "DONE",
];

const assignees: TicketAssignee[] = ["HUMAN", "AGENT", "UNASSIGNED"];

export function ControlRoom({ projectId, lastEvent }: ControlRoomProps) {
  const { openTicket, setActiveSubprojectId, setView } = useWorkspace();
  const project = useAsync<Project>(() => getProject(projectId), [projectId]);
  const subprojects = useAsync<Subproject[]>(
    () => listSubprojects(projectId),
    [projectId],
  );
  const tickets = useAsync<TicketRef[]>(
    () => listProjectTickets(projectId),
    [projectId],
  );
  const knowledge = useAsync<KnowledgeNode[]>(
    () => listKnowledgeNodesAll(projectId),
    [projectId],
  );
  const proposals = useAsync<KnowledgeProposal[]>(
    () => listProjectProposals(projectId),
    [projectId],
  );
  const sessions = useAsync<AgentSession[]>(
    () => listSessions(projectId),
    [projectId],
  );

  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.action === "SYNC_REQUIRED") {
      project.refetch();
      subprojects.refetch();
      tickets.refetch();
      knowledge.refetch();
      proposals.refetch();
      sessions.refetch();
      return;
    }

    if (lastEvent.entity === "project" && lastEvent.entity_id === projectId) {
      project.refetch();
    }
    if (
      lastEvent.entity === "subproject" &&
      lastEvent.parent_id === projectId
    ) {
      subprojects.refetch();
    }
    if (
      lastEvent.entity === "ticket" &&
      subprojects.data?.some(
        (subproject) => subproject.id === lastEvent.parent_id,
      )
    ) {
      tickets.refetch();
    }
    if (
      lastEvent.entity === "knowledge_node" &&
      lastEvent.parent_id === projectId
    ) {
      knowledge.refetch();
    }
    if (
      lastEvent.entity === "knowledge_proposal" &&
      (lastEvent.parent_id === projectId ||
        proposals.data?.some(
          (proposal) => proposal.id === lastEvent.entity_id,
        ))
    ) {
      proposals.refetch();
    }
    if (
      lastEvent.entity === "agent_session" &&
      lastEvent.parent_id === projectId
    ) {
      sessions.refetch();
    }
    // Each resource owns its own loading/error state; targeted invalidation
    // keeps one noisy source from blanking the full Control Room.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent, projectId]);

  const ticketSummary = useMemo(() => {
    const statusCounts = Object.fromEntries(
      ticketStatuses.map((status) => [status, 0]),
    ) as Record<TicketStatus, number>;
    const ownerCounts = Object.fromEntries(
      assignees.map((assignee) => [assignee, 0]),
    ) as Record<TicketAssignee, number>;
    const attention: TicketRef[] = [];
    const bySubproject = new Map<
      number,
      { total: number; moving: number; attention: number }
    >();

    for (const ticket of tickets.data ?? []) {
      statusCounts[ticket.status] += 1;
      ownerCounts[ticket.assignee] += 1;
      if (ticket.status === "BLOCKED" || ticket.status === "REVIEW") {
        attention.push(ticket);
      }
      const scoped = bySubproject.get(ticket.subproject_id) ?? {
        total: 0,
        moving: 0,
        attention: 0,
      };
      scoped.total += 1;
      if (ticket.status === "IN_PROGRESS") scoped.moving += 1;
      if (ticket.status === "BLOCKED" || ticket.status === "REVIEW") {
        scoped.attention += 1;
      }
      bySubproject.set(ticket.subproject_id, scoped);
    }

    attention.sort((a, b) => {
      if (a.status === b.status) return a.id - b.id;
      return a.status === "BLOCKED" ? -1 : 1;
    });
    return { statusCounts, ownerCounts, attention, bySubproject };
  }, [tickets.data]);
  const knowledgeCounts = useMemo(
    () => ({
      CURRENT:
        knowledge.data?.filter((node) => node.status === "CURRENT").length ?? 0,
      STALE:
        knowledge.data?.filter((node) => node.status === "STALE").length ?? 0,
      ARCHIVED:
        knowledge.data?.filter((node) => node.status === "ARCHIVED").length ??
        0,
    }),
    [knowledge.data],
  );
  const activeSessions = (sessions.data ?? []).filter(
    (session) => session.status === "ACTIVE",
  );
  const resumableSessions = (sessions.data ?? [])
    .filter(
      (session) =>
        session.status !== "ACTIVE" &&
        Boolean(session.handoff_note?.trim()),
    )
    .slice(0, 4);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-[1480px] space-y-8 px-4 py-6 sm:px-6 lg:px-8">
        <section aria-labelledby="control-room-title">
          <TechnicalLabel>Project command context</TechnicalLabel>
          <div className="mt-3 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
            <div className="min-w-0">
              <h2
                id="control-room-title"
                className="text-2xl font-semibold tracking-tight sm:text-3xl"
              >
                Control Room
              </h2>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground sm:text-base">
                See what is moving, what needs judgment, and where verified
                context should guide the next safe action.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => {
                project.refetch();
                subprojects.refetch();
                tickets.refetch();
                knowledge.refetch();
                proposals.refetch();
                sessions.refetch();
              }}
            >
              <RefreshCcw className="h-4 w-4" aria-hidden />
              Refresh project state
            </Button>
          </div>
        </section>

        <AsyncSection
          title="Project brief"
          loading={project.loading}
          error={project.error}
          onRetry={project.refetch}
        >
          {project.data && (
            <Surface radius="none" padding="lg">
              <div className="grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
                <div>
                  <p className="text-lg font-semibold">{project.data.name}</p>
                  <p className="mt-3 max-w-3xl text-sm leading-7 text-muted-foreground">
                    {project.data.description?.trim() ||
                      "No project brief has been recorded yet."}
                  </p>
                </div>
                <ol
                  className="grid grid-cols-2 gap-px border border-border bg-border sm:grid-cols-4"
                  aria-label="Mouvadah control-plane lifecycle"
                >
                  {[
                    ["01", "Bound outcome"],
                    ["02", "Safe execution"],
                    ["03", "Verified evidence"],
                    ["04", "Review + resume"],
                  ].map(([step, label]) => (
                    <li
                      key={step}
                      className="min-w-0 bg-surface-subtle px-3 py-4"
                    >
                      <span className="font-mono text-xs text-brand-brass">
                        {step}
                      </span>
                      <span className="mt-2 block text-xs font-medium">
                        {label}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            </Surface>
          )}
        </AsyncSection>

        <div className="grid gap-8 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)]">
          <AsyncSection
            title="Work state"
            loading={tickets.loading}
            error={tickets.error}
            onRetry={tickets.refetch}
          >
            {tickets.data && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                  {ticketStatuses.map((status) => (
                    <Surface
                      key={status}
                      radius="none"
                      padding="sm"
                      className="min-w-0"
                    >
                      <TicketStatusIndicator status={status} />
                      <p className="mt-4 font-mono text-2xl font-semibold">
                        {String(ticketSummary.statusCounts[status]).padStart(
                          2,
                          "0",
                        )}
                      </p>
                    </Surface>
                  ))}
                </div>
                <Surface radius="none" padding="md">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold">
                        Human attention
                      </h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Blocked work comes first, followed by work awaiting
                        review.
                      </p>
                    </div>
                    <CircleAlert
                      className="h-5 w-5 shrink-0 text-brand-brass"
                      aria-hidden
                    />
                  </div>
                  <p className="sr-only" role="status" aria-live="polite">
                    {ticketSummary.attention.length}{" "}
                    {ticketSummary.attention.length === 1
                      ? "ticket requires"
                      : "tickets require"}{" "}
                    human attention.
                  </p>
                  {ticketSummary.attention.length === 0 ? (
                    <EmptyState
                      icon={CircleCheck}
                      title="No blocked or review work"
                      body="This project has no tickets currently requiring human judgment."
                    />
                  ) : (
                    <ul className="mt-4 divide-y divide-border border-y border-border">
                      {ticketSummary.attention.map((ticket) => (
                        <li key={ticket.id}>
                          <button
                            type="button"
                            className="focus-ring flex min-h-12 w-full items-center gap-3 px-2 py-3 text-left hover:bg-accent/40"
                            onClick={() => openTicket(ticket.id)}
                          >
                            <span className="font-mono text-xs text-muted-foreground">
                              #{ticket.id}
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium">
                                {ticket.title}
                              </span>
                              <span className="mt-1 block truncate text-xs text-muted-foreground">
                                {ticket.subproject_name ??
                                  `Subproject #${ticket.subproject_id}`}
                              </span>
                            </span>
                            <TicketStatusIndicator status={ticket.status} />
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </Surface>
              </div>
            )}
          </AsyncSection>

          <AsyncSection
            title="Ownership"
            loading={tickets.loading}
            error={tickets.error}
            onRetry={tickets.refetch}
          >
            {tickets.data && (
              <Surface radius="none" padding="md">
                <div className="space-y-3">
                  {assignees.map((assignee) => (
                    <div
                      key={assignee}
                      className="flex min-h-11 items-center justify-between gap-3 border-b border-border pb-3 last:border-0 last:pb-0"
                    >
                      <AssigneeIndicator assignee={assignee} />
                      <span className="font-mono text-lg font-semibold">
                        {ticketSummary.ownerCounts[assignee]}
                      </span>
                    </div>
                  ))}
                </div>
              </Surface>
            )}
          </AsyncSection>
        </div>

        <div className="grid gap-8 xl:grid-cols-2">
          <AsyncSection
            title="Agent continuity"
            loading={sessions.loading}
            error={sessions.error}
            onRetry={sessions.refetch}
          >
            {sessions.data && (
              <Surface radius="none" padding="md">
                {activeSessions.length === 0 &&
                resumableSessions.length === 0 ? (
                  <EmptyState
                    icon={Bot}
                    title="No active or resumable sessions"
                    body="Active work and completed handoffs will appear here when agents record project sessions."
                  />
                ) : (
                  <div className="space-y-5">
                    {activeSessions.length > 0 && (
                      <SessionList
                        label="Active now"
                        sessions={activeSessions.slice(0, 5)}
                      />
                    )}
                    {resumableSessions.length > 0 && (
                      <SessionList
                        label="Handoffs ready to resume"
                        sessions={resumableSessions}
                      />
                    )}
                  </div>
                )}
              </Surface>
            )}
          </AsyncSection>

          <AsyncSection
            title="Knowledge health"
            loading={knowledge.loading || proposals.loading}
            error={knowledge.error ?? proposals.error}
            onRetry={() => {
              knowledge.refetch();
              proposals.refetch();
            }}
          >
            {knowledge.data && proposals.data && (
              <Surface radius="none" padding="md">
                <div className="grid grid-cols-3 gap-px border border-border bg-border">
                  {[
                    ["Current", knowledgeCounts.CURRENT],
                    ["Stale", knowledgeCounts.STALE],
                    ["Archived", knowledgeCounts.ARCHIVED],
                  ].map(([label, count]) => (
                    <div key={label} className="bg-surface-subtle p-3">
                      <p className="text-xs text-muted-foreground">{label}</p>
                      <p className="mt-2 font-mono text-xl font-semibold">
                        {count}
                      </p>
                    </div>
                  ))}
                </div>
                <div className="mt-4 flex flex-col justify-between gap-3 border-t border-border pt-4 sm:flex-row sm:items-center">
                  <div>
                    <p className="text-sm font-semibold">
                      {
                        proposals.data.filter(
                          (proposal) => proposal.status === "PENDING",
                        ).length
                      }{" "}
                      pending proposal
                      {proposals.data.filter(
                        (proposal) => proposal.status === "PENDING",
                      ).length === 1
                        ? ""
                        : "s"}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Proposed knowledge remains reviewable until a human
                      accepts or rejects it.
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => setView("knowledge")}
                  >
                    Open Knowledge
                    <ArrowRight className="h-4 w-4" aria-hidden />
                  </Button>
                </div>
              </Surface>
            )}
          </AsyncSection>
        </div>

        <AsyncSection
          title="Subproject map"
          loading={subprojects.loading || tickets.loading}
          error={subprojects.error ?? tickets.error}
          onRetry={() => {
            subprojects.refetch();
            tickets.refetch();
          }}
        >
          {subprojects.data && tickets.data && (
            <>
              {subprojects.data.length === 0 ? (
                <Surface radius="none" padding="lg">
                  <EmptyState
                    icon={GitBranch}
                    title="No subprojects yet"
                    body="Create a subproject from workspace navigation to give this project an execution boundary."
                  />
                </Surface>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {subprojects.data.map((subproject) => {
                    const scoped = ticketSummary.bySubproject.get(
                      subproject.id,
                    ) ?? {
                      total: 0,
                      moving: 0,
                      attention: 0,
                    };
                    return (
                      <button
                        key={subproject.id}
                        type="button"
                        className="focus-ring min-h-44 border border-border bg-surface p-4 text-left transition-colors hover:border-brand-brass hover:bg-accent/30"
                        onClick={() =>
                          setActiveSubprojectId(
                            subproject.id,
                            subproject.name,
                          )
                        }
                      >
                        <span className="flex items-center justify-between gap-3">
                          <span className="font-mono text-xs text-brand-brass">
                            {subproject.status}
                          </span>
                          <ArrowRight
                            className="h-4 w-4 text-muted-foreground"
                            aria-hidden
                          />
                        </span>
                        <span className="mt-4 block text-base font-semibold">
                          {subproject.name}
                        </span>
                        <span className="mt-2 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">
                          {subproject.context_brief ||
                            "No subproject context has been recorded."}
                        </span>
                        <span className="mt-4 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          <span>{scoped.total} total</span>
                          <span aria-hidden>·</span>
                          <span>
                            {scoped.moving} moving
                          </span>
                          <span aria-hidden>·</span>
                          <span>
                            {scoped.attention} attention
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </AsyncSection>
      </div>
    </div>
  );
}

function AsyncSection({
  title,
  loading,
  error,
  onRetry,
  children,
}: {
  title: string;
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={`control-room-${slug(title)}`}>
      <div className="mb-3 flex min-h-9 items-center justify-between gap-3">
        <h3
          id={`control-room-${slug(title)}`}
          className="text-sm font-semibold"
        >
          {title}
        </h3>
        {loading && (
          <span className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            Refreshing
          </span>
        )}
      </div>
      {error ? (
        <Surface radius="none" padding="md" role="alert">
          <p className="text-sm font-semibold">This section could not load.</p>
          <p className="mt-1 text-xs text-muted-foreground">{error.message}</p>
          <Button className="mt-4" variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </Surface>
      ) : (
        children
      )}
    </section>
  );
}

function EmptyState({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof BookOpenCheck;
  title: string;
  body: string;
}) {
  return (
    <div className="flex min-h-28 flex-col items-center justify-center px-4 py-6 text-center">
      <Icon className="h-5 w-5 text-muted-foreground" aria-hidden />
      <p className="mt-3 text-sm font-semibold">{title}</p>
      <p className="mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">
        {body}
      </p>
    </div>
  );
}

function SessionList({
  label,
  sessions,
}: {
  label: string;
  sessions: AgentSession[];
}) {
  return (
    <div>
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <ul className="mt-2 divide-y divide-border border-y border-border">
        {sessions.map((session) => (
          <li key={session.id} className="py-3">
            <div className="flex items-start gap-3">
              {session.status === "ACTIVE" ? (
                <Bot
                  className="mt-0.5 h-4 w-4 shrink-0 text-brand-brass"
                  aria-hidden
                />
              ) : (
                <Clock3
                  className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden
                />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{session.intent}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {session.status === "ACTIVE"
                    ? `Started ${formatTimestamp(session.started_at)}`
                    : session.handoff_note}
                </p>
              </div>
              <span className="font-mono text-[0.6875rem] text-muted-foreground">
                {session.status}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "at an unknown time";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}
