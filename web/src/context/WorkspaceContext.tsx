import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type WorkspaceView = "control" | "subproject" | "knowledge";

interface WorkspaceState {
  activeProjectId: number | null;
  activeSubprojectId: number | null;
  activeProjectName: string | null;
  activeSubprojectName: string | null;
  setActiveProjectId: (id: number | null, name?: string | null) => void;
  setActiveSubprojectId: (id: number | null, name?: string | null) => void;
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
  const [activeSubprojectId, setActiveSubprojectIdRaw] = useState<number | null>(
    null,
  );
  const [activeProjectName, setActiveProjectName] = useState<string | null>(
    null,
  );
  const [activeSubprojectName, setActiveSubprojectName] = useState<
    string | null
  >(null);
  const [activeTicketId, setActiveTicketId] = useState<number | null>(null);
  const [view, setView] = useState<WorkspaceView>("control");

  const setActiveProjectId = useCallback(
    (id: number | null, name: string | null = null) => {
      setActiveProjectIdRaw(id);
      setActiveProjectName(id == null ? null : name);
      // Switching project invalidates subproject/ticket context.
      setActiveSubprojectIdRaw(null);
      setActiveSubprojectName(null);
      setActiveTicketId(null);
      setView("control");
    },
    [],
  );

  const setActiveSubprojectId = useCallback(
    (id: number | null, name: string | null = null) => {
      setActiveSubprojectIdRaw(id);
      setActiveSubprojectName(id == null ? null : name);
      setActiveTicketId(null);
      if (id != null) setView("subproject");
    },
    [],
  );

  const openTicket = useCallback((id: number | null) => {
    setActiveTicketId(id);
  }, []);

  const value = useMemo(
    () => ({
      activeProjectId,
      activeSubprojectId,
      activeProjectName,
      activeSubprojectName,
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
      activeProjectName,
      activeSubprojectName,
      activeTicketId,
      setActiveProjectId,
      setActiveSubprojectId,
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
