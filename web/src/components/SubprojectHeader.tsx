import { useState } from "react";
import { Pencil, Save, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useWorkspace } from "@/context/WorkspaceContext";
import { deleteSubproject, updateSubproject } from "@/lib/api";
import type { Subproject, SubprojectStatus } from "@/types";

const STATUSES: SubprojectStatus[] = ["PLANNING", "ACTIVE", "COMPLETED"];

interface Props {
  subproject: Subproject;
  onSaved: () => void;
  onDeleted?: () => void;
}

export function SubprojectHeader({ subproject, onSaved, onDeleted }: Props) {
  const { setActiveSubprojectId } = useWorkspace();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(subproject.name);
  const [brief, setBrief] = useState(subproject.context_brief);
  const [status, setStatus] = useState<SubprojectStatus>(subproject.status);
  const [saving, setSaving] = useState(false);

  function reset() {
    setName(subproject.name);
    setBrief(subproject.context_brief);
    setStatus(subproject.status);
  }

  async function save() {
    setSaving(true);
    try {
      await updateSubproject(subproject.id, {
        name: name.trim() || subproject.name,
        context_brief: brief,
        status,
      });
      setEditing(false);
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (
      !window.confirm(
        `Delete subproject "${subproject.name}" and all its tickets?`,
      )
    ) {
      return;
    }
    setActiveSubprojectId(null);
    try {
      await deleteSubproject(subproject.id);
      onDeleted?.();
    } catch {
      onSaved();
    }
  }

  return (
    <div className="h-full overflow-auto border-b border-border bg-card/40 px-6 py-4">
      {!editing ? (
        <div className="flex items-start justify-between gap-6">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <h2 className="truncate text-xl font-semibold tracking-tight">
                {subproject.name}
              </h2>
              <Badge variant="outline" className="uppercase tracking-wide">
                {subproject.status}
              </Badge>
            </div>
            <p className="mt-1 max-w-3xl whitespace-pre-wrap text-sm text-muted-foreground">
              {subproject.context_brief.trim() ||
                "No context brief. The agent will have nothing to work from until this is filled in."}
            </p>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => {
                reset();
                setEditing(true);
              }}
              aria-label="Edit subproject"
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={remove}
              aria-label="Delete subproject"
              className="text-destructive-foreground/80 hover:bg-destructive/20"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 max-w-md text-base font-semibold"
            />
            <Select
              value={status}
              onValueChange={(v) => setStatus(v as SubprojectStatus)}
            >
              <SelectTrigger className="h-9 w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={3}
            placeholder="Context brief used by the MCP agent for orientation."
          />
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                reset();
                setEditing(false);
              }}
            >
              <X className="mr-1 h-3.5 w-3.5" />
              Cancel
            </Button>
            <Button size="sm" onClick={save} disabled={saving}>
              <Save className="mr-1 h-3.5 w-3.5" />
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
