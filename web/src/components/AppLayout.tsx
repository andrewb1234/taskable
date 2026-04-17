import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Workspace } from "@/components/Workspace";
import { TicketModal } from "@/components/TicketModal";
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
      <Sidebar lastEvent={lastEvent} />
      <Workspace lastEvent={lastEvent} />
      <TicketModal
        ticketId={activeTicketId}
        onClose={() => openTicket(null)}
        lastEvent={lastEvent}
      />
    </div>
  );
}
