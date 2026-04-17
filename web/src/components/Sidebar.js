import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { FolderPlus, Plus, Folder, FileText, Loader2 } from "lucide-react";
import { createProject, createSubproject, listProjects, listSubprojects, } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { useAsync } from "@/hooks/useAsync";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
export function Sidebar({ lastEvent }) {
    const { activeProjectId, activeSubprojectId, setActiveProjectId, setActiveSubprojectId, } = useWorkspace();
    const projects = useAsync(() => listProjects(), []);
    useEffect(() => {
        if (!lastEvent)
            return;
        if (lastEvent.action === "PROJECT_CREATED")
            projects.refetch();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lastEvent]);
    // Default-select the first project once data arrives.
    useEffect(() => {
        if (activeProjectId == null &&
            projects.data &&
            projects.data.length > 0) {
            setActiveProjectId(projects.data[0].id);
        }
    }, [activeProjectId, projects.data, setActiveProjectId]);
    return (_jsxs("aside", { className: "flex w-72 shrink-0 flex-col border-r border-border bg-card/30", children: [_jsxs("header", { className: "border-b border-border px-4 py-3", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("h1", { className: "text-sm font-semibold tracking-tight", children: "Taskable" }), _jsx("span", { className: "text-[10px] uppercase tracking-widest text-muted-foreground", children: "Co-Pilot" })] }), _jsx("p", { className: "mt-1 text-xs text-muted-foreground", children: "Human + Agent workspace" })] }), _jsx(ScrollArea, { className: "flex-1", children: _jsx("div", { className: "space-y-4 px-3 py-4", children: _jsxs("section", { children: [_jsxs("div", { className: "mb-2 flex items-center justify-between px-1", children: [_jsx("span", { className: "text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Projects" }), _jsx(NewProjectButton, { onCreated: projects.refetch })] }), projects.loading && (_jsxs("div", { className: "flex items-center gap-2 px-2 py-2 text-xs text-muted-foreground", children: [_jsx(Loader2, { className: "h-3 w-3 animate-spin" }), "Loading\u2026"] })), projects.error && (_jsx("p", { className: "px-2 py-2 text-xs text-destructive-foreground/80", children: projects.error.message })), projects.data?.length === 0 && !projects.loading && (_jsx("p", { className: "px-2 py-2 text-xs text-muted-foreground", children: "No projects yet. Create one to begin." })), _jsx("ul", { className: "space-y-1", children: projects.data?.map((project) => (_jsxs("li", { children: [_jsxs("button", { className: cn("flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors", activeProjectId === project.id
                                                ? "bg-accent text-accent-foreground"
                                                : "hover:bg-accent/50"), onClick: () => setActiveProjectId(project.id), children: [_jsx(Folder, { className: "h-3.5 w-3.5 shrink-0" }), _jsx("span", { className: "truncate", children: project.name })] }), activeProjectId === project.id && (_jsx(SubprojectList, { projectId: project.id, lastEvent: lastEvent, activeSubprojectId: activeSubprojectId, onSelect: setActiveSubprojectId }))] }, project.id))) })] }) }) })] }));
}
function SubprojectList({ projectId, lastEvent, activeSubprojectId, onSelect, }) {
    const subprojects = useAsync(() => listSubprojects(projectId), [projectId]);
    useEffect(() => {
        if (!lastEvent)
            return;
        if (lastEvent.action === "SUBPROJECT_CREATED" ||
            lastEvent.action === "SUBPROJECT_UPDATED") {
            subprojects.refetch();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [lastEvent]);
    useEffect(() => {
        if (activeSubprojectId == null &&
            subprojects.data &&
            subprojects.data.length > 0) {
            onSelect(subprojects.data[0].id);
        }
    }, [activeSubprojectId, subprojects.data, onSelect]);
    return (_jsxs("div", { className: "ml-6 mt-1 border-l border-border pl-3", children: [_jsxs("div", { className: "mb-1 flex items-center justify-between", children: [_jsx("span", { className: "text-[10px] uppercase tracking-wider text-muted-foreground", children: "Subprojects" }), _jsx(NewSubprojectButton, { projectId: projectId, onCreated: subprojects.refetch })] }), _jsxs("ul", { className: "space-y-0.5", children: [subprojects.data?.map((sub) => (_jsx("li", { children: _jsxs("button", { className: cn("flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors", activeSubprojectId === sub.id
                                ? "bg-primary/10 text-primary-foreground"
                                : "text-muted-foreground hover:bg-accent/40"), onClick: () => onSelect(sub.id), children: [_jsx(FileText, { className: "h-3 w-3 shrink-0" }), _jsx("span", { className: "truncate", children: sub.name }), _jsx("span", { className: "ml-auto rounded bg-muted px-1 text-[9px] uppercase text-muted-foreground", children: sub.status.slice(0, 4) })] }) }, sub.id))), subprojects.data?.length === 0 && (_jsx("li", { className: "px-2 py-1 text-[11px] text-muted-foreground", children: "None yet." }))] })] }));
}
function NewProjectButton({ onCreated }) {
    const [expanded, setExpanded] = useState(false);
    const [name, setName] = useState("");
    const [desc, setDesc] = useState("");
    const [saving, setSaving] = useState(false);
    async function submit(e) {
        e.preventDefault();
        if (!name.trim())
            return;
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
        }
        finally {
            setSaving(false);
        }
    }
    if (!expanded) {
        return (_jsx(Button, { variant: "ghost", size: "icon", className: "h-6 w-6", onClick: () => setExpanded(true), "aria-label": "New project", children: _jsx(FolderPlus, { className: "h-3.5 w-3.5" }) }));
    }
    return (_jsxs("form", { onSubmit: submit, className: "absolute inset-x-3 top-12 z-20 space-y-2 rounded-md border border-border bg-popover p-3 text-xs shadow-lg", children: [_jsx(Input, { autoFocus: true, placeholder: "Project name", value: name, onChange: (e) => setName(e.target.value), className: "h-8 text-xs" }), _jsx(Textarea, { placeholder: "Description (optional)", value: desc, onChange: (e) => setDesc(e.target.value), className: "min-h-[60px] text-xs" }), _jsxs("div", { className: "flex justify-end gap-1", children: [_jsx(Button, { type: "button", variant: "ghost", size: "sm", onClick: () => setExpanded(false), children: "Cancel" }), _jsx(Button, { type: "submit", size: "sm", disabled: saving, children: saving ? "…" : "Create" })] })] }));
}
function NewSubprojectButton({ projectId, onCreated, }) {
    const [expanded, setExpanded] = useState(false);
    const [name, setName] = useState("");
    const [brief, setBrief] = useState("");
    const [saving, setSaving] = useState(false);
    async function submit(e) {
        e.preventDefault();
        if (!name.trim())
            return;
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
        }
        finally {
            setSaving(false);
        }
    }
    if (!expanded) {
        return (_jsx(Button, { variant: "ghost", size: "icon", className: "h-5 w-5", onClick: () => setExpanded(true), "aria-label": "New subproject", children: _jsx(Plus, { className: "h-3 w-3" }) }));
    }
    return (_jsxs("form", { onSubmit: submit, className: "ml-2 mt-1 space-y-2 rounded-md border border-border bg-popover p-2 text-xs", children: [_jsx(Input, { autoFocus: true, placeholder: "Subproject", value: name, onChange: (e) => setName(e.target.value), className: "h-7 text-xs" }), _jsx(Textarea, { placeholder: "Context brief for the agent", value: brief, onChange: (e) => setBrief(e.target.value), className: "min-h-[60px] text-xs" }), _jsxs("div", { className: "flex justify-end gap-1", children: [_jsx(Button, { type: "button", variant: "ghost", size: "sm", onClick: () => setExpanded(false), children: "Cancel" }), _jsx(Button, { type: "submit", size: "sm", disabled: saving, children: saving ? "…" : "Add" })] })] }));
}
