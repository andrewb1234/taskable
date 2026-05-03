import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Workspace } from "@/components/Workspace";
import { TicketModal } from "@/components/TicketModal";
import { ResizableSplit } from "@/components/ui/resizable-split";
import { useWorkspace } from "@/context/WorkspaceContext";
import { useSSE } from "@/hooks/useSSE";
import type { SSEPayload } from "@/types";

export function AppLayout() {
  const { activeTicketId, openTicket } = useWorkspace();
  const [lastEvent, setLastEvent] = useState<SSEPayload | null>(null);

  useSSE((payload) => {
    setLastEvent(payload);
  });

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <ResizableSplit
        direction="horizontal"
        defaultSize={288}
        minSize={200}
        maxSize={520}
        storageKey="taskable.sidebar.width"
        first={<Sidebar lastEvent={lastEvent} />}
        second={<Workspace lastEvent={lastEvent} />}
      />
      <TicketModal
        ticketId={activeTicketId}
        onClose={() => openTicket(null)}
        lastEvent={lastEvent}
      />
    </div>
  );
}
