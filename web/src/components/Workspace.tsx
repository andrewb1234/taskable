import { useEffect } from "react";
import { KanbanSquare, Loader2, Network } from "lucide-react";
import { useAsync } from "@/hooks/useAsync";
import { useWorkspace } from "@/context/WorkspaceContext";
import { getSubproject } from "@/lib/api";
import type { SSEPayload, SubprojectDetail } from "@/types";
import { SubprojectHeader } from "@/components/SubprojectHeader";
import { KanbanBoard } from "@/components/KanbanBoard";
import { KnowledgePanel } from "@/components/KnowledgePanel";
import { cn } from "@/lib/utils";

interface Props {
  lastEvent: SSEPayload | null;
}

export function Workspace({ lastEvent }: Props) {
  const { activeProjectId, activeSubprojectId, openTicket, view, setView } =
    useWorkspace();
  const subproject = useAsync<SubprojectDetail | null>(
    () =>
      activeSubprojectId == null
        ? Promise.resolve(null)
        : getSubproject(activeSubprojectId),
    [activeSubprojectId],
  );

  // SSE-driven targeted refetch.
  useEffect(() => {
    if (!lastEvent || activeSubprojectId == null) return;
    if (
      (lastEvent.entity === "ticket" &&
        lastEvent.parent_id === activeSubprojectId) ||
      (lastEvent.entity === "subproject" &&
        lastEvent.entity_id === activeSubprojectId)
    ) {
      subproject.refetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent, activeSubprojectId]);

  if (activeProjectId == null) {
    return (
      <main className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Select a project from the sidebar to get started.
      </main>
    );
  }

  return (
    <main className="flex flex-1 flex-col overflow-hidden">
      <nav className="flex items-center gap-1 border-b border-border bg-card/20 px-4 py-2 text-xs">
        <ViewTab
          active={view === "knowledge"}
          onClick={() => setView("knowledge")}
          icon={<Network className="h-3.5 w-3.5" />}
          label="Knowledge"
          hint="Plan upstream"
        />
        <ViewTab
          active={view === "subproject"}
          onClick={() => setView("subproject")}
          icon={<KanbanSquare className="h-3.5 w-3.5" />}
          label="Kanban"
          hint={
            activeSubprojectId == null
              ? "Pick a subproject"
              : "Execute downstream"
          }
        />
      </nav>
      {view === "knowledge" ? (
        <KnowledgePanel projectId={activeProjectId} lastEvent={lastEvent} />
      ) : activeSubprojectId == null ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Select a subproject from the sidebar to open the Kanban board.
        </div>
      ) : subproject.loading && !subproject.data ? (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : subproject.error ? (
        <div className="flex flex-1 items-center justify-center text-sm text-destructive-foreground">
          {subproject.error.message}
        </div>
      ) : subproject.data ? (
        <>
          <SubprojectHeader
            subproject={subproject.data}
            onSaved={() => subproject.refetch()}
          />
          <KanbanBoard
            subproject={subproject.data}
            onTicketClick={(id) => openTicket(id)}
            onSubprojectRefetch={() => subproject.refetch()}
            lastEvent={lastEvent}
          />
        </>
      ) : null}
    </main>
  );
}

interface ViewTabProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  hint?: string;
}

function ViewTab({ active, onClick, icon, label, hint }: ViewTabProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 rounded-md border px-2.5 py-1 transition-colors",
        active
          ? "border-primary/50 bg-primary/10 text-primary-foreground"
          : "border-transparent text-muted-foreground hover:bg-accent/40",
      )}
    >
      {icon}
      <span className="font-semibold">{label}</span>
      {hint && (
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {hint}
        </span>
      )}
    </button>
  );
}
