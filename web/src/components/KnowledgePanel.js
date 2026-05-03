import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink, Flag, Loader2, Map as MapIcon, MessageSquare, Plus, Save, Search, Sparkles, Trash2, X, } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ResizableSplit } from "@/components/ui/resizable-split";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAsync } from "@/hooks/useAsync";
import { createKnowledgeNode, deleteKnowledgeNode, getContextTrail, listKnowledgeNodes, updateKnowledgeNode, } from "@/lib/api";
import { cn } from "@/lib/utils";
import { KNOWLEDGE_NODE_TYPE_LABELS, KNOWLEDGE_NODE_TYPES, } from "@/types";
/**
 * Renders the per-project knowledge tree: a collapsible left column of
 * nodes plus a right-hand editor for the selection. Listens to SSE events
 * so agent-side mutations reconcile live. Styled with a type-coded left
 * border (navy / mustard / emerald / sky) to keep the four node types
 * scannable without fighting the existing palette.
 */
export function KnowledgePanel({ projectId, lastEvent }) {
    const nodes = useAsync(() => listKnowledgeNodes(projectId), [projectId]);
    const [selectedId, setSelectedId] = useState(null);
    const [expanded, setExpanded] = useState(new Set());
    const [creatingUnder, setCreatingUnder] = useState(null);
    const [trailQuery, setTrailQuery] = useState("");
    const [trail, setTrail] = useState(null);
    const [trailLoading, setTrailLoading] = useState(false);
    // SSE-driven refetch: any knowledge mutation for this project refreshes
    // the whole panel. The endpoint is cheap (single SELECT) so we don't
    // bother with targeted updates.
    useEffect(() => {
        if (!lastEvent)
            return;
        if (lastEvent.entity === "knowledge_node" &&
            lastEvent.parent_id === projectId) {
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
    const selectedNode = useMemo(() => nodes.data?.find((n) => n.id === selectedId) ?? null, [nodes.data, selectedId]);
    const childrenByParent = useMemo(() => {
        const map = new Map();
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
    function toggleExpanded(id) {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(id))
                next.delete(id);
            else
                next.add(id);
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
                for (const segment of result.load_order)
                    next.add(segment.id);
                return next;
            });
            if (result.items[0])
                setSelectedId(result.items[0].id);
        }
        finally {
            setTrailLoading(false);
        }
    }
    async function saveContextCheckpoint() {
        if (!trail || trail.load_order.length === 0)
            return;
        const title = trail.query.trim().length > 0
            ? `Context checkpoint: ${trail.query.trim()}`
            : "Context checkpoint";
        const sourceRefs = trail.load_order.map((segment) => `node:${segment.id}`);
        const lines = [
            "# Context checkpoint",
            "",
            `Query: ${trail.query.trim() || "(empty)"}`,
            "",
            "## Loaded nodes",
            ...trail.load_order.map((segment, index) => `${index + 1}. [${segment.node_type}] #${segment.id} ${segment.title}`),
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
    const tree = (_jsxs("aside", { className: "flex h-full w-full flex-col border-r border-border bg-card/20", children: [_jsxs("header", { className: "flex items-center justify-between border-b border-border px-4 py-3", children: [_jsxs("div", { children: [_jsx("h3", { className: "text-sm font-semibold tracking-tight", children: "Knowledge Tree" }), _jsx("p", { className: "text-[11px] text-muted-foreground", children: "Raw \u2192 Summary \u2192 PRD / TDD" })] }), _jsxs(Button, { size: "sm", variant: "outline", className: "h-7 px-2 text-xs", onClick: () => setCreatingUnder("root"), children: [_jsx(Plus, { className: "mr-1 h-3 w-3" }), "Root node"] })] }), _jsx(ScrollArea, { className: "flex-1", children: _jsxs("div", { className: "px-2 py-2", children: [nodes.loading && !nodes.data && (_jsxs("div", { className: "flex items-center gap-2 px-2 py-4 text-xs text-muted-foreground", children: [_jsx(Loader2, { className: "h-3 w-3 animate-spin" }), "Loading\u2026"] })), nodes.error && (_jsx("p", { className: "px-2 py-2 text-xs text-destructive-foreground/80", children: nodes.error.message })), nodes.data && nodes.data.length === 0 && (_jsxs("p", { className: "px-2 py-4 text-xs text-muted-foreground", children: ["No knowledge nodes yet. Use the agent's", " ", _jsx("span", { className: "font-mono", children: "create_knowledge_node" }), " tool or click ", _jsx("em", { children: "Root node" }), " to start."] })), creatingUnder === "root" && (_jsx("div", { className: "mb-2", children: _jsx(NewNodeForm, { projectId: projectId, parentId: null, onCancel: () => setCreatingUnder(null), onCreated: (node) => {
                                    setCreatingUnder(null);
                                    setSelectedId(node.id);
                                    nodes.refetch();
                                } }) })), _jsx(TreeBranch, { parentId: null, depth: 0, childrenByParent: childrenByParent, selectedId: selectedId, expanded: expanded, creatingUnder: creatingUnder, onSelect: setSelectedId, onToggle: toggleExpanded, onStartCreate: (id) => {
                                setCreatingUnder(id);
                                setExpanded((prev) => new Set(prev).add(id));
                            }, onCancelCreate: () => setCreatingUnder(null), onCreated: (node) => {
                                setCreatingUnder(null);
                                setSelectedId(node.id);
                                nodes.refetch();
                            }, projectId: projectId })] }) })] }));
    const editor = (_jsxs("section", { className: "flex h-full w-full flex-1 flex-col overflow-hidden", children: [_jsx(ContextTrailPanel, { query: trailQuery, trail: trail, loading: trailLoading, onQueryChange: setTrailQuery, onRun: runContextTrail, onSelectNode: setSelectedId, onSaveCheckpoint: saveContextCheckpoint }), selectedNode ? (_jsx(NodeEditor, { node: selectedNode, allNodes: nodes.data ?? [], onSaved: () => nodes.refetch(), onSelectNode: setSelectedId, onDeleted: () => {
                    setSelectedId(null);
                    nodes.refetch();
                } }, selectedNode.id)) : (_jsx("div", { className: "flex flex-1 items-center justify-center text-sm text-muted-foreground", children: "Select a node on the left to review or edit." }))] }));
    return (_jsx(ResizableSplit, { direction: "horizontal", defaultSize: 320, minSize: 240, maxSize: 640, storageKey: "taskable.knowledge.treeWidth", first: tree, second: editor }));
}
function ContextTrailPanel({ query, trail, loading, onQueryChange, onRun, onSelectNode, onSaveCheckpoint, }) {
    const hasTrail = trail !== null;
    return (_jsxs("section", { className: "border-b border-border bg-card/20 px-4 py-3", children: [_jsxs("form", { className: "flex items-center gap-2", onSubmit: (event) => {
                    event.preventDefault();
                    onRun();
                }, children: [_jsxs("div", { className: "flex min-w-0 flex-1 items-center gap-2", children: [_jsx(MapIcon, { className: "h-4 w-4 shrink-0 text-muted-foreground" }), _jsx(Input, { value: query, onChange: (event) => onQueryChange(event.target.value), placeholder: "Find context trail, e.g. battle component", className: "h-8 text-xs" })] }), _jsxs(Button, { type: "submit", size: "sm", disabled: loading, children: [_jsx(Search, { className: "mr-1 h-3.5 w-3.5" }), loading ? "Finding…" : "Find trail"] }), _jsxs(Button, { type: "button", variant: "outline", size: "sm", disabled: !trail || trail.load_order.length === 0, onClick: onSaveCheckpoint, children: [_jsx(Flag, { className: "mr-1 h-3.5 w-3.5" }), "Checkpoint"] })] }), hasTrail && (_jsxs("div", { className: "mt-3 grid gap-3 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]", children: [_jsxs("div", { className: "min-w-0", children: [_jsx("div", { className: "mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Load order" }), trail.load_order.length === 0 ? (_jsx("p", { className: "text-xs text-muted-foreground", children: "No matching nodes. Add clearer signpost text to the tree or try another query." })) : (_jsx("div", { className: "flex flex-wrap gap-1", children: trail.load_order.map((segment, index) => (_jsxs("button", { type: "button", onClick: () => onSelectNode(segment.id), className: "inline-flex max-w-[240px] items-center gap-1 rounded-md border border-border bg-background/60 px-2 py-1 text-[11px] hover:border-primary/50 hover:bg-accent/60", title: segment.title, children: [_jsx("span", { className: "text-muted-foreground", children: index + 1 }), _jsx(TypeBadge, { type: segment.node_type }), _jsx("span", { className: "truncate", children: segment.title })] }, segment.id))) }))] }), _jsxs("div", { className: "min-w-0", children: [_jsx("div", { className: "mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Matched branches" }), _jsx("div", { className: "flex max-h-36 flex-col gap-1 overflow-auto pr-1", children: trail.items.map((item) => (_jsxs("button", { type: "button", onClick: () => onSelectNode(item.id), className: "rounded-md border border-border/60 bg-background/50 px-2 py-1.5 text-left text-xs hover:border-primary/50 hover:bg-accent/50", children: [_jsxs("div", { className: "flex min-w-0 items-center gap-1.5", children: [_jsx(TypeBadge, { type: item.node_type }), _jsx("span", { className: "truncate font-medium", children: item.title }), _jsxs("span", { className: "ml-auto shrink-0 text-[10px] text-muted-foreground", children: ["score ", item.score] })] }), _jsx("div", { className: "mt-1 truncate text-[11px] text-muted-foreground", children: item.path.map((part) => part.title).join(" > ") }), item.children.length > 0 && (_jsxs("div", { className: "mt-1 text-[10px] text-muted-foreground", children: [item.children.length, " child hint", item.children.length === 1 ? "" : "s", " available"] }))] }, item.id))) })] })] }))] }));
}
function TreeBranch(props) {
    const siblings = props.childrenByParent.get(props.parentId) ?? [];
    return (_jsx("ul", { className: "space-y-0.5", children: siblings.map((node) => {
            const children = props.childrenByParent.get(node.id) ?? [];
            const hasChildren = children.length > 0;
            const isExpanded = props.expanded.has(node.id);
            const isSelected = props.selectedId === node.id;
            return (_jsxs("li", { children: [_jsxs("div", { className: cn("group flex items-center gap-1 rounded-md border-l-2 pl-1.5 pr-1 py-1 text-xs transition-colors", TYPE_BORDER[node.node_type], isSelected
                            ? "bg-accent text-accent-foreground"
                            : "hover:bg-accent/40"), style: { marginLeft: `${props.depth * 10}px` }, children: [_jsx("button", { type: "button", className: "flex h-4 w-4 shrink-0 items-center justify-center rounded hover:bg-accent", onClick: () => hasChildren && props.onToggle(node.id), "aria-label": isExpanded ? "Collapse" : "Expand", disabled: !hasChildren, children: hasChildren ? (isExpanded ? (_jsx(ChevronDown, { className: "h-3 w-3" })) : (_jsx(ChevronRight, { className: "h-3 w-3" }))) : (_jsx("span", { className: "h-1 w-1 rounded-full bg-muted-foreground/40" })) }), _jsxs("button", { type: "button", className: "flex min-w-0 flex-1 items-center gap-1.5 text-left", onClick: () => props.onSelect(node.id), children: [_jsx(TypeBadge, { type: node.node_type }), _jsx("span", { className: "truncate font-medium", children: node.title })] }), _jsx("button", { type: "button", className: "h-5 w-5 shrink-0 rounded text-muted-foreground opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100", "aria-label": "Add child node", onClick: () => props.onStartCreate(node.id), children: _jsx(Plus, { className: "mx-auto h-3 w-3" }) })] }), isExpanded && (_jsxs(_Fragment, { children: [props.creatingUnder === node.id && (_jsx("div", { style: { marginLeft: `${(props.depth + 1) * 10 + 6}px` }, children: _jsx(NewNodeForm, { projectId: props.projectId, parentId: node.id, onCancel: props.onCancelCreate, onCreated: props.onCreated }) })), hasChildren && (_jsx(TreeBranch, { ...props, parentId: node.id, depth: props.depth + 1 }))] }))] }, node.id));
        }) }));
}
function NewNodeForm({ projectId, parentId, onCancel, onCreated, }) {
    const [title, setTitle] = useState("");
    const [type, setType] = useState("RAW");
    const [saving, setSaving] = useState(false);
    async function submit(e) {
        e.preventDefault();
        if (!title.trim())
            return;
        setSaving(true);
        try {
            const node = await createKnowledgeNode(projectId, {
                title: title.trim(),
                node_type: type,
                content: "",
                parent_id: parentId,
            });
            onCreated(node);
        }
        finally {
            setSaving(false);
        }
    }
    return (_jsxs("form", { onSubmit: submit, className: "my-1 space-y-2 rounded-md border border-border bg-popover p-2 text-xs", children: [_jsx(Input, { autoFocus: true, value: title, onChange: (e) => setTitle(e.target.value), placeholder: "Node title", className: "h-7 text-xs" }), _jsxs(Select, { value: type, onValueChange: (v) => setType(v), children: [_jsx(SelectTrigger, { className: "h-7 text-xs", children: _jsx(SelectValue, {}) }), _jsx(SelectContent, { children: KNOWLEDGE_NODE_TYPES.map((t) => (_jsx(SelectItem, { value: t, children: KNOWLEDGE_NODE_TYPE_LABELS[t] }, t))) })] }), _jsxs("div", { className: "flex justify-end gap-1", children: [_jsx(Button, { type: "button", variant: "ghost", size: "sm", onClick: onCancel, children: "Cancel" }), _jsx(Button, { type: "submit", size: "sm", disabled: saving, children: saving ? "…" : "Create" })] })] }));
}
function NodeEditor({ node, allNodes, onSaved, onDeleted, onSelectNode, }) {
    const [title, setTitle] = useState(node.title);
    const [type, setType] = useState(node.node_type);
    const [content, setContent] = useState(node.content);
    const [sourceRefsText, setSourceRefsText] = useState(node.source_refs.join("\n"));
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [correctionText, setCorrectionText] = useState("");
    const [correctionSaving, setCorrectionSaving] = useState(false);
    // Build an id → KnowledgeNode lookup so ``node:N`` source refs can render
    // a live, clickable chip showing the current title of the referenced
    // node. Re-derives on every render so SSE-driven title edits elsewhere
    // propagate immediately.
    const nodeById = useMemo(() => {
        const map = new Map();
        for (const n of allNodes)
            map.set(n.id, n);
        return map;
    }, [allNodes]);
    const resolvedRefs = useMemo(() => sourceRefsText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
        const match = line.match(/^node:(\d+)$/i);
        if (!match)
            return { kind: "text", value: line };
        const id = Number(match[1]);
        const target = nodeById.get(id);
        return {
            kind: "node",
            value: line,
            id,
            target: target ?? null,
        };
    }), [sourceRefsText, nodeById]);
    const dirty = title !== node.title ||
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
        }
        finally {
            setSaving(false);
        }
    }
    async function remove() {
        if (!window.confirm(`Delete "${node.title}" and all its children?`))
            return;
        setDeleting(true);
        try {
            await deleteKnowledgeNode(node.id);
            onDeleted();
        }
        finally {
            setDeleting(false);
        }
    }
    async function requestCorrection() {
        const correction = correctionText.trim();
        if (!correction)
            return;
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
        }
        finally {
            setCorrectionSaving(false);
        }
    }
    return (_jsxs("div", { className: "flex flex-1 flex-col overflow-hidden", children: [_jsxs("header", { className: "flex items-start justify-between gap-3 border-b border-border bg-card/30 px-6 py-3", children: [_jsxs("div", { className: "min-w-0 flex-1 space-y-2", children: [_jsxs("div", { className: "flex items-center gap-2", children: [_jsx(TypeBadge, { type: type }), _jsx(Input, { value: title, onChange: (e) => setTitle(e.target.value), className: "h-8 flex-1 text-sm font-semibold" }), _jsxs(Select, { value: type, onValueChange: (v) => setType(v), children: [_jsx(SelectTrigger, { className: "h-8 w-28 text-xs", children: _jsx(SelectValue, {}) }), _jsx(SelectContent, { children: KNOWLEDGE_NODE_TYPES.map((t) => (_jsx(SelectItem, { value: t, children: KNOWLEDGE_NODE_TYPE_LABELS[t] }, t))) })] })] }), _jsxs("div", { className: "flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground", children: [_jsxs("span", { className: "uppercase tracking-wide", children: ["#", node.id] }), _jsx("span", { children: "\u00B7" }), _jsxs(Badge, { variant: node.created_by === "AGENT" ? "agent" : "human", className: "py-0 text-[10px]", children: [node.created_by === "AGENT" ? (_jsx(Sparkles, { className: "mr-1 h-2.5 w-2.5" })) : null, node.created_by] }), _jsx("span", { children: "\u00B7" }), _jsxs("span", { children: ["updated ", formatWhen(node.updated_at)] })] })] }), _jsxs("div", { className: "flex items-center gap-1", children: [_jsxs(Button, { variant: "ghost", size: "sm", onClick: remove, disabled: deleting, className: "text-destructive-foreground/80", children: [_jsx(Trash2, { className: "mr-1 h-3.5 w-3.5" }), "Delete"] }), _jsxs(Button, { size: "sm", onClick: save, disabled: !dirty || saving, children: [_jsx(Save, { className: "mr-1 h-3.5 w-3.5" }), saving ? "Saving…" : "Save"] })] })] }), _jsxs("div", { className: "flex flex-1 flex-col gap-3 overflow-auto px-6 py-4", children: [_jsxs("section", { className: "rounded-md border border-border bg-muted/20 p-3", children: [_jsxs("div", { className: "mb-2 flex items-center gap-2", children: [_jsx(MessageSquare, { className: "h-3.5 w-3.5 text-muted-foreground" }), _jsx("label", { className: "text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Correction request" })] }), _jsxs("div", { className: "flex gap-2", children: [_jsx(Textarea, { value: correctionText, onChange: (e) => setCorrectionText(e.target.value), rows: 2, placeholder: "Tell the agent what looks stale, wrong, or missing for this context node.", className: "min-h-16 text-xs" }), _jsx(Button, { type: "button", size: "sm", variant: "outline", className: "self-start", onClick: requestCorrection, disabled: !correctionText.trim() || correctionSaving, children: correctionSaving ? "Saving…" : "Request update" })] })] }), _jsxs("section", { children: [_jsx("label", { className: "mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Source references" }), resolvedRefs.length > 0 && (_jsx("div", { className: "mb-2 flex flex-wrap gap-1", children: resolvedRefs.map((ref, idx) => ref.kind === "node" ? (_jsxs("button", { type: "button", onClick: () => ref.target && onSelectNode(ref.target.id), disabled: !ref.target, title: ref.target
                                        ? `Open node #${ref.id}: ${ref.target.title}`
                                        : `Node #${ref.id} no longer exists in this project`, className: cn("group inline-flex max-w-[260px] items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] transition-colors", ref.target
                                        ? "cursor-pointer border-border bg-card hover:border-primary/50 hover:bg-accent/60"
                                        : "cursor-not-allowed border-destructive/30 bg-destructive/10 text-destructive-foreground/80"), children: [ref.target ? (_jsx(TypeBadge, { type: ref.target.node_type })) : (_jsx("span", { className: "rounded bg-destructive/20 px-1 text-[9px] font-semibold uppercase", children: "GONE" })), _jsxs("span", { className: "truncate", children: ["#", ref.id, " ", ref.target?.title ?? "Missing node"] }), ref.target && (_jsx(ExternalLink, { className: "h-2.5 w-2.5 shrink-0 text-muted-foreground group-hover:text-foreground" }))] }, `${ref.value}-${idx}`)) : (_jsx("span", { className: "inline-flex max-w-[260px] items-center gap-1 rounded-md border border-border/40 bg-muted/30 px-2 py-0.5 font-mono text-[11px] text-muted-foreground", title: ref.value, children: _jsx("span", { className: "truncate", children: ref.value }) }, `${ref.value}-${idx}`))) })), _jsx(Textarea, { value: sourceRefsText, onChange: (e) => setSourceRefsText(e.target.value), rows: 3, placeholder: "/absolute/path/file.py\nhttps://example.com/doc\nnode:42", className: "font-mono text-xs" }), _jsxs("p", { className: "mt-1 text-[10px] text-muted-foreground", children: ["One pointer per line. These are the breadcrumbs a reviewer follows back to the raw material. ", _jsx("span", { className: "font-mono", children: "node:N" }), " ", "entries resolve to clickable chips above."] })] }), _jsxs("section", { className: "flex flex-1 flex-col", children: [_jsx("label", { className: "mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Content" }), _jsx(Textarea, { value: content, onChange: (e) => setContent(e.target.value), className: "min-h-[300px] flex-1 font-mono text-xs", placeholder: CONTENT_PLACEHOLDERS[type] })] })] }), dirty && (_jsxs("footer", { className: "flex items-center justify-end gap-2 border-t border-border bg-muted/20 px-6 py-2 text-xs", children: [_jsx("span", { className: "text-muted-foreground", children: "Unsaved changes" }), _jsxs(Button, { variant: "ghost", size: "sm", onClick: () => {
                            setTitle(node.title);
                            setType(node.node_type);
                            setContent(node.content);
                            setSourceRefsText(node.source_refs.join("\n"));
                        }, children: [_jsx(X, { className: "mr-1 h-3.5 w-3.5" }), "Revert"] }), _jsxs(Button, { size: "sm", onClick: save, disabled: saving, children: [_jsx(Save, { className: "mr-1 h-3.5 w-3.5" }), saving ? "Saving…" : "Save"] })] }))] }));
}
// ---- visuals --------------------------------------------------------------
const TYPE_BORDER = {
    // Bauhaus-flavored type indicators: heavy 2px left borders, no rounding
    // on the border itself, sized to remain legible against the existing
    // shadcn palette.
    RAW: "border-slate-500",
    SUMMARY: "border-amber-500",
    PRD: "border-sky-500",
    TDD: "border-emerald-500",
};
const TYPE_BADGE = {
    RAW: "bg-slate-600/30 text-slate-100",
    SUMMARY: "bg-amber-500/30 text-amber-100",
    PRD: "bg-sky-500/30 text-sky-100",
    TDD: "bg-emerald-500/30 text-emerald-100",
};
function TypeBadge({ type }) {
    return (_jsx("span", { className: cn("inline-flex h-4 items-center justify-center rounded px-1 text-[9px] font-semibold uppercase tracking-wider", TYPE_BADGE[type]), children: type }));
}
const CONTENT_PLACEHOLDERS = {
    RAW: "Paste the raw file excerpt, documentation, or research content here.",
    SUMMARY: "Write a compressed summary of this branch of the tree. Reference the children by their #id so a reviewer can drill down.",
    PRD: "# Product Requirements Document\n\n## Goal\n\n## User stories\n\n## Acceptance criteria",
    TDD: "# Technical Design Document\n\n## Architecture\n\n## Data model\n\n## Open questions",
};
function formatWhen(iso) {
    try {
        const date = new Date(iso);
        return date.toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    }
    catch {
        return iso;
    }
}
