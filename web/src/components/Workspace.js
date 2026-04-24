import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect } from "react";
import { KanbanSquare, Loader2, Network } from "lucide-react";
import { useAsync } from "@/hooks/useAsync";
import { useWorkspace } from "@/context/WorkspaceContext";
import { getSubproject } from "@/lib/api";
import { SubprojectHeader } from "@/components/SubprojectHeader";
import { KanbanBoard } from "@/components/KanbanBoard";
import { KnowledgePanel } from "@/components/KnowledgePanel";
import { cn } from "@/lib/utils";
export function Workspace({ lastEvent }) {
    const { activeProjectId, activeSubprojectId, openTicket, view, setView } = useWorkspace();
    const subproject = useAsync(() => activeSubprojectId == null
        ? Promise.resolve(null)
        : getSubproject(activeSubprojectId), [activeSubprojectId]);
    // SSE-driven targeted refetch.
    useEffect(() => {
        if (!lastEvent || activeSubprojectId == null)
            return;
        if ((lastEvent.entity === "ticket" &&
            lastEvent.parent_id === activeSubprojectId) ||
            (lastEvent.entity === "subproject" &&
                lastEvent.entity_id === activeSubprojectId)) {
            subproject.refetch();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lastEvent, activeSubprojectId]);
    if (activeProjectId == null) {
        return (_jsx("main", { className: "flex flex-1 items-center justify-center text-sm text-muted-foreground", children: "Select a project from the sidebar to get started." }));
    }
    return (_jsxs("main", { className: "flex flex-1 flex-col overflow-hidden", children: [_jsxs("nav", { className: "flex items-center gap-1 border-b border-border bg-card/20 px-4 py-2 text-xs", children: [_jsx(ViewTab, { active: view === "knowledge", onClick: () => setView("knowledge"), icon: _jsx(Network, { className: "h-3.5 w-3.5" }), label: "Knowledge", hint: "Plan upstream" }), _jsx(ViewTab, { active: view === "subproject", onClick: () => setView("subproject"), icon: _jsx(KanbanSquare, { className: "h-3.5 w-3.5" }), label: "Kanban", hint: activeSubprojectId == null
                            ? "Pick a subproject"
                            : "Execute downstream" })] }), view === "knowledge" ? (_jsx(KnowledgePanel, { projectId: activeProjectId, lastEvent: lastEvent })) : activeSubprojectId == null ? (_jsx("div", { className: "flex flex-1 items-center justify-center text-sm text-muted-foreground", children: "Select a subproject from the sidebar to open the Kanban board." })) : subproject.loading && !subproject.data ? (_jsx("div", { className: "flex flex-1 items-center justify-center", children: _jsx(Loader2, { className: "h-5 w-5 animate-spin text-muted-foreground" }) })) : subproject.error ? (_jsx("div", { className: "flex flex-1 items-center justify-center text-sm text-destructive-foreground", children: subproject.error.message })) : subproject.data ? (_jsxs(_Fragment, { children: [_jsx(SubprojectHeader, { subproject: subproject.data, onSaved: () => subproject.refetch() }), _jsx(KanbanBoard, { subproject: subproject.data, onTicketClick: (id) => openTicket(id), onSubprojectRefetch: () => subproject.refetch(), lastEvent: lastEvent })] })) : null] }));
}
function ViewTab({ active, onClick, icon, label, hint }) {
    return (_jsxs("button", { type: "button", onClick: onClick, className: cn("flex items-center gap-1.5 rounded-md border px-2.5 py-1 transition-colors", active
            ? "border-primary/50 bg-primary/10 text-primary-foreground"
            : "border-transparent text-muted-foreground hover:bg-accent/40"), children: [icon, _jsx("span", { className: "font-semibold", children: label }), hint && (_jsx("span", { className: "text-[10px] uppercase tracking-wide text-muted-foreground", children: hint }))] }));
}
