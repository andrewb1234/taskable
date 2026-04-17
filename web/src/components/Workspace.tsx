import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useAsync } from "@/hooks/useAsync";
import { useWorkspace } from "@/context/WorkspaceContext";
import { getSubproject } from "@/lib/api";
import type { SSEPayload, SubprojectDetail } from "@/types";
import { SubprojectHeader } from "@/components/SubprojectHeader";
import { KanbanBoard } from "@/components/KanbanBoard";

interface Props {
  lastEvent: SSEPayload | null;
}

export function Workspace({ lastEvent }: Props) {
  const { activeSubprojectId, openTicket } = useWorkspace();
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

  if (activeSubprojectId == null) {
    return (
      <main className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Select a subproject from the sidebar to get started.
      </main>
    );
  }

  if (subproject.loading && !subproject.data) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </main>
    );
  }

  if (subproject.error) {
    return (
      <main className="flex flex-1 items-center justify-center text-sm text-destructive-foreground">
        {subproject.error.message}
      </main>
    );
  }

  if (!subproject.data) return null;

  return (
    <main className="flex flex-1 flex-col overflow-hidden">
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
    </main>
  );
}
