import { useEffect, useState } from "react";
import { FolderPlus, Plus, Folder, FileText, Loader2 } from "lucide-react";
import {
  createProject,
  createSubproject,
  listProjects,
  listSubprojects,
} from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { useAsync } from "@/hooks/useAsync";
import type { Project, SSEPayload, Subproject } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

interface SidebarProps {
  lastEvent: SSEPayload | null;
}

export function Sidebar({ lastEvent }: SidebarProps) {
  const {
    activeProjectId,
    activeSubprojectId,
    setActiveProjectId,
    setActiveSubprojectId,
  } = useWorkspace();

  const projects = useAsync<Project[]>(() => listProjects(), []);

  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.action === "PROJECT_CREATED") projects.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent]);

  // Default-select the first project once data arrives.
  useEffect(() => {
    if (
      activeProjectId == null &&
      projects.data &&
      projects.data.length > 0
    ) {
      setActiveProjectId(projects.data[0].id);
    }
  }, [activeProjectId, projects.data, setActiveProjectId]);

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-card/30">
      <header className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-sm font-semibold tracking-tight">Taskable</h1>
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Co-Pilot
          </span>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Human + Agent workspace
        </p>
      </header>

      <ScrollArea className="flex-1">
        <div className="space-y-4 px-3 py-4">
          <section>
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Projects
              </span>
              <NewProjectButton onCreated={projects.refetch} />
            </div>
            {projects.loading && (
              <div className="flex items-center gap-2 px-2 py-2 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading…
              </div>
            )}
            {projects.error && (
              <p className="px-2 py-2 text-xs text-destructive-foreground/80">
                {projects.error.message}
              </p>
            )}
            {projects.data?.length === 0 && !projects.loading && (
              <p className="px-2 py-2 text-xs text-muted-foreground">
                No projects yet. Create one to begin.
              </p>
            )}
            <ul className="space-y-1">
              {projects.data?.map((project) => (
                <li key={project.id}>
                  <button
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                      activeProjectId === project.id
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-accent/50",
                    )}
                    onClick={() => setActiveProjectId(project.id)}
                  >
                    <Folder className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{project.name}</span>
                  </button>
                  {activeProjectId === project.id && (
                    <SubprojectList
                      projectId={project.id}
                      lastEvent={lastEvent}
                      activeSubprojectId={activeSubprojectId}
                      onSelect={setActiveSubprojectId}
                    />
                  )}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </ScrollArea>
    </aside>
  );
}

function SubprojectList({
  projectId,
  lastEvent,
  activeSubprojectId,
  onSelect,
}: {
  projectId: number;
  lastEvent: SSEPayload | null;
  activeSubprojectId: number | null;
  onSelect: (id: number | null) => void;
}) {
  const subprojects = useAsync<Subproject[]>(
    () => listSubprojects(projectId),
    [projectId],
  );

  useEffect(() => {
    if (!lastEvent) return;
    if (
      lastEvent.action === "SUBPROJECT_CREATED" ||
      lastEvent.action === "SUBPROJECT_UPDATED"
    ) {
      subprojects.refetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent]);

  useEffect(() => {
    if (
      activeSubprojectId == null &&
      subprojects.data &&
      subprojects.data.length > 0
    ) {
      onSelect(subprojects.data[0].id);
    }
  }, [activeSubprojectId, subprojects.data, onSelect]);

  return (
    <div className="ml-6 mt-1 border-l border-border pl-3">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Subprojects
        </span>
        <NewSubprojectButton
          projectId={projectId}
          onCreated={subprojects.refetch}
        />
      </div>
      <ul className="space-y-0.5">
        {subprojects.data?.map((sub) => (
          <li key={sub.id}>
            <button
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors",
                activeSubprojectId === sub.id
                  ? "bg-primary/10 text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent/40",
              )}
              onClick={() => onSelect(sub.id)}
            >
              <FileText className="h-3 w-3 shrink-0" />
              <span className="truncate">{sub.name}</span>
              <span className="ml-auto rounded bg-muted px-1 text-[9px] uppercase text-muted-foreground">
                {sub.status.slice(0, 4)}
              </span>
            </button>
          </li>
        ))}
        {subprojects.data?.length === 0 && (
          <li className="px-2 py-1 text-[11px] text-muted-foreground">
            None yet.
          </li>
        )}
      </ul>
    </div>
  );
}

function NewProjectButton({ onCreated }: { onCreated: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await createProject({
        name: name.trim(),
        description: desc.trim() || undefined,
      });
      setName("");
      setDesc("");
      setExpanded(false);
      onCreated();
    } finally {
      setSaving(false);
    }
  }

  if (!expanded) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6"
        onClick={() => setExpanded(true)}
        aria-label="New project"
      >
        <FolderPlus className="h-3.5 w-3.5" />
      </Button>
    );
  }

  return (
    <form
      onSubmit={submit}
      className="absolute inset-x-3 top-12 z-20 space-y-2 rounded-md border border-border bg-popover p-3 text-xs shadow-lg"
    >
      <Input
        autoFocus
        placeholder="Project name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="h-8 text-xs"
      />
      <Textarea
        placeholder="Description (optional)"
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
        className="min-h-[60px] text-xs"
      />
      <div className="flex justify-end gap-1">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(false)}
        >
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? "…" : "Create"}
        </Button>
      </div>
    </form>
  );
}

function NewSubprojectButton({
  projectId,
  onCreated,
}: {
  projectId: number;
  onCreated: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [name, setName] = useState("");
  const [brief, setBrief] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await createSubproject(projectId, {
        name: name.trim(),
        context_brief: brief.trim(),
      });
      setName("");
      setBrief("");
      setExpanded(false);
      onCreated();
    } finally {
      setSaving(false);
    }
  }

  if (!expanded) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className="h-5 w-5"
        onClick={() => setExpanded(true)}
        aria-label="New subproject"
      >
        <Plus className="h-3 w-3" />
      </Button>
    );
  }

  return (
    <form
      onSubmit={submit}
      className="ml-2 mt-1 space-y-2 rounded-md border border-border bg-popover p-2 text-xs"
    >
      <Input
        autoFocus
        placeholder="Subproject"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="h-7 text-xs"
      />
      <Textarea
        placeholder="Context brief for the agent"
        value={brief}
        onChange={(e) => setBrief(e.target.value)}
        className="min-h-[60px] text-xs"
      />
      <div className="flex justify-end gap-1">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(false)}
        >
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? "…" : "Add"}
        </Button>
      </div>
    </form>
  );
}
