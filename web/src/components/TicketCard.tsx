import {
  BookOpen,
  Bot,
  CheckCircle2,
  Clock3,
  GitPullRequest,
  HelpCircle,
  Link2,
  OctagonAlert,
  Trash2,
  User,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Ticket, TicketAssignee, TicketRef, TicketStatus } from "@/types";
import {
  ASSIGNEE_LABELS,
  BLOCKED_BY_LABELS,
  TICKET_STATUS_LABELS,
} from "@/types";

const assigneeIcon: Record<TicketAssignee, React.JSX.Element> = {
  HUMAN: <User className="h-3 w-3" aria-hidden />,
  AGENT: <Bot className="h-3 w-3" aria-hidden />,
  UNASSIGNED: <HelpCircle className="h-3 w-3" aria-hidden />,
};

const assigneeVariant: Record<TicketAssignee, "human" | "agent" | "unassigned"> =
  {
    HUMAN: "human",
    AGENT: "agent",
    UNASSIGNED: "unassigned",
  };

const dependencyVariant: Record<
  TicketStatus,
  "todo" | "inprogress" | "blocked" | "review" | "done"
> = {
  TODO: "todo",
  IN_PROGRESS: "inprogress",
  BLOCKED: "blocked",
  REVIEW: "review",
  DONE: "done",
};

interface Props {
  ticket: Ticket;
  onClick: () => void;
  onDelete?: () => void;
}

export function TicketCard({ ticket, onClick, onDelete }: Props) {
  const leaseExpiry = ticket.lease_expires_at
    ? new Date(
        ticket.lease_expires_at.endsWith("Z")
          ? ticket.lease_expires_at
          : `${ticket.lease_expires_at}Z`,
      )
    : null;
  const leaseExpired =
    leaseExpiry != null && leaseExpiry.getTime() <= Date.now();

  return (
    <article
      data-testid={`ticket-${ticket.id}`}
      data-ticket-id={ticket.id}
      data-status={ticket.status}
      className="group relative overflow-hidden border border-border bg-card shadow-sm transition-fast hover:border-brand-brass/60 hover:shadow-md"
    >
      <button
        type="button"
        onClick={onClick}
        className="focus-ring block min-h-11 w-full p-3 pr-10 text-left"
        aria-label={`Open ticket #${ticket.id}: ${ticket.title}`}
      >
        <div className="flex items-start gap-3">
          <span className="shrink-0 font-mono text-[10px] font-semibold text-brand-brass">
            #{ticket.id}
          </span>
          <h4
            className="min-w-0 flex-1 line-clamp-2 text-sm font-semibold leading-snug"
            title={ticket.title}
          >
            {ticket.title}
          </h4>
        </div>

        {ticket.description && (
          <p
            className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground"
            title={ticket.description}
          >
            {ticket.description}
          </p>
        )}

        {ticket.status === "BLOCKED" && ticket.blocked_by && (
          <div className="mt-2 flex min-w-0 items-start gap-1.5 border-l-2 border-status-blocked-border pl-2 text-[10px] text-status-blocked-foreground">
            <OctagonAlert className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
            <span className="min-w-0">
              <strong>{BLOCKED_BY_LABELS[ticket.blocked_by]}</strong>
              {ticket.blocked_reason && (
                <span className="block truncate" title={ticket.blocked_reason}>
                  {ticket.blocked_reason}
                </span>
              )}
            </span>
          </div>
        )}

        {ticket.depends_on.length > 0 && (
          <div className="mt-2">
            <div className="mb-1 flex items-center gap-1 font-mono text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
              <Link2 className="h-3 w-3" aria-hidden />
              Dependencies
            </div>
            <div className="flex flex-wrap gap-1">
              {ticket.depends_on_refs?.length
                ? ticket.depends_on_refs.map((depRef) => (
                    <DependencyChip key={depRef.id} depRef={depRef} />
                  ))
                : ticket.depends_on.map((id) => (
                    <Badge
                      key={id}
                      variant="todo"
                      className="max-w-full gap-1 px-1.5 py-0 text-[9px]"
                    >
                      <span className="font-mono">#{id}</span>
                    </Badge>
                  ))}
            </div>
          </div>
        )}

        {ticket.claimed_by && (
          <div
            className={cn(
              "mt-2 flex min-w-0 items-center gap-1.5 text-[10px]",
              leaseExpired
                ? "text-status-blocked-foreground"
                : "text-status-progress-foreground",
            )}
          >
            <Clock3 className="h-3 w-3 shrink-0" aria-hidden />
            <span className="min-w-0 truncate" title={ticket.claimed_by}>
              {ticket.claimed_by}
            </span>
            <span className="shrink-0" aria-hidden>·</span>
            <span className="shrink-0 font-semibold">
              {leaseExpired ? "Lease expired" : "Lease active"}
            </span>
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <Badge
            variant={assigneeVariant[ticket.assignee]}
            className="gap-1 px-1.5 py-0 text-[9px]"
          >
            {assigneeIcon[ticket.assignee]}
            <span>{ASSIGNEE_LABELS[ticket.assignee]}</span>
          </Badge>
          {ticket.mr_link && (
            <Badge
              variant="review"
              className="gap-1 px-1.5 py-0 text-[9px]"
            >
              <GitPullRequest className="h-3 w-3" aria-hidden />
              MR linked
            </Badge>
          )}
          {ticket.source_refs.length > 0 && (
            <Badge
              variant="outline"
              className="gap-1 px-1.5 py-0 text-[9px] text-muted-foreground"
            >
              <BookOpen className="h-3 w-3" aria-hidden />
              {ticket.source_refs.length} evidence
            </Badge>
          )}
        </div>
      </button>

      {onDelete && (
        <button
          type="button"
          aria-label={`Delete ticket ${ticket.title}`}
          className="focus-ring absolute right-2 top-2 flex h-8 w-8 items-center justify-center text-muted-foreground transition-fast hover:bg-destructive/10 hover:text-destructive"
          onClick={onDelete}
        >
          <Trash2 className="h-3.5 w-3.5" aria-hidden />
        </button>
      )}

      {ticket.mr_link && (
        <a
          href={ticket.mr_link}
          target="_blank"
          rel="noopener noreferrer"
          className="focus-ring flex min-h-11 items-center justify-between border-t border-border px-3 py-2 text-[10px] font-semibold text-muted-foreground hover:bg-accent/50 hover:text-foreground sm:min-h-9"
          aria-label={`Open merge request for ticket #${ticket.id}`}
        >
          <span className="flex items-center gap-1.5">
            <GitPullRequest className="h-3 w-3" aria-hidden />
            Review merge request
          </span>
          <span aria-hidden>↗</span>
        </a>
      )}
    </article>
  );
}

function DependencyChip({ depRef }: { depRef: TicketRef }) {
  const done = depRef.status === "DONE";
  return (
    <Badge
      variant={dependencyVariant[depRef.status]}
      className="max-w-full gap-1 px-1.5 py-0 text-[9px]"
      title={`${TICKET_STATUS_LABELS[depRef.status]} · ${
        depRef.subproject_name ?? "same subproject"
      } · ${depRef.title}`}
    >
      {done ? (
        <CheckCircle2 className="h-2.5 w-2.5 shrink-0" aria-hidden />
      ) : (
        <span className="font-mono">{TICKET_STATUS_LABELS[depRef.status]}</span>
      )}
      <span className="max-w-32 truncate font-mono">#{depRef.id}</span>
      {depRef.subproject_name && (
        <span className="max-w-24 truncate opacity-70">
          {depRef.subproject_name}
        </span>
      )}
    </Badge>
  );
}
