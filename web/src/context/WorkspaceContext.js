import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useCallback, useContext, useMemo, useState, } from "react";
const WorkspaceContext = createContext(null);
export function WorkspaceProvider({ children }) {
    const [activeProjectId, setActiveProjectIdRaw] = useState(null);
    const [activeSubprojectId, setActiveSubprojectId] = useState(null);
    const [activeTicketId, setActiveTicketId] = useState(null);
    const [view, setView] = useState("subproject");
    const setActiveProjectId = useCallback((id) => {
        setActiveProjectIdRaw(id);
        // Switching project invalidates subproject/ticket context.
        setActiveSubprojectId(null);
        setActiveTicketId(null);
    }, []);
    const openTicket = useCallback((id) => {
        setActiveTicketId(id);
    }, []);
    const value = useMemo(() => ({
        activeProjectId,
        activeSubprojectId,
        setActiveProjectId,
        setActiveSubprojectId,
        activeTicketId,
        openTicket,
        view,
        setView,
    }), [
        activeProjectId,
        activeSubprojectId,
        activeTicketId,
        setActiveProjectId,
        openTicket,
        view,
    ]);
    return (_jsx(WorkspaceContext.Provider, { value: value, children: children }));
}
export function useWorkspace() {
    const ctx = useContext(WorkspaceContext);
    if (!ctx) {
        throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
    }
    return ctx;
}
