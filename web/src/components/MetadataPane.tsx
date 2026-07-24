import { useEffect, useState } from "react";
import { GitPullRequest, Link as LinkIcon, Link2, Save, CheckCircle2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  ASSIGNEE_LABELS,
  BLOCKED_BY_LABELS,
  TICKET_STATUSES,
  TICKET_STATUS_LABELS,
} from "@/types";
import type { BlockedByCategory, TicketAssignee, TicketDetail, TicketStatus } from "@/types";
import { linkTicketMR, listProjectTickets, updateTicket } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAsync } from "@/hooks/useAsync";

const BLOCKED_BY_OPTIONS: BlockedByCategory[] = [
  "WAITING_HUMAN",
  "WAITING_DEPENDENCY",
  "AMBIGUOUS_REQUIREMENT",
  "EXTERNAL",
];

interface Props {
  ticket: TicketDetail;
  onChanged: () => void;
}

const ASSIGNEES: TicketAssignee[] = ["UNASSIGNED", "HUMAN", "AGENT"];

const statusDotColor: Record<string, string> = {
  TODO: "bg-muted-foreground/40",
  IN_PROGRESS: "bg-blue-500",
  BLOCKED: "bg-red-500",
  REVIEW: "bg-yellow-500",
  DONE: "bg-green-500",
};

