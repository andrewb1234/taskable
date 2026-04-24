import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAsync } from "@/hooks/useAsync";
import {
  createKnowledgeNode,
  deleteKnowledgeNode,
  listKnowledgeNodes,
  updateKnowledgeNode,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  KnowledgeNode,
  KnowledgeNodeType,
  SSEPayload,
} from "@/types";
import {
  KNOWLEDGE_NODE_TYPE_LABELS,
  KNOWLEDGE_NODE_TYPES,
} from "@/types";

interface Props {
  projectId: number;
  lastEvent: SSEPayload | null;
}

/**
 * Renders the per-project knowledge tree: a collapsible left column of
 * nodes plus a right-hand editor for the selection. Listens to SSE events
 * so agent-side mutations reconcile live. Styled with a type-coded left
 * border (navy / mustard / emerald / sky) to keep the four node types
 * scannable without fighting the existing palette.
 */
export function KnowledgePanel({ projectId, lastEvent }: Props) {
  const nodes = useAsync<KnowledgeNode[]>(
    () => listKnowledgeNodes(projectId),
    [projectId],
  );
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [creatingUnder, setCreatingUnder] = useState<number | null | "root">(
    null,
  );

  // SSE-driven refetch: any knowledge mutation for this project refreshes
  // the whole panel. The endpoint is cheap (single SELECT) so we don't
  // bother with targeted updates.
  useEffect(() => {
    if (!lastEvent) return;
    if (
      lastEvent.entity === "knowledge_node" &&
      lastEvent.parent_id === projectId
    ) {
      nodes.refetch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent, projectId]);

  // Auto-expand all nodes the first time data arrives so the human sees
  // the whole tree without clicking around.
  useEffect(() => {
    if (nodes.data && expanded.size === 0 && nodes.data.length > 0) {
      setExpanded(new Set(nodes.data.map((n) => n.id)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.data]);

  const selectedNode = useMemo(
    () => nodes.data?.find((n) => n.id === selectedId) ?? null,
    [nodes.data, selectedId],
  );

  const childrenByParent = useMemo(() => {
    const map = new Map<number | null, KnowledgeNode[]>();
    for (const node of nodes.data ?? []) {
      const bucket = map.get(node.parent_id) ?? [];
      bucket.push(node);
      map.set(node.parent_id, bucket);
    }
    for (const bucket of map.values()) {
      bucket.sort((a, b) => a.created_at.localeCompare(b.created_at));
    }
    return map;
  }, [nodes.data]);

  function toggleExpanded(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      <aside className="flex w-80 shrink-0 flex-col border-r border-border bg-card/20">
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h3 className="text-sm font-semibold tracking-tight">
              Knowledge Tree
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Raw → Summary → PRD / TDD
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            onClick={() => setCreatingUnder("root")}
          >
            <Plus className="mr-1 h-3 w-3" />
            Root node
          </Button>
        </header>
        <ScrollArea className="flex-1">
          <div className="px-2 py-2">
            {nodes.loading && !nodes.data && (
              <div className="flex items-center gap-2 px-2 py-4 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading…
              </div>
            )}
            {nodes.error && (
              <p className="px-2 py-2 text-xs text-destructive-foreground/80">
                {nodes.error.message}
              </p>
            )}
            {nodes.data && nodes.data.length === 0 && (
              <p className="px-2 py-4 text-xs text-muted-foreground">
                No knowledge nodes yet. Use the agent's{" "}
                <span className="font-mono">create_knowledge_node</span> tool
                or click <em>Root node</em> to start.
              </p>
            )}
            {creatingUnder === "root" && (
              <div className="mb-2">
                <NewNodeForm
                  projectId={projectId}
                  parentId={null}
                  onCancel={() => setCreatingUnder(null)}
                  onCreated={(node) => {
                    setCreatingUnder(null);
                    setSelectedId(node.id);
                    nodes.refetch();
                  }}
                />
              </div>
            )}
            <TreeBranch
              parentId={null}
              depth={0}
              childrenByParent={childrenByParent}
              selectedId={selectedId}
              expanded={expanded}
              creatingUnder={creatingUnder}
              onSelect={setSelectedId}
              onToggle={toggleExpanded}
              onStartCreate={(id) => {
                setCreatingUnder(id);
                setExpanded((prev) => new Set(prev).add(id));
              }}
              onCancelCreate={() => setCreatingUnder(null)}
              onCreated={(node) => {
                setCreatingUnder(null);
                setSelectedId(node.id);
                nodes.refetch();
              }}
              projectId={projectId}
            />
          </div>
        </ScrollArea>
      </aside>
      <section className="flex flex-1 flex-col overflow-hidden">
        {selectedNode ? (
          <NodeEditor
            key={selectedNode.id}
            node={selectedNode}
            onSaved={() => nodes.refetch()}
            onDeleted={() => {
              setSelectedId(null);
              nodes.refetch();
            }}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            Select a node on the left to review or edit.
          </div>
        )}
      </section>
    </div>
  );
}

interface TreeBranchProps {
  parentId: number | null;
  depth: number;
  childrenByParent: Map<number | null, KnowledgeNode[]>;
  selectedId: number | null;
  expanded: Set<number>;
  creatingUnder: number | null | "root";
  projectId: number;
  onSelect: (id: number) => void;
  onToggle: (id: number) => void;
  onStartCreate: (parentId: number) => void;
  onCancelCreate: () => void;
  onCreated: (node: KnowledgeNode) => void;
}

function TreeBranch(props: TreeBranchProps) {
  const siblings = props.childrenByParent.get(props.parentId) ?? [];
  return (
    <ul className="space-y-0.5">
      {siblings.map((node) => {
        const children = props.childrenByParent.get(node.id) ?? [];
        const hasChildren = children.length > 0;
        const isExpanded = props.expanded.has(node.id);
        const isSelected = props.selectedId === node.id;
        return (
          <li key={node.id}>
            <div
              className={cn(
                "group flex items-center gap-1 rounded-md border-l-2 pl-1.5 pr-1 py-1 text-xs transition-colors",
                TYPE_BORDER[node.node_type],
                isSelected
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-accent/40",
              )}
              style={{ marginLeft: `${props.depth * 10}px` }}
            >
              <button
                type="button"
                className="flex h-4 w-4 shrink-0 items-center justify-center rounded hover:bg-accent"
                onClick={() => hasChildren && props.onToggle(node.id)}
                aria-label={isExpanded ? "Collapse" : "Expand"}
                disabled={!hasChildren}
              >
                {hasChildren ? (
                  isExpanded ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )
                ) : (
                  <span className="h-1 w-1 rounded-full bg-muted-foreground/40" />
                )}
              </button>
              <button
                type="button"
                className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                onClick={() => props.onSelect(node.id)}
              >
                <TypeBadge type={node.node_type} />
                <span className="truncate font-medium">{node.title}</span>
              </button>
              <button
                type="button"
                className="h-5 w-5 shrink-0 rounded text-muted-foreground opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100"
                aria-label="Add child node"
                onClick={() => props.onStartCreate(node.id)}
              >
                <Plus className="mx-auto h-3 w-3" />
              </button>
            </div>
            {isExpanded && (
              <>
                {props.creatingUnder === node.id && (
                  <div style={{ marginLeft: `${(props.depth + 1) * 10 + 6}px` }}>
                    <NewNodeForm
                      projectId={props.projectId}
                      parentId={node.id}
                      onCancel={props.onCancelCreate}
                      onCreated={props.onCreated}
                    />
                  </div>
                )}
                {hasChildren && (
                  <TreeBranch {...props} parentId={node.id} depth={props.depth + 1} />
                )}
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}

interface NewNodeFormProps {
  projectId: number;
  parentId: number | null;
  onCancel: () => void;
  onCreated: (node: KnowledgeNode) => void;
}

function NewNodeForm({
  projectId,
  parentId,
  onCancel,
  onCreated,
}: NewNodeFormProps) {
  const [title, setTitle] = useState("");
  const [type, setType] = useState<KnowledgeNodeType>("RAW");
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    try {
      const node = await createKnowledgeNode(projectId, {
        title: title.trim(),
        node_type: type,
        content: "",
        parent_id: parentId,
      });
      onCreated(node);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="my-1 space-y-2 rounded-md border border-border bg-popover p-2 text-xs"
    >
      <Input
        autoFocus
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Node title"
        className="h-7 text-xs"
      />
      <Select
        value={type}
        onValueChange={(v) => setType(v as KnowledgeNodeType)}
      >
        <SelectTrigger className="h-7 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {KNOWLEDGE_NODE_TYPES.map((t) => (
            <SelectItem key={t} value={t}>
              {KNOWLEDGE_NODE_TYPE_LABELS[t]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <div className="flex justify-end gap-1">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? "…" : "Create"}
        </Button>
      </div>
    </form>
  );
}

interface NodeEditorProps {
  node: KnowledgeNode;
  onSaved: () => void;
  onDeleted: () => void;
}

function NodeEditor({ node, onSaved, onDeleted }: NodeEditorProps) {
  const [title, setTitle] = useState(node.title);
  const [type, setType] = useState<KnowledgeNodeType>(node.node_type);
  const [content, setContent] = useState(node.content);
  const [sourceRefsText, setSourceRefsText] = useState(
    node.source_refs.join("\n"),
  );
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const dirty =
    title !== node.title ||
    type !== node.node_type ||
    content !== node.content ||
    sourceRefsText !== node.source_refs.join("\n");

  async function save() {
    setSaving(true);
    try {
      await updateKnowledgeNode(node.id, {
        title: title.trim() || node.title,
        node_type: type,
        content,
        source_refs: sourceRefsText
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${node.title}" and all its children?`)) return;
    setDeleting(true);
    try {
      await deleteKnowledgeNode(node.id);
      onDeleted();
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <header className="flex items-start justify-between gap-3 border-b border-border bg-card/30 px-6 py-3">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <TypeBadge type={type} />
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="h-8 flex-1 text-sm font-semibold"
            />
            <Select
              value={type}
              onValueChange={(v) => setType(v as KnowledgeNodeType)}
            >
              <SelectTrigger className="h-8 w-28 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {KNOWLEDGE_NODE_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {KNOWLEDGE_NODE_TYPE_LABELS[t]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span className="uppercase tracking-wide">#{node.id}</span>
            <span>·</span>
            <Badge
              variant={node.created_by === "AGENT" ? "agent" : "human"}
              className="py-0 text-[10px]"
            >
              {node.created_by === "AGENT" ? (
                <Sparkles className="mr-1 h-2.5 w-2.5" />
              ) : null}
              {node.created_by}
            </Badge>
            <span>·</span>
            <span>updated {formatWhen(node.updated_at)}</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={remove}
            disabled={deleting}
            className="text-destructive-foreground/80"
          >
            <Trash2 className="mr-1 h-3.5 w-3.5" />
            Delete
          </Button>
          <Button size="sm" onClick={save} disabled={!dirty || saving}>
            <Save className="mr-1 h-3.5 w-3.5" />
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </header>
      <div className="flex flex-1 flex-col gap-3 overflow-auto px-6 py-4">
        <section>
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Source references
          </label>
          <Textarea
            value={sourceRefsText}
            onChange={(e) => setSourceRefsText(e.target.value)}
            rows={3}
            placeholder={
              "/absolute/path/file.py\nhttps://example.com/doc\nnode:42"
            }
            className="font-mono text-xs"
          />
          <p className="mt-1 text-[10px] text-muted-foreground">
            One pointer per line. These are the breadcrumbs a reviewer follows
            back to the raw material.
          </p>
        </section>
        <section className="flex flex-1 flex-col">
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Content
          </label>
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="min-h-[300px] flex-1 font-mono text-xs"
            placeholder={CONTENT_PLACEHOLDERS[type]}
          />
        </section>
      </div>
      {dirty && (
        <footer className="flex items-center justify-end gap-2 border-t border-border bg-muted/20 px-6 py-2 text-xs">
          <span className="text-muted-foreground">Unsaved changes</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setTitle(node.title);
              setType(node.node_type);
              setContent(node.content);
              setSourceRefsText(node.source_refs.join("\n"));
            }}
          >
            <X className="mr-1 h-3.5 w-3.5" />
            Revert
          </Button>
          <Button size="sm" onClick={save} disabled={saving}>
            <Save className="mr-1 h-3.5 w-3.5" />
            {saving ? "Saving…" : "Save"}
          </Button>
        </footer>
      )}
    </div>
  );
}

// ---- visuals --------------------------------------------------------------

const TYPE_BORDER: Record<KnowledgeNodeType, string> = {
  // Bauhaus-flavored type indicators: heavy 2px left borders, no rounding
  // on the border itself, sized to remain legible against the existing
  // shadcn palette.
  RAW: "border-slate-500",
  SUMMARY: "border-amber-500",
  PRD: "border-sky-500",
  TDD: "border-emerald-500",
};

const TYPE_BADGE: Record<KnowledgeNodeType, string> = {
  RAW: "bg-slate-600/30 text-slate-100",
  SUMMARY: "bg-amber-500/30 text-amber-100",
  PRD: "bg-sky-500/30 text-sky-100",
  TDD: "bg-emerald-500/30 text-emerald-100",
};

function TypeBadge({ type }: { type: KnowledgeNodeType }) {
  return (
    <span
      className={cn(
        "inline-flex h-4 items-center justify-center rounded px-1 text-[9px] font-semibold uppercase tracking-wider",
        TYPE_BADGE[type],
      )}
    >
      {type}
    </span>
  );
}

const CONTENT_PLACEHOLDERS: Record<KnowledgeNodeType, string> = {
  RAW: "Paste the raw file excerpt, documentation, or research content here.",
  SUMMARY:
    "Write a compressed summary of this branch of the tree. Reference the children by their #id so a reviewer can drill down.",
  PRD: "# Product Requirements Document\n\n## Goal\n\n## User stories\n\n## Acceptance criteria",
  TDD: "# Technical Design Document\n\n## Architecture\n\n## Data model\n\n## Open questions",
};

function formatWhen(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
