import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type WorkspaceView = "subproject" | "knowledge";

interface WorkspaceState {
  activeProjectId: number | null;
  activeSubprojectId: number | null;
  setActiveProjectId: (id: number | null) => void;
  setActiveSubprojectId: (id: number | null) => void;
  activeTicketId: number | null;
  openTicket: (id: number | null) => void;
  view: WorkspaceView;
  setView: (view: WorkspaceView) => void;
}

const WorkspaceContext = createContext<WorkspaceState | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [activeProjectId, setActiveProjectIdRaw] = useState<number | null>(
    null,
  );
  const [activeSubprojectId, setActiveSubprojectId] = useState<number | null>(
    null,
  );
  const [activeTicketId, setActiveTicketId] = useState<number | null>(null);
  const [view, setView] = useState<WorkspaceView>("subproject");

  const setActiveProjectId = useCallback((id: number | null) => {
    setActiveProjectIdRaw(id);
    // Switching project invalidates subproject/ticket context.
    setActiveSubprojectId(null);
    setActiveTicketId(null);
  }, []);

  const openTicket = useCallback((id: number | null) => {
    setActiveTicketId(id);
  }, []);

  const value = useMemo(
    () => ({
      activeProjectId,
      activeSubprojectId,
      setActiveProjectId,
      setActiveSubprojectId,
      activeTicketId,
      openTicket,
      view,
      setView,
    }),
    [
      activeProjectId,
      activeSubprojectId,
      activeTicketId,
      setActiveProjectId,
      openTicket,
      view,
    ],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceState {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  }
  return ctx;
}
