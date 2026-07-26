import { useEffect, useMemo } from "react";
import {
  ArrowRight,
  BookOpenCheck,
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
import { ASSIGNEE_LABELS, TICKET_STATUS_LABELS } from "@/types";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/ui/surface";
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
    const inFlight: TicketRef[] = [];
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
      if (ticket.status === "IN_PROGRESS") inFlight.push(ticket);
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
    inFlight.sort((a, b) => a.id - b.id);
    return { statusCounts, ownerCounts, attention, inFlight, bySubproject };
  }, [tickets.data]);
  const staleKnowledgeCount =
    knowledge.data?.filter((node) => node.status === "STALE").length ?? 0;
  const pendingProposalCount =
    proposals.data?.filter((proposal) => proposal.status === "PENDING").length ??
    0;
  const resumableSessions = (sessions.data ?? [])
    .filter(
      (session) =>
        session.status !== "ACTIVE" &&
        Boolean(session.handoff_note?.trim()),
    )
    .slice(0, 4);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-[1480px] space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section aria-labelledby="control-room-title">
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
            <div className="min-w-0">
              <h2
                id="control-room-title"
                className="text-2xl font-semibold tracking-tight sm:text-3xl"
              >
                Control Room
              </h2>
              {project.data ? (
                <p className="mt-2 line-clamp-2 max-w-3xl break-words text-sm leading-relaxed text-muted-foreground">
                  <span className="font-semibold text-foreground">
                    {project.data.name}
                  </span>
                  {project.data.description?.trim()
                    ? ` — ${project.data.description.trim()}`
                    : ""}
                </p>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  Current work, decisions, and next actions.
                </p>
              )}
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
              Refresh
            </Button>
          </div>
        </section>

        <AsyncSection
          title="Project state"
          loading={tickets.loading}
          error={tickets.error}
          onRetry={tickets.refetch}
        >
          {tickets.data && (
            <div className="space-y-3">
              <div className="grid gap-3 xl:grid-cols-2">
                <Surface radius="none" padding="md">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold">
                        Needs your attention
                      </h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Blocked work first, then items awaiting human review.
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
                  <TicketSummaryList
                    tickets={ticketSummary.attention}
                    emptyIcon={CircleCheck}
                    emptyTitle="Nothing needs attention"
                    emptyBody="No tickets are blocked or awaiting review."
                    indicator="status"
                    onOpen={openTicket}
                  />
                </Surface>

                <Surface radius="none" padding="md">
                  <div>
                    <h3 className="text-sm font-semibold">Work in flight</h3>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Active tickets and their current owners.
                    </p>
                  </div>
                  <TicketSummaryList
                    tickets={ticketSummary.inFlight}
                    emptyIcon={CircleCheck}
                    emptyTitle="No work in flight"
                    emptyBody="No tickets are currently in progress."
                    indicator="assignee"
                    onOpen={openTicket}
                  />
                </Surface>
              </div>

              <dl
                className="grid grid-cols-2 gap-px border border-border bg-border sm:grid-cols-5"
                aria-label="Ticket status summary"
              >
                {ticketStatuses.map((status) => (
                  <div
                    key={status}
                    className="flex min-w-0 items-center justify-between gap-2 bg-surface-subtle px-3 py-3 sm:block"
                  >
                    <dt className="min-w-0 text-xs text-muted-foreground">
                      {TICKET_STATUS_LABELS[status]}
                    </dt>
                    <dd className="shrink-0 font-mono text-lg font-semibold sm:mt-2">
                      {ticketSummary.statusCounts[status]}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </AsyncSection>

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
                          <span className="font-mono text-xs text-status-review-foreground">
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

        {(pendingProposalCount > 0 || staleKnowledgeCount > 0) && (
          <section aria-labelledby="control-room-knowledge-review">
            <h3
              id="control-room-knowledge-review"
              className="mb-3 text-sm font-semibold"
            >
              Knowledge review
            </h3>
            <Surface
              radius="none"
              padding="md"
              className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"
            >
              <div>
                <p className="text-sm font-semibold">
                  {pendingProposalCount} pending{" "}
                  {pendingProposalCount === 1 ? "proposal" : "proposals"} ·{" "}
                  {staleKnowledgeCount} stale{" "}
                  {staleKnowledgeCount === 1 ? "node" : "nodes"}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  Review proposed changes and context that may no longer be
                  current.
                </p>
              </div>
              <Button variant="outline" onClick={() => setView("knowledge")}>
                Review Knowledge
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Button>
            </Surface>
          </section>
        )}

        {resumableSessions.length > 0 && (
          <section aria-labelledby="control-room-handoffs">
            <h3 id="control-room-handoffs" className="mb-3 text-sm font-semibold">
              Handoffs ready to resume
            </h3>
            <Surface radius="none" padding="md">
              <p className="mb-4 text-xs leading-relaxed text-muted-foreground">
                Explicit handoff notes from recorded agent sessions. Active
                ticket work appears under Work in flight.
              </p>
              <SessionList sessions={resumableSessions} />
            </Surface>
          </section>
        )}

        {project.data && tickets.data && (
          <details className="group border border-border bg-surface">
            <summary className="focus-ring flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold marker:content-none">
              Project details
              <span className="text-xs font-normal text-muted-foreground group-open:hidden">
                Brief and ownership
              </span>
              <span className="hidden text-xs font-normal text-muted-foreground group-open:inline">
                Hide
              </span>
            </summary>
            <div className="grid gap-6 border-t border-border p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div>
                <p className="text-sm font-semibold">{project.data.name}</p>
                <p className="mt-2 max-w-3xl whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">
                  {project.data.description?.trim() ||
                    "No project brief has been recorded yet."}
                </p>
              </div>
              <dl className="grid grid-cols-3 gap-px border border-border bg-border lg:min-w-72">
                {assignees.map((assignee) => (
                  <div
                    key={assignee}
                    className="min-w-0 bg-surface-subtle p-3 text-center"
                  >
                    <dt className="truncate text-xs text-muted-foreground">
                      {ASSIGNEE_LABELS[assignee]}
                    </dt>
                    <dd className="mt-2 font-mono text-lg font-semibold">
                      {ticketSummary.ownerCounts[assignee]}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </details>
        )}
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

function TicketSummaryList({
  tickets,
  emptyIcon,
  emptyTitle,
  emptyBody,
  indicator,
  onOpen,
}: {
  tickets: TicketRef[];
  emptyIcon: typeof BookOpenCheck;
  emptyTitle: string;
  emptyBody: string;
  indicator: "status" | "assignee";
  onOpen: (ticketId: number) => void;
}) {
  if (tickets.length === 0) {
    return (
      <EmptyState
        icon={emptyIcon}
        title={emptyTitle}
        body={emptyBody}
      />
    );
  }

  return (
    <ul className="mt-4 divide-y divide-border border-y border-border">
      {tickets.map((ticket) => (
        <li key={ticket.id}>
          <button
            type="button"
            className="focus-ring flex min-h-12 w-full flex-wrap items-center gap-x-3 gap-y-2 px-2 py-3 text-left hover:bg-accent/40 sm:flex-nowrap"
            onClick={() => onOpen(ticket.id)}
          >
            <span className="shrink-0 font-mono text-xs text-muted-foreground">
              #{ticket.id}
            </span>
            <span className="min-w-0 flex-1 basis-[12rem]">
              <span className="block truncate text-sm font-medium">
                {ticket.title}
              </span>
              <span className="mt-1 block truncate text-xs text-muted-foreground">
                {ticket.subproject_name ??
                  `Subproject #${ticket.subproject_id}`}
              </span>
            </span>
            {indicator === "status" ? (
              <TicketStatusIndicator
                status={ticket.status}
                className="max-w-full shrink-0"
              />
            ) : (
              <AssigneeIndicator
                assignee={ticket.assignee}
                className="max-w-full shrink-0"
              />
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}

function SessionList({
  sessions,
}: {
  sessions: AgentSession[];
}) {
  return (
    <div>
      <ul className="divide-y divide-border border-y border-border">
        {sessions.map((session) => (
          <li key={session.id} className="py-3">
            <div className="flex flex-wrap items-start gap-3">
              <Clock3
                className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <p className="break-words text-sm font-medium">
                  {session.intent}
                </p>
                <p className="mt-1 break-words text-xs text-muted-foreground">
                  {session.handoff_note}
                </p>
              </div>
              <span className="font-mono text-[0.6875rem] text-muted-foreground">
                Recorded handoff
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}
