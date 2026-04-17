import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { TicketCard } from "@/components/TicketCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { createTicket, updateTicket } from "@/lib/api";
import type {
  SSEPayload,
  SubprojectDetail,
  Ticket,
  TicketAssignee,
  TicketStatus,
} from "@/types";
import {
  ASSIGNEE_LABELS,
  TICKET_STATUSES,
  TICKET_STATUS_LABELS,
} from "@/types";
import { cn } from "@/lib/utils";

interface Props {
  subproject: SubprojectDetail;
  onTicketClick: (ticketId: number) => void;
  onSubprojectRefetch: () => void;
  lastEvent: SSEPayload | null;
}

export function KanbanBoard({
  subproject,
  onTicketClick,
  onSubprojectRefetch,
}: Props) {
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [optimistic, setOptimistic] = useState<Record<number, TicketStatus>>(
    {},
  );

  // Drop the optimistic override once real data catches up.
  useEffect(() => {
    setOptimistic((prev) => {
      const next: typeof prev = {};
      for (const [id, status] of Object.entries(prev)) {
        const ticket = subproject.tickets.find((t) => t.id === Number(id));
        if (ticket && ticket.status !== status) next[Number(id)] = status;
      }
      return next;
    });
  }, [subproject.tickets]);

  const ticketsByStatus = useMemo(() => {
    const grouped: Record<TicketStatus, Ticket[]> = {
      TODO: [],
      IN_PROGRESS: [],
      BLOCKED: [],
      REVIEW: [],
      DONE: [],
    };
    for (const ticket of subproject.tickets) {
      const effective = optimistic[ticket.id] ?? ticket.status;
      grouped[effective].push(ticket);
    }
    return grouped;
  }, [subproject.tickets, optimistic]);

  const handleDrop = useCallback(
    async (targetStatus: TicketStatus) => {
      if (draggingId == null) return;
      const ticket = subproject.tickets.find((t) => t.id === draggingId);
      setDraggingId(null);
      if (!ticket || ticket.status === targetStatus) return;
      // Optimistic update; the SSE refetch will reconcile.
      setOptimistic((prev) => ({ ...prev, [ticket.id]: targetStatus }));
      try {
        await updateTicket(ticket.id, { status: targetStatus });
      } catch {
        // Revert on failure so UX doesn't desync.
        setOptimistic((prev) => {
          const { [ticket.id]: _, ...rest } = prev;
          return rest;
        });
        onSubprojectRefetch();
      }
    },
    [draggingId, subproject.tickets, onSubprojectRefetch],
  );

  return (
    <div className="flex-1 overflow-hidden px-4 py-4">
      <div className="flex h-full gap-3 overflow-x-auto">
        {TICKET_STATUSES.map((status) => (
          <KanbanColumn
            key={status}
            status={status}
            tickets={ticketsByStatus[status]}
            subprojectId={subproject.id}
            onTicketClick={onTicketClick}
            onCreated={onSubprojectRefetch}
            onDropTicket={() => handleDrop(status)}
            onDragStart={(id) => setDraggingId(id)}
            onDragEnd={() => setDraggingId(null)}
            isDropTarget={draggingId != null}
          />
        ))}
      </div>
    </div>
  );
}

interface ColumnProps {
  status: TicketStatus;
  tickets: Ticket[];
  subprojectId: number;
  onTicketClick: (ticketId: number) => void;
  onCreated: () => void;
  onDropTicket: () => void;
  onDragStart: (ticketId: number) => void;
  onDragEnd: () => void;
  isDropTarget: boolean;
}

function KanbanColumn({
  status,
  tickets,
  subprojectId,
  onTicketClick,
  onCreated,
  onDropTicket,
  onDragStart,
  onDragEnd,
  isDropTarget,
}: ColumnProps) {
  const [hover, setHover] = useState(false);
  const [creating, setCreating] = useState(false);
  return (
    <section
      onDragOver={(e) => {
        if (!isDropTarget) return;
        e.preventDefault();
        setHover(true);
      }}
      onDragLeave={() => setHover(false)}
      onDrop={() => {
        setHover(false);
        onDropTicket();
      }}
      className={cn(
        "kanban-column flex h-full w-80 shrink-0 flex-col rounded-lg border border-border bg-background/40 transition-colors",
        hover && "border-primary/60 bg-primary/5",
      )}
    >
      <header className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {TICKET_STATUS_LABELS[status]}
          </h3>
          <span className="rounded-full bg-muted px-1.5 text-[10px] text-muted-foreground">
            {tickets.length}
          </span>
        </div>
        {status === "TODO" && (
          <Button
            size="icon"
            variant="ghost"
            className="h-6 w-6"
            onClick={() => setCreating((v) => !v)}
            aria-label="New ticket"
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        )}
      </header>
      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {creating && (
          <NewTicketForm
            subprojectId={subprojectId}
            onClose={() => setCreating(false)}
            onCreated={() => {
              onCreated();
              setCreating(false);
            }}
          />
        )}
        {tickets.map((ticket) => (
          <TicketCard
            key={ticket.id}
            ticket={ticket}
            onClick={() => onTicketClick(ticket.id)}
            onDragStart={(e) => {
              onDragStart(ticket.id);
              e.dataTransfer.effectAllowed = "move";
              e.dataTransfer.setData("text/plain", String(ticket.id));
            }}
            onDragEnd={onDragEnd}
          />
        ))}
        {tickets.length === 0 && !creating && (
          <p className="mt-4 text-center text-[11px] text-muted-foreground">
            Empty
          </p>
        )}
      </div>
    </section>
  );
}

function NewTicketForm({
  subprojectId,
  onClose,
  onCreated,
}: {
  subprojectId: number;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assignee, setAssignee] = useState<TicketAssignee>("UNASSIGNED");
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    try {
      await createTicket(subprojectId, {
        title: title.trim(),
        description: description.trim() || undefined,
        assignee,
      });
      onCreated();
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="space-y-2 rounded-md border border-border bg-card p-2 text-xs"
    >
      <Input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Ticket title"
        className="h-8 text-xs"
      />
      <Textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description"
        className="min-h-[60px] text-xs"
      />
      <Select
        value={assignee}
        onValueChange={(v) => setAssignee(v as TicketAssignee)}
      >
        <SelectTrigger className="h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(
            ["UNASSIGNED", "HUMAN", "AGENT"] as TicketAssignee[]
          ).map((role) => (
            <SelectItem key={role} value={role}>
              {ASSIGNEE_LABELS[role]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <div className="flex justify-end gap-1">
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : "Create"}
        </Button>
      </div>
    </form>
  );
}
