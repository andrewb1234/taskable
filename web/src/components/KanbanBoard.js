import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { TicketCard } from "@/components/TicketCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { createTicket, deleteTicket, updateTicket } from "@/lib/api";
import { ASSIGNEE_LABELS, TICKET_STATUSES, TICKET_STATUS_LABELS, } from "@/types";
import { cn } from "@/lib/utils";
export function KanbanBoard({ subproject, onTicketClick, onSubprojectRefetch, }) {
    const [draggingId, setDraggingId] = useState(null);
    const [optimistic, setOptimistic] = useState({});
    // Drop the optimistic override once real data catches up.
    useEffect(() => {
        setOptimistic((prev) => {
            const next = {};
            for (const [id, status] of Object.entries(prev)) {
                const ticket = subproject.tickets.find((t) => t.id === Number(id));
                if (ticket && ticket.status !== status)
                    next[Number(id)] = status;
            }
            return next;
        });
    }, [subproject.tickets]);
    const ticketsByStatus = useMemo(() => {
        const grouped = {
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
    const handleDelete = useCallback(async (ticket) => {
        if (!window.confirm(`Delete ticket "${ticket.title}"?`))
            return;
        try {
            await deleteTicket(ticket.id);
            onSubprojectRefetch();
        }
        catch {
            onSubprojectRefetch();
        }
    }, [onSubprojectRefetch]);
    const handleDrop = useCallback(async (targetStatus) => {
        if (draggingId == null)
            return;
        const ticket = subproject.tickets.find((t) => t.id === draggingId);
        setDraggingId(null);
        if (!ticket || ticket.status === targetStatus)
            return;
        // Optimistic update; the SSE refetch will reconcile.
        setOptimistic((prev) => ({ ...prev, [ticket.id]: targetStatus }));
        try {
            await updateTicket(ticket.id, { status: targetStatus });
        }
        catch {
            // Revert on failure so UX doesn't desync.
            setOptimistic((prev) => {
                const { [ticket.id]: _, ...rest } = prev;
                return rest;
            });
            onSubprojectRefetch();
        }
    }, [draggingId, subproject.tickets, onSubprojectRefetch]);
    return (_jsx("div", { className: "flex-1 overflow-hidden px-4 py-4", children: _jsx("div", { className: "flex h-full gap-3 overflow-x-auto", children: TICKET_STATUSES.map((status) => (_jsx(KanbanColumn, { status: status, tickets: ticketsByStatus[status], subprojectId: subproject.id, onTicketClick: onTicketClick, onTicketDelete: handleDelete, onCreated: onSubprojectRefetch, onDropTicket: () => handleDrop(status), onDragStart: (id) => setDraggingId(id), onDragEnd: () => setDraggingId(null), isDropTarget: draggingId != null }, status))) }) }));
}
function KanbanColumn({ status, tickets, subprojectId, onTicketClick, onTicketDelete, onCreated, onDropTicket, onDragStart, onDragEnd, isDropTarget, }) {
    const [hover, setHover] = useState(false);
    const [creating, setCreating] = useState(false);
    return (_jsxs("section", { "data-testid": `column-${status}`, "data-status": status, onDragOver: (e) => {
            if (!isDropTarget)
                return;
            e.preventDefault();
            setHover(true);
        }, onDragLeave: () => setHover(false), onDrop: () => {
            setHover(false);
            onDropTicket();
        }, className: cn("kanban-column flex h-full w-80 shrink-0 flex-col rounded-lg border border-border bg-background/40 transition-colors", hover && "border-primary/60 bg-primary/5"), children: [_jsxs("header", { className: "flex items-center justify-between border-b border-border px-3 py-2", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx("h3", { className: "text-xs font-semibold uppercase tracking-wider text-muted-foreground", children: TICKET_STATUS_LABELS[status] }), _jsx("span", { className: "rounded-full bg-muted px-1.5 text-[10px] text-muted-foreground", children: tickets.length })] }), status === "TODO" && (_jsx(Button, { size: "icon", variant: "ghost", className: "h-6 w-6", onClick: () => setCreating((v) => !v), "aria-label": "New ticket", children: _jsx(Plus, { className: "h-3.5 w-3.5" }) }))] }), _jsxs("div", { className: "flex-1 space-y-2 overflow-y-auto p-2", children: [creating && (_jsx(NewTicketForm, { subprojectId: subprojectId, onClose: () => setCreating(false), onCreated: () => {
                            onCreated();
                            setCreating(false);
                        } })), tickets.map((ticket) => (_jsx(TicketCard, { ticket: ticket, onClick: () => onTicketClick(ticket.id), onDelete: () => onTicketDelete(ticket), onDragStart: (e) => {
                            onDragStart(ticket.id);
                            e.dataTransfer.effectAllowed = "move";
                            e.dataTransfer.setData("text/plain", String(ticket.id));
                        }, onDragEnd: onDragEnd }, ticket.id))), tickets.length === 0 && !creating && (_jsx("p", { className: "mt-4 text-center text-[11px] text-muted-foreground", children: "Empty" }))] })] }));
}
function NewTicketForm({ subprojectId, onClose, onCreated, }) {
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [assignee, setAssignee] = useState("UNASSIGNED");
    const [saving, setSaving] = useState(false);
    async function submit(e) {
        e.preventDefault();
        if (!title.trim())
            return;
        setSaving(true);
        try {
            await createTicket(subprojectId, {
                title: title.trim(),
                description: description.trim() || undefined,
                assignee,
            });
            onCreated();
        }
        finally {
            setSaving(false);
        }
    }
    return (_jsxs("form", { onSubmit: submit, className: "space-y-2 rounded-md border border-border bg-card p-2 text-xs", children: [_jsx(Input, { autoFocus: true, value: title, onChange: (e) => setTitle(e.target.value), placeholder: "Ticket title", className: "h-8 text-xs" }), _jsx(Textarea, { value: description, onChange: (e) => setDescription(e.target.value), placeholder: "Description", className: "min-h-[60px] text-xs" }), _jsxs(Select, { value: assignee, onValueChange: (v) => setAssignee(v), children: [_jsx(SelectTrigger, { className: "h-8 text-xs", children: _jsx(SelectValue, {}) }), _jsx(SelectContent, { children: ["UNASSIGNED", "HUMAN", "AGENT"].map((role) => (_jsx(SelectItem, { value: role, children: ASSIGNEE_LABELS[role] }, role))) })] }), _jsxs("div", { className: "flex justify-end gap-1", children: [_jsx(Button, { type: "button", variant: "ghost", size: "sm", onClick: onClose, children: "Cancel" }), _jsx(Button, { type: "submit", size: "sm", disabled: saving, children: saving ? _jsx(Loader2, { className: "h-3 w-3 animate-spin" }) : "Create" })] })] }));
}
