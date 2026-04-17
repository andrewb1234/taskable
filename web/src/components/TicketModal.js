import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getTicket, updateTicket } from "@/lib/api";
import { useAsync } from "@/hooks/useAsync";
import { CommentThread } from "@/components/CommentThread";
import { MetadataPane } from "@/components/MetadataPane";
export function TicketModal({ ticketId, onClose, lastEvent }) {
    const isOpen = ticketId != null;
    const ticket = useAsync(() => (ticketId == null ? Promise.resolve(null) : getTicket(ticketId)), [ticketId]);
    // Re-fetch this ticket whenever an SSE event concerns it.
    useEffect(() => {
        if (!lastEvent || ticketId == null)
            return;
        if (lastEvent.entity === "ticket" &&
            lastEvent.entity_id === ticketId) {
            ticket.refetch();
        }
        if (lastEvent.entity === "comment" &&
            lastEvent.parent_id === ticketId) {
            ticket.refetch();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lastEvent, ticketId]);
    return (_jsx(Dialog, { open: isOpen, onOpenChange: (next) => !next && onClose(), children: _jsxs(DialogContent, { className: "max-w-4xl p-0", children: [!ticket.data && ticket.loading && (_jsx("div", { className: "flex items-center justify-center p-10", children: _jsx(Loader2, { className: "h-5 w-5 animate-spin" }) })), ticket.error && (_jsx("div", { className: "p-6 text-sm text-destructive-foreground", children: ticket.error.message })), ticket.data && (_jsx(Body, { ticket: ticket.data, onRefresh: () => ticket.refetch() }))] }) }));
}
function Body({ ticket, onRefresh, }) {
    const [title, setTitle] = useState(ticket.title);
    const [description, setDescription] = useState(ticket.description ?? "");
    const [saving, setSaving] = useState(false);
    useEffect(() => {
        setTitle(ticket.title);
        setDescription(ticket.description ?? "");
    }, [ticket.id, ticket.title, ticket.description]);
    const dirty = title !== ticket.title || description !== (ticket.description ?? "");
    async function saveContent() {
        setSaving(true);
        try {
            await updateTicket(ticket.id, {
                title: title.trim() || ticket.title,
                description,
            });
            onRefresh();
        }
        finally {
            setSaving(false);
        }
    }
    return (_jsxs("div", { className: "grid max-h-[85vh] grid-cols-[1fr_280px] gap-0", children: [_jsxs("div", { className: "flex min-h-0 flex-col border-r border-border", children: [_jsxs(DialogHeader, { children: [_jsxs("div", { className: "flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground", children: ["Ticket #", ticket.id] }), _jsx(Input, { value: title, onChange: (e) => setTitle(e.target.value), className: "h-10 border-none bg-transparent px-0 text-xl font-semibold shadow-none focus-visible:ring-0" }), _jsx(DialogTitle, { className: "sr-only", children: ticket.title }), _jsx(DialogDescription, { className: "sr-only", children: "Editable ticket details and discussion" })] }), _jsxs("div", { className: "flex min-h-0 flex-1 flex-col gap-3 px-6 pb-6", children: [_jsxs("div", { children: [_jsx("label", { className: "mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Description" }), _jsx(Textarea, { value: description, onChange: (e) => setDescription(e.target.value), rows: 4 }), _jsx("div", { className: "mt-2 flex justify-end", children: _jsxs(Button, { size: "sm", disabled: !dirty || saving, onClick: saveContent, children: [_jsx(Save, { className: "mr-1 h-3.5 w-3.5" }), saving ? "Saving…" : "Save description"] }) })] }), _jsx("div", { className: "min-h-0 flex-1", children: _jsx(CommentThread, { ticketId: ticket.id, comments: ticket.comments, onPosted: onRefresh }) })] })] }), _jsx("aside", { className: "bg-card/40 p-6", children: _jsx(MetadataPane, { ticket: ticket, onChanged: onRefresh }) })] }));
}
