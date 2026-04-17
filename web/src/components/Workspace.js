import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useAsync } from "@/hooks/useAsync";
import { useWorkspace } from "@/context/WorkspaceContext";
import { getSubproject } from "@/lib/api";
import { SubprojectHeader } from "@/components/SubprojectHeader";
import { KanbanBoard } from "@/components/KanbanBoard";
export function Workspace({ lastEvent }) {
    const { activeSubprojectId, openTicket } = useWorkspace();
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
    if (activeSubprojectId == null) {
        return (_jsx("main", { className: "flex flex-1 items-center justify-center text-sm text-muted-foreground", children: "Select a subproject from the sidebar to get started." }));
    }
    if (subproject.loading && !subproject.data) {
        return (_jsx("main", { className: "flex flex-1 items-center justify-center", children: _jsx(Loader2, { className: "h-5 w-5 animate-spin text-muted-foreground" }) }));
    }
    if (subproject.error) {
        return (_jsx("main", { className: "flex flex-1 items-center justify-center text-sm text-destructive-foreground", children: subproject.error.message }));
    }
    if (!subproject.data)
        return null;
    return (_jsxs("main", { className: "flex flex-1 flex-col overflow-hidden", children: [_jsx(SubprojectHeader, { subproject: subproject.data, onSaved: () => subproject.refetch() }), _jsx(KanbanBoard, { subproject: subproject.data, onTicketClick: (id) => openTicket(id), onSubprojectRefetch: () => subproject.refetch(), lastEvent: lastEvent })] }));
}