export function MetadataPane({ ticket, onChanged }: Props) {
  const [mrUrl, setMrUrl] = useState(ticket.mr_link ?? "");
  const [savingMR, setSavingMR] = useState(false);
  const [blockedReason, setBlockedReason] = useState(ticket.blocked_reason ?? "");
  const [dependencyIds, setDependencyIds] = useState<number[]>(ticket.depends_on ?? []);
  const [savingDependencies, setSavingDependencies] = useState(false);
  const projectTickets = useAsync(
    () => ticket.project_id ? listProjectTickets(ticket.project_id) : Promise.resolve([]),
    [ticket.project_id],
  );

  useEffect(() => {
    setBlockedReason(ticket.blocked_reason ?? "");
    setDependencyIds(ticket.depends_on ?? []);
  }, [ticket.id, ticket.blocked_reason, ticket.depends_on]);

  async function setStatus(status: TicketStatus) {
    const patch: Parameters<typeof updateTicket>[1] = { status };
    if (status === "BLOCKED" && !ticket.blocked_by) {
      patch.blocked_by = "WAITING_DEPENDENCY";
    }
    await updateTicket(ticket.id, patch);
    onChanged();
  }

  async function setBlockedBy(blocked_by: BlockedByCategory) {
    await updateTicket(ticket.id, {
      blocked_by,
      ...(ticket.status === "BLOCKED" ? {} : { status: "BLOCKED" }),
    });
    onChanged();
  }

  async function saveDependencies() {
    setSavingDependencies(true);
    try {
      await updateTicket(ticket.id, { depends_on: dependencyIds });
      onChanged();
    } finally {
      setSavingDependencies(false);
    }
  }

  function toggleDependency(id: number) {
    setDependencyIds((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );
  }

  async function saveBlockedReason() {
    if (blockedReason === (ticket.blocked_reason ?? "")) return;
    await updateTicket(ticket.id, { blocked_reason: blockedReason || null });
    onChanged();
  }

  async function setAssignee(assignee: TicketAssignee) {
    await updateTicket(ticket.id, { assignee });
    onChanged();
  }

  async function saveMR(e: React.FormEvent) {
    e.preventDefault();
    if (!mrUrl.trim()) return;
    setSavingMR(true);
    try {
      await linkTicketMR(ticket.id, mrUrl.trim());
      onChanged();
    } finally {
      setSavingMR(false);
    }
  }

  return (
    <div className="space-y-4 text-sm">
      <div>
        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Status
        </label>
        <Select
          value={ticket.status}
          onValueChange={(v) => void setStatus(v as TicketStatus)}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TICKET_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {TICKET_STATUS_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Blocked by
        </label>
        <Select
          value={ticket.status === "BLOCKED" ? (ticket.blocked_by ?? "") : ""}
          onValueChange={(v) => void setBlockedBy(v as BlockedByCategory)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Mark as blocked…" />
          </SelectTrigger>
          <SelectContent>
            {BLOCKED_BY_OPTIONS.map((opt) => (
              <SelectItem key={opt} value={opt}>
                {BLOCKED_BY_LABELS[opt]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {ticket.status === "BLOCKED" && (
          <Input
            value={blockedReason}
            onChange={(e) => setBlockedReason(e.target.value)}
            onBlur={() => void saveBlockedReason()}
            placeholder="Optional reason…"
            className="mt-1.5 h-8 text-xs"
          />
        )}
      </div>

      <div>
        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Assignee
        </label>
        <Select
          value={ticket.assignee}
          onValueChange={(v) => void setAssignee(v as TicketAssignee)}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ASSIGNEES.map((a) => (
              <SelectItem key={a} value={a}>
                {ASSIGNEE_LABELS[a]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <label className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          <GitPullRequest className="h-3 w-3" />
          Merge Request
        </label>
        <form onSubmit={saveMR} className="flex items-center gap-2">
          <Input
            value={mrUrl}
            onChange={(e) => setMrUrl(e.target.value)}
            placeholder="https://github.com/org/repo/pull/123"
            className="h-8 text-xs"
          />
          <Button
            type="submit"
            size="icon"
            variant="outline"
            className="h-8 w-8"
            disabled={savingMR}
            aria-label="Attach MR"
          >
            <Save className="h-3.5 w-3.5" />
          </Button>
        </form>
        {ticket.mr_link && (
          <a
            href={ticket.mr_link}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 flex items-center gap-1 text-[11px] text-primary underline-offset-2 hover:underline"
          >
            <LinkIcon className="h-3 w-3" />
            Current link
          </a>
        )}
      </div>

      <div>
        <label className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          <Link2 className="h-3 w-3" />
          Dependencies ({dependencyIds.length})
        </label>
        <div className="max-h-44 space-y-1 overflow-y-auto rounded-md border border-border p-1.5">
          {projectTickets.loading && (
            <p className="px-2 py-1 text-xs text-muted-foreground">Loading tickets…</p>
          )}
          {projectTickets.data?.filter((ref) => ref.id !== ticket.id).map((ref) => (
            <label key={ref.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-accent">
              <input type="checkbox" checked={dependencyIds.includes(ref.id)} onChange={() => toggleDependency(ref.id)} />
              {ref.status === "DONE" ? (
                <CheckCircle2 className="h-3 w-3 shrink-0 text-green-600" />
              ) : (
                <span className={cn("h-2 w-2 shrink-0 rounded-full", statusDotColor[ref.status] ?? "bg-muted-foreground/40")} />
              )}
              <span className="font-mono text-muted-foreground">#{ref.id}</span>
              <span className="min-w-0 flex-1 truncate">{ref.title}</span>
              {ref.subproject_name && <span className="shrink-0 text-muted-foreground/70">{ref.subproject_name}</span>}
            </label>
          ))}
          {projectTickets.data?.filter((ref) => ref.id !== ticket.id).length === 0 && !projectTickets.loading && (
            <p className="px-2 py-1 text-xs text-muted-foreground">No other tickets in this project.</p>
          )}
        </div>
        <Button
          className="mt-2 w-full"
          size="sm"
          variant="outline"
          onClick={() => void saveDependencies()}
          disabled={savingDependencies || (dependencyIds.length === ticket.depends_on.length && dependencyIds.every((id) => ticket.depends_on.includes(id)))}
        >
          <Save className="mr-1 h-3.5 w-3.5" />
          {savingDependencies ? "Saving…" : "Save dependencies"}
        </Button>
      </div>

      {ticket.source_refs && ticket.source_refs.length > 0 && (
        <div>
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Source Refs
          </label>
          <ul className="space-y-1">
            {ticket.source_refs.map((ref, i) => (
              <li key={i} className="truncate text-[11px] text-muted-foreground">
                {ref.startsWith("node:") ? (
                  <span className="font-mono">{ref}</span>
                ) : (
                  <span className="font-mono">{ref}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {ticket.audit_logs.length > 0 && (
        <div>
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Audit Ledger
          </label>
          <ul className="space-y-1 text-[11px] text-muted-foreground">
            {ticket.audit_logs
              .slice()
              .reverse()
              .slice(0, 8)
              .map((log) => (
                <li key={log.id} className="flex justify-between gap-2">
                  <span className="truncate">
                    <strong className="text-foreground/80">{log.actor}</strong>{" "}
                    {log.action.replace("_", " ").toLowerCase()}
                  </span>
                  <span className="shrink-0">
                    {new Date(log.timestamp + "Z").toLocaleTimeString()}
                  </span>
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
