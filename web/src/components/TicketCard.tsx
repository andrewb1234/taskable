import { GitPullRequest, Bot, User, HelpCircle, Trash2, BookOpen, Link2, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Ticket, TicketAssignee } from "@/types";
import { BLOCKED_BY_LABELS, BLOCKED_BY_COLORS } from "@/types";

const assigneeIcon: Record<TicketAssignee, JSX.Element> = {
  HUMAN: <User className="h-3 w-3" />,
  AGENT: <Bot className="h-3 w-3" />,
  UNASSIGNED: <HelpCircle className="h-3 w-3" />,
};

const assigneeVariant: Record<TicketAssignee, "human" | "agent" | "unassigned"> =
  {
    HUMAN: "human",
    AGENT: "agent",
    UNASSIGNED: "unassigned",
  };

interface Props {
  ticket: Ticket;
  onClick: () => void;
  isDragging?: boolean;
  onDragStart?: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragEnd?: () => void;
  onDelete?: () => void;
}

export function TicketCard({
  ticket,
  onClick,
  isDragging,
  onDragStart,
  onDragEnd,
  onDelete,
}: Props) {
  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      data-testid={`ticket-${ticket.id}`}
      data-ticket-id={ticket.id}
      data-status={ticket.status}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        "group relative w-full cursor-pointer rounded-md border border-border bg-card p-3 text-left shadow-sm transition hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isDragging && "opacity-60",
      )}
    >
      {onDelete && (
        <button
          type="button"
          aria-label={`Delete ticket ${ticket.title}`}
          className="absolute right-1 top-1 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/20 hover:text-destructive-foreground group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          <Trash2 className="h-3 w-3" />
        </button>
      )}
      <div className="mb-1 flex items-start justify-between gap-2 pr-6">
        <p className="line-clamp-2 text-sm font-medium leading-snug">
          {ticket.title}
        </p>
        <span className="shrink-0 text-[10px] text-muted-foreground">
          #{ticket.id}
        </span>
      </div>
      {ticket.description && (
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {ticket.description}
        </p>
      )}
      {ticket.status === "BLOCKED" && ticket.blocked_by && (
        <div
          className={cn(
            "mt-1.5 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium",
            BLOCKED_BY_COLORS[ticket.blocked_by],
          )}
          title={ticket.blocked_reason ?? undefined}
        >
          {BLOCKED_BY_LABELS[ticket.blocked_by]}
        </div>
      )}
      {ticket.depends_on && ticket.depends_on.length > 0 && (
        <div className="mt-1.5 flex items-center gap-1 text-[10px] text-muted-foreground">
          <Link2 className="h-3 w-3" />
          <span>depends on #{ticket.depends_on.join(", #")}</span>
        </div>
      )}
      {ticket.claimed_by && (
        <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
          <Clock className="h-3 w-3" />
          <span>claimed by {ticket.claimed_by}</span>
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <Badge
          variant={assigneeVariant[ticket.assignee]}
          className="flex items-center gap-1"
        >
          {assigneeIcon[ticket.assignee]}
          <span>{ticket.assignee.toLowerCase()}</span>
        </Badge>
        {ticket.mr_link && (
          <a
            href={ticket.mr_link}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted/80"
            onClick={(e) => e.stopPropagation()}
          >
            <GitPullRequest className="h-3 w-3" />
            MR
          </a>
        )}
        {ticket.source_refs && ticket.source_refs.length > 0 && (
          <span
            className="flex items-center gap-0.5 rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
            title={ticket.source_refs.join(", ")}
          >
            <BookOpen className="h-3 w-3" />
            {ticket.source_refs.length}
          </span>
        )}
      </div>
    </div>
  );
}
