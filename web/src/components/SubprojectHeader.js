import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Pencil, Save, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, } from "@/components/ui/select";
import { updateSubproject } from "@/lib/api";
const STATUSES = ["PLANNING", "ACTIVE", "COMPLETED"];
export function SubprojectHeader({ subproject, onSaved }) {
    const [editing, setEditing] = useState(false);
    const [name, setName] = useState(subproject.name);
    const [brief, setBrief] = useState(subproject.context_brief);
    const [status, setStatus] = useState(subproject.status);
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
        }
        finally {
            setSaving(false);
        }
    }
    return (_jsx("div", { className: "border-b border-border bg-card/40 px-6 py-4", children: !editing ? (_jsxs("div", { className: "flex items-start justify-between gap-6", children: [_jsxs("div", { className: "min-w-0 flex-1", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("h2", { className: "truncate text-xl font-semibold tracking-tight", children: subproject.name }), _jsx(Badge, { variant: "outline", className: "uppercase tracking-wide", children: subproject.status })] }), _jsx("p", { className: "mt-1 max-w-3xl whitespace-pre-wrap text-sm text-muted-foreground", children: subproject.context_brief.trim() ||
                                "No context brief. The agent will have nothing to work from until this is filled in." })] }), _jsx(Button, { variant: "ghost", size: "icon", onClick: () => {
                        reset();
                        setEditing(true);
                    }, "aria-label": "Edit subproject", children: _jsx(Pencil, { className: "h-4 w-4" }) })] })) : (_jsxs("div", { className: "space-y-3", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx(Input, { value: name, onChange: (e) => setName(e.target.value), className: "h-9 max-w-md text-base font-semibold" }), _jsxs(Select, { value: status, onValueChange: (v) => setStatus(v), children: [_jsx(SelectTrigger, { className: "h-9 w-40", children: _jsx(SelectValue, {}) }), _jsx(SelectContent, { children: STATUSES.map((s) => (_jsx(SelectItem, { value: s, children: s }, s))) })] })] }), _jsx(Textarea, { value: brief, onChange: (e) => setBrief(e.target.value), rows: 3, placeholder: "Context brief used by the MCP agent for orientation." }), _jsxs("div", { className: "flex items-center justify-end gap-2", children: [_jsxs(Button, { variant: "ghost", size: "sm", onClick: () => {
                                reset();
                                setEditing(false);
                            }, children: [_jsx(X, { className: "mr-1 h-3.5 w-3.5" }), "Cancel"] }), _jsxs(Button, { size: "sm", onClick: save, disabled: saving, children: [_jsx(Save, { className: "mr-1 h-3.5 w-3.5" }), saving ? "Saving…" : "Save"] })] })] })) }));
}
