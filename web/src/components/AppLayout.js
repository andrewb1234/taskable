import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Workspace } from "@/components/Workspace";
import { TicketModal } from "@/components/TicketModal";
import { ResizableSplit } from "@/components/ui/resizable-split";
import { useWorkspace } from "@/context/WorkspaceContext";
import { useSSE } from "@/hooks/useSSE";
export function AppLayout() {
    const { activeTicketId, openTicket } = useWorkspace();
    const [lastEvent, setLastEvent] = useState(null);
    useSSE((payload) => {
        setLastEvent(payload);
    });
    return (_jsxs("div", { className: "flex h-screen w-screen overflow-hidden", children: [_jsx(ResizableSplit, { direction: "horizontal", defaultSize: 288, minSize: 200, maxSize: 520, storageKey: "taskable.sidebar.width", first: _jsx(Sidebar, { lastEvent: lastEvent }), second: _jsx(Workspace, { lastEvent: lastEvent }) }), _jsx(TicketModal, { ticketId: activeTicketId, onClose: () => openTicket(null), lastEvent: lastEvent })] }));
}
