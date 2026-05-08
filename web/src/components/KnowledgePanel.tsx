import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  ExternalLink,
  Flag,
  Loader2,
  Map as MapIcon,
  MessageSquare,
  Plus,
  Save,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ResizableSplit } from "@/components/ui/resizable-split";
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
  getContextTrail,
  listKnowledgeNodes,
  listProposalsForNode,
  reviewProposal,
  updateKnowledgeNode,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  ContextTrail,
  KnowledgeNode,
  KnowledgeNodeStatus,
  KnowledgeNodeType,
  KnowledgeProposal,
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
  const [trailQuery, setTrailQuery] = useState("");
  const [trail, setTrail] = useState<ContextTrail | null>(null);
  const [trailLoading, setTrailLoading] = useState(false);

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

  async function runContextTrail(nextQuery = trailQuery) {
    setTrailLoading(true);
    try {
      const result = await getContextTrail(projectId, nextQuery, 6);
      setTrail(result);
      setExpanded((prev) => {
        const next = new Set(prev);
        for (const segment of result.load_order) next.add(segment.id);
        return next;
      });
      if (result.items[0]) setSelectedId(result.items[0].id);
    } finally {
      setTrailLoading(false);
    }
  }

  async function saveContextCheckpoint() {
    if (!trail || trail.load_order.length === 0) return;
    const title =
      trail.query.trim().length > 0
        ? `Context checkpoint: ${trail.query.trim()}`
        : "Context checkpoint";
    const sourceRefs = trail.load_order.map((segment) => `node:${segment.id}`);
    const lines = [
      "# Context checkpoint",
      "",
      `Query: ${trail.query.trim() || "(empty)"}`,
      "",
      "## Loaded nodes",
      ...trail.load_order.map(
        (segment, index) =>
          `${index + 1}. [${segment.node_type}] #${segment.id} ${segment.title}`,
      ),
      "",
      "## Agent belief to verify",
      "Fill this in after the agent uses the trail, then keep or correct the branch.",
    ];
    const node = await createKnowledgeNode(projectId, {
      title,
      node_type: "SUMMARY",
      content: lines.join("\n"),
      parent_id: trail.items[0]?.id ?? null,
      source_refs: sourceRefs,
    });
    setSelectedId(node.id);
    nodes.refetch();
  }

  const tree = (
    <aside className="flex h-full w-full flex-col border-r border-border bg-card/20">
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
  );

  const editor = (
    <section className="flex h-full w-full flex-1 flex-col overflow-hidden">
      <ContextTrailPanel
        query={trailQuery}
        trail={trail}
        loading={trailLoading}
        onQueryChange={setTrailQuery}
        onRun={runContextTrail}
        onSelectNode={setSelectedId}
        onSaveCheckpoint={saveContextCheckpoint}
      />
      {selectedNode ? (
        <NodeEditor
          key={selectedNode.id}
          node={selectedNode}
          allNodes={nodes.data ?? []}
          onSaved={() => nodes.refetch()}
          onSelectNode={setSelectedId}
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
  );

  return (
    <ResizableSplit
      direction="horizontal"
      defaultSize={320}
      minSize={240}
      maxSize={640}
      storageKey="taskable.knowledge.treeWidth"
      first={tree}
      second={editor}
    />
  );
}

interface ContextTrailPanelProps {
  query: string;
  trail: ContextTrail | null;
  loading: boolean;
  onQueryChange: (query: string) => void;
  onRun: (query?: string) => void;
  onSelectNode: (id: number) => void;
  onSaveCheckpoint: () => void;
}

function ContextTrailPanel({
  query,
  trail,
  loading,
  onQueryChange,
  onRun,
  onSelectNode,
  onSaveCheckpoint,
}: ContextTrailPanelProps) {
  const hasTrail = trail !== null;
  return (
    <section className="border-b border-border bg-card/20 px-4 py-3">
      <form
        className="flex items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          onRun();
        }}
      >
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <MapIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Find context trail, e.g. battle component"
            className="h-8 text-xs"
          />
        </div>
        <Button type="submit" size="sm" disabled={loading}>
          <Search className="mr-1 h-3.5 w-3.5" />
          {loading ? "Finding…" : "Find trail"}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!trail || trail.load_order.length === 0}
          onClick={onSaveCheckpoint}
        >
          <Flag className="mr-1 h-3.5 w-3.5" />
          Checkpoint
        </Button>
      </form>

      {hasTrail && (
        <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
          <div className="min-w-0">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Load order
            </div>
            {trail.load_order.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No matching nodes. Add clearer signpost text to the tree or try
                another query.
              </p>
            ) : (
              <div className="flex flex-wrap gap-1">
                {trail.load_order.map((segment, index) => (
                  <button
                    key={segment.id}
                    type="button"
                    onClick={() => onSelectNode(segment.id)}
                    className="inline-flex max-w-[240px] items-center gap-1 rounded-md border border-border bg-background/60 px-2 py-1 text-[11px] hover:border-primary/50 hover:bg-accent/60"
                    title={segment.title}
                  >
                    <span className="text-muted-foreground">{index + 1}</span>
                    <TypeBadge type={segment.node_type} />
                    <span className="truncate">{segment.title}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="min-w-0">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Matched branches
            </div>
            <div className="flex max-h-36 flex-col gap-1 overflow-auto pr-1">
              {trail.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelectNode(item.id)}
                  className="rounded-md border border-border/60 bg-background/50 px-2 py-1.5 text-left text-xs hover:border-primary/50 hover:bg-accent/50"
                >
                  <div className="flex min-w-0 items-center gap-1.5">
                    <TypeBadge type={item.node_type} />
                    <span className="truncate font-medium">{item.title}</span>
                    <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                      score {item.score}
                    </span>
                  </div>
                  <div className="mt-1 truncate text-[11px] text-muted-foreground">
                    {item.path.map((part) => part.title).join(" > ")}
                  </div>
                  {item.children.length > 0 && (
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      {item.children.length} child hint
                      {item.children.length === 1 ? "" : "s"} available
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
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
                {node.status === "STALE" && (
                  <span className="shrink-0 rounded bg-yellow-500/20 px-1 text-[9px] font-semibold uppercase text-yellow-300">STALE</span>
                )}
                {node.status === "ARCHIVED" && (
                  <span className="shrink-0 rounded bg-gray-500/20 px-1 text-[9px] font-semibold uppercase text-gray-400">ARCH</span>
                )}
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
  allNodes: KnowledgeNode[];
  onSaved: () => void;
  onDeleted: () => void;
  onSelectNode: (id: number) => void;
}

function NodeEditor({
  node,
  allNodes,
  onSaved,
  onDeleted,
  onSelectNode,
}: NodeEditorProps) {
  const [title, setTitle] = useState(node.title);
  const [type, setType] = useState<KnowledgeNodeType>(node.node_type);
  const [content, setContent] = useState(node.content);
  const [sourceRefsText, setSourceRefsText] = useState(
    node.source_refs.join("\n"),
  );
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [correctionText, setCorrectionText] = useState("");
  const [correctionSaving, setCorrectionSaving] = useState(false);

  // Build an id → KnowledgeNode lookup so ``node:N`` source refs can render
  // a live, clickable chip showing the current title of the referenced
  // node. Re-derives on every render so SSE-driven title edits elsewhere
  // propagate immediately.
  const nodeById = useMemo(() => {
    const map = new Map<number, KnowledgeNode>();
    for (const n of allNodes) map.set(n.id, n);
    return map;
  }, [allNodes]);

  const resolvedRefs = useMemo(
    () =>
      sourceRefsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const match = line.match(/^node:(\d+)$/i);
          if (!match) return { kind: "text" as const, value: line };
          const id = Number(match[1]);
          const target = nodeById.get(id);
          return {
            kind: "node" as const,
            value: line,
            id,
            target: target ?? null,
          };
        }),
    [sourceRefsText, nodeById],
  );

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

  async function requestCorrection() {
    const correction = correctionText.trim();
    if (!correction) return;
    setCorrectionSaving(true);
    try {
      const created = await createKnowledgeNode(node.project_id, {
        title: `Correction request: ${node.title}`,
        node_type: "SUMMARY",
        parent_id: node.id,
        source_refs: [`node:${node.id}`],
        content: [
          "# Human correction request",
          "",
          correction,
          "",
          "## Target node",
          `node:${node.id}`,
          "",
          "Agent: resolve this by updating the target node or adding a corrected child summary.",
        ].join("\n"),
      });
      setCorrectionText("");
      onSaved();
      onSelectNode(created.id);
    } finally {
      setCorrectionSaving(false);
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
            <span>·</span>
            <Select
              value={node.status ?? "CURRENT"}
              onValueChange={(v) =>
                void updateKnowledgeNode(node.id, { status: v as KnowledgeNodeStatus }).then(onSaved)
              }
            >
              <SelectTrigger className="h-5 w-24 border-0 bg-transparent px-1 text-[10px] shadow-none">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="CURRENT">Current</SelectItem>
                <SelectItem value="STALE">Stale</SelectItem>
                <SelectItem value="ARCHIVED">Archived</SelectItem>
              </SelectContent>
            </Select>
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
        <ProposalsSection nodeId={node.id} onAccepted={onSaved} />
        <section className="rounded-md border border-border bg-muted/20 p-3">
          <div className="mb-2 flex items-center gap-2">
            <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" />
            <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Correction request
            </label>
          </div>
          <div className="flex gap-2">
            <Textarea
              value={correctionText}
              onChange={(e) => setCorrectionText(e.target.value)}
              rows={2}
              placeholder="Tell the agent what looks stale, wrong, or missing for this context node."
              className="min-h-16 text-xs"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="self-start"
              onClick={requestCorrection}
              disabled={!correctionText.trim() || correctionSaving}
            >
              {correctionSaving ? "Saving…" : "Request update"}
            </Button>
          </div>
        </section>
        <section>
          <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Source references
          </label>
          {resolvedRefs.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-1">
              {resolvedRefs.map((ref, idx) =>
                ref.kind === "node" ? (
                  <button
                    key={`${ref.value}-${idx}`}
                    type="button"
                    onClick={() => ref.target && onSelectNode(ref.target.id)}
                    disabled={!ref.target}
                    title={
                      ref.target
                        ? `Open node #${ref.id}: ${ref.target.title}`
                        : `Node #${ref.id} no longer exists in this project`
                    }
                    className={cn(
                      "group inline-flex max-w-[260px] items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] transition-colors",
                      ref.target
                        ? "cursor-pointer border-border bg-card hover:border-primary/50 hover:bg-accent/60"
                        : "cursor-not-allowed border-destructive/30 bg-destructive/10 text-destructive-foreground/80",
                    )}
                  >
                    {ref.target ? (
                      <TypeBadge type={ref.target.node_type} />
                    ) : (
                      <span className="rounded bg-destructive/20 px-1 text-[9px] font-semibold uppercase">
                        GONE
                      </span>
                    )}
                    <span className="truncate">
                      #{ref.id}{" "}
                      {ref.target?.title ?? "Missing node"}
                    </span>
                    {ref.target && (
                      <ExternalLink className="h-2.5 w-2.5 shrink-0 text-muted-foreground group-hover:text-foreground" />
                    )}
                  </button>
                ) : (
                  <span
                    key={`${ref.value}-${idx}`}
                    className="inline-flex max-w-[260px] items-center gap-1 rounded-md border border-border/40 bg-muted/30 px-2 py-0.5 font-mono text-[11px] text-muted-foreground"
                    title={ref.value}
                  >
                    <span className="truncate">{ref.value}</span>
                  </span>
                ),
              )}
            </div>
          )}
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
            back to the raw material. <span className="font-mono">node:N</span>{" "}
            entries resolve to clickable chips above.
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

// ---- ProposalsSection ----------------------------------------------------

function ProposalsSection({
  nodeId,
  onAccepted,
}: {
  nodeId: number;
  onAccepted: () => void;
}) {
  const [proposals, setProposals] = useState<KnowledgeProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    try {
      const all = await listProposalsForNode(nodeId);
      setProposals(all.filter((p) => p.status === "PENDING"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [nodeId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleReview(id: number, action: "accept" | "reject") {
    setReviewing(id);
    try {
      await reviewProposal(id, action);
      if (action === "accept") onAccepted();
      await load();
    } finally {
      setReviewing(null);
    }
  }

  if (!loading && proposals.length === 0) return null;

  return (
    <section className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3">
      <div className="mb-2 flex items-center gap-2">
        <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
        <label className="text-[11px] font-semibold uppercase tracking-wider text-amber-400">
          Pending proposals
        </label>
        {loading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
      </div>
      {proposals.map((p) => (
        <div key={p.id} className="mb-2 rounded border border-border/50 bg-card/60 p-2 text-xs">
          <div className="mb-1 flex items-start justify-between gap-2">
            <span className="text-[10px] text-muted-foreground">
              <Clock className="mr-0.5 inline h-2.5 w-2.5" />
              {new Date(p.created_at + "Z").toLocaleString()}
            </span>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="outline"
                className="h-6 px-2 text-[10px] text-destructive-foreground/80 hover:bg-destructive/20"
                disabled={reviewing === p.id}
                onClick={() => void handleReview(p.id, "reject")}
              >
                <X className="mr-1 h-3 w-3" />
                Reject
              </Button>
              <Button
                size="sm"
                className="h-6 px-2 text-[10px]"
                disabled={reviewing === p.id}
                onClick={() => void handleReview(p.id, "accept")}
              >
                <Check className="mr-1 h-3 w-3" />
                Accept
              </Button>
            </div>
          </div>
          {p.rationale && (
            <p className="mb-1 text-muted-foreground">{p.rationale}</p>
          )}
          <details className="text-[10px]">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              View proposed changes
            </summary>
            <pre className="mt-1 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-muted-foreground">
              {JSON.stringify(p.proposed_changes, null, 2)}
            </pre>
          </details>
        </div>
      ))}
    </section>
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
