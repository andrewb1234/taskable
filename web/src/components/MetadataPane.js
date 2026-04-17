import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { GitPullRequest, Link as LinkIcon, Save } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ASSIGNEE_LABELS, TICKET_STATUSES, TICKET_STATUS_LABELS, } from "@/types";
import { linkTicketMR, updateTicket } from "@/lib/api";
const ASSIGNEES = ["UNASSIGNED", "HUMAN", "AGENT"];
export function MetadataPane({ ticket, onChanged }) {
    const [mrUrl, setMrUrl] = useState(ticket.mr_link ?? "");
    const [savingMR, setSavingMR] = useState(false);
    async function setStatus(status) {
        await updateTicket(ticket.id, { status });
        onChanged();
    }
    async function setAssignee(assignee) {
        await updateTicket(ticket.id, { assignee });
        onChanged();
    }
    async function saveMR(e) {
        e.preventDefault();
        if (!mrUrl.trim())
            return;
        setSavingMR(true);
        try {
            await linkTicketMR(ticket.id, mrUrl.trim());
            onChanged();
        }
        finally {
            setSavingMR(false);
        }
    }
    return (_jsxs("div", { className: "space-y-4 text-sm", children: [_jsxs("div", { children: [_jsx("label", { className: "mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Status" }), _jsxs(Select, { value: ticket.status, onValueChange: (v) => void setStatus(v), children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, {}) }), _jsx(SelectContent, { children: TICKET_STATUSES.map((s) => (_jsx(SelectItem, { value: s, children: TICKET_STATUS_LABELS[s] }, s))) })] })] }), _jsxs("div", { children: [_jsx("label", { className: "mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Assignee" }), _jsxs(Select, { value: ticket.assignee, onValueChange: (v) => void setAssignee(v), children: [_jsx(SelectTrigger, { children: _jsx(SelectValue, {}) }), _jsx(SelectContent, { children: ASSIGNEES.map((a) => (_jsx(SelectItem, { value: a, children: ASSIGNEE_LABELS[a] }, a))) })] })] }), _jsxs("div", { children: [_jsxs("label", { className: "mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: [_jsx(GitPullRequest, { className: "h-3 w-3" }), "Merge Request"] }), _jsxs("form", { onSubmit: saveMR, className: "flex items-center gap-2", children: [_jsx(Input, { value: mrUrl, onChange: (e) => setMrUrl(e.target.value), placeholder: "https://github.com/org/repo/pull/123", className: "h-8 text-xs" }), _jsx(Button, { type: "submit", size: "icon", variant: "outline", className: "h-8 w-8", disabled: savingMR, "aria-label": "Attach MR", children: _jsx(Save, { className: "h-3.5 w-3.5" }) })] }), ticket.mr_link && (_jsxs("a", { href: ticket.mr_link, target: "_blank", rel: "noopener noreferrer", className: "mt-2 flex items-center gap-1 text-[11px] text-primary underline-offset-2 hover:underline", children: [_jsx(LinkIcon, { className: "h-3 w-3" }), "Current link"] }))] }), ticket.audit_logs.length > 0 && (_jsxs("div", { children: [_jsx("label", { className: "mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Audit Ledger" }), _jsx("ul", { className: "space-y-1 text-[11px] text-muted-foreground", children: ticket.audit_logs
                            .slice()
                            .reverse()
                            .slice(0, 8)
                            .map((log) => (_jsxs("li", { className: "flex justify-between gap-2", children: [_jsxs("span", { className: "truncate", children: [_jsx("strong", { className: "text-foreground/80", children: log.actor }), " ", log.action.replace("_", " ").toLowerCase()] }), _jsx("span", { className: "shrink-0", children: new Date(log.timestamp + "Z").toLocaleTimeString() })] }, log.id))) })] }))] }));
}
