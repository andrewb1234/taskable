import { GitPullRequest, Bot, User, HelpCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Ticket, TicketAssignee } from "@/types";

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
  onDragStart?: (e: React.DragEvent<HTMLButtonElement>) => void;
  onDragEnd?: () => void;
}

export function TicketCard({
  ticket,
  onClick,
  isDragging,
  onDragStart,
  onDragEnd,
}: Props) {
  return (
    <button
      draggable
      data-testid={`ticket-${ticket.id}`}
      data-ticket-id={ticket.id}
      data-status={ticket.status}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onClick}
      className={cn(
        "group w-full rounded-md border border-border bg-card p-3 text-left shadow-sm transition hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isDragging && "opacity-60",
      )}
    >
      <div className="mb-1 flex items-start justify-between gap-2">
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
      <div className="mt-2 flex items-center gap-1.5">
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
      </div>
    </button>
  );
}
