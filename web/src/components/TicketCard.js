import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { GitPullRequest, Bot, User, HelpCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
const assigneeIcon = {
    HUMAN: _jsx(User, { className: "h-3 w-3" }),
    AGENT: _jsx(Bot, { className: "h-3 w-3" }),
    UNASSIGNED: _jsx(HelpCircle, { className: "h-3 w-3" }),
};
const assigneeVariant = {
    HUMAN: "human",
    AGENT: "agent",
    UNASSIGNED: "unassigned",
};
export function TicketCard({ ticket, onClick, isDragging, onDragStart, onDragEnd, }) {
    return (_jsxs("button", { draggable: true, onDragStart: onDragStart, onDragEnd: onDragEnd, onClick: onClick, className: cn("group w-full rounded-md border border-border bg-card p-3 text-left shadow-sm transition hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", isDragging && "opacity-60"), children: [_jsxs("div", { className: "mb-1 flex items-start justify-between gap-2", children: [_jsx("p", { className: "line-clamp-2 text-sm font-medium leading-snug", children: ticket.title }), _jsxs("span", { className: "shrink-0 text-[10px] text-muted-foreground", children: ["#", ticket.id] })] }), ticket.description && (_jsx("p", { className: "line-clamp-2 text-xs text-muted-foreground", children: ticket.description })), _jsxs("div", { className: "mt-2 flex items-center gap-1.5", children: [_jsxs(Badge, { variant: assigneeVariant[ticket.assignee], className: "flex items-center gap-1", children: [assigneeIcon[ticket.assignee], _jsx("span", { children: ticket.assignee.toLowerCase() })] }), ticket.mr_link && (_jsxs("a", { href: ticket.mr_link, target: "_blank", rel: "noopener noreferrer", className: "flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted/80", onClick: (e) => e.stopPropagation(), children: [_jsx(GitPullRequest, { className: "h-3 w-3" }), "MR"] }))] })] }));
}
