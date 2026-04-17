import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getTicket, updateTicket } from "@/lib/api";
import { useAsync } from "@/hooks/useAsync";
import type { SSEPayload, TicketDetail } from "@/types";
import { CommentThread } from "@/components/CommentThread";
import { MetadataPane } from "@/components/MetadataPane";

interface Props {
  ticketId: number | null;
  onClose: () => void;
  lastEvent: SSEPayload | null;
}

export function TicketModal({ ticketId, onClose, lastEvent }: Props) {
  const isOpen = ticketId != null;
  const ticket = useAsync<TicketDetail | null>(
    () => (ticketId == null ? Promise.resolve(null) : getTicket(ticketId)),
    [ticketId],
  );

  // Re-fetch this ticket whenever an SSE event concerns it.
  useEffect(() => {
    if (!lastEvent || ticketId == null) return;
    if (
      lastEvent.entity === "ticket" &&
      lastEvent.entity_id === ticketId
    ) {
      ticket.refetch();
    }
    if (
      lastEvent.entity === "comment" &&
      lastEvent.parent_id === ticketId
    ) {
      ticket.refetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent, ticketId]);

  return (
    <Dialog open={isOpen} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-4xl p-0">
        {!ticket.data && ticket.loading && (
          <div className="flex items-center justify-center p-10">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        )}
        {ticket.error && (
          <div className="p-6 text-sm text-destructive-foreground">
            {ticket.error.message}
          </div>
        )}
        {ticket.data && (
          <Body ticket={ticket.data} onRefresh={() => ticket.refetch()} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function Body({
  ticket,
  onRefresh,
}: {
  ticket: TicketDetail;
  onRefresh: () => void;
}) {
  const [title, setTitle] = useState(ticket.title);
  const [description, setDescription] = useState(ticket.description ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTitle(ticket.title);
    setDescription(ticket.description ?? "");
  }, [ticket.id, ticket.title, ticket.description]);

  const dirty =
    title !== ticket.title || description !== (ticket.description ?? "");

  async function saveContent() {
    setSaving(true);
    try {
      await updateTicket(ticket.id, {
        title: title.trim() || ticket.title,
        description,
      });
      onRefresh();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid max-h-[85vh] grid-cols-[1fr_280px] gap-0">
      <div className="flex min-h-0 flex-col border-r border-border">
        <DialogHeader>
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
            Ticket #{ticket.id}
          </div>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="h-10 border-none bg-transparent px-0 text-xl font-semibold shadow-none focus-visible:ring-0"
          />
          <DialogTitle className="sr-only">{ticket.title}</DialogTitle>
          <DialogDescription className="sr-only">
            Editable ticket details and discussion
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-3 px-6 pb-6">
          <div>
            <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Description
            </label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
            />
            <div className="mt-2 flex justify-end">
              <Button
                size="sm"
                disabled={!dirty || saving}
                onClick={saveContent}
              >
                <Save className="mr-1 h-3.5 w-3.5" />
                {saving ? "Saving…" : "Save description"}
              </Button>
            </div>
          </div>
          <div className="min-h-0 flex-1">
            <CommentThread
              ticketId={ticket.id}
              comments={ticket.comments}
              onPosted={onRefresh}
            />
          </div>
        </div>
      </div>
      <aside className="bg-card/40 p-6">
        <MetadataPane ticket={ticket} onChanged={onRefresh} />
      </aside>
    </div>
  );
}
