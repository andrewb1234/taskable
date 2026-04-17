import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Bot, Send, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { createComment } from "@/lib/api";
export function CommentThread({ ticketId, comments, onPosted }) {
    const [content, setContent] = useState("");
    const [saving, setSaving] = useState(false);
    async function submit(e) {
        e.preventDefault();
        if (!content.trim())
            return;
        setSaving(true);
        try {
            await createComment(ticketId, {
                author: "HUMAN",
                content: content.trim(),
            });
            setContent("");
            onPosted();
        }
        finally {
            setSaving(false);
        }
    }
    return (_jsxs("div", { className: "flex h-full flex-col", children: [_jsx("h4", { className: "mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", children: "Discussion" }), _jsxs("div", { className: "flex-1 space-y-3 overflow-y-auto pr-2", children: [comments.length === 0 && (_jsx("p", { className: "text-xs text-muted-foreground", children: "No messages yet. Comments from the agent will appear here." })), comments.map((comment) => (_jsxs("div", { className: cn("flex gap-2", comment.author === "AGENT" ? "flex-row-reverse" : ""), children: [_jsx("div", { className: cn("flex h-6 w-6 shrink-0 items-center justify-center rounded-full", comment.author === "AGENT"
                                    ? "bg-fuchsia-500/20 text-fuchsia-200"
                                    : "bg-sky-500/20 text-sky-200"), children: comment.author === "AGENT" ? (_jsx(Bot, { className: "h-3.5 w-3.5" })) : (_jsx(User, { className: "h-3.5 w-3.5" })) }), _jsxs("div", { className: cn("max-w-[85%] rounded-md border border-border bg-background/70 px-3 py-2 text-xs", comment.author === "AGENT" ? "text-right" : ""), children: [_jsx("p", { className: "whitespace-pre-wrap", children: comment.content }), _jsx("p", { className: "mt-1 text-[10px] text-muted-foreground", children: new Date(comment.timestamp + "Z").toLocaleString() })] })] }, comment.id)))] }), _jsxs("form", { onSubmit: submit, className: "mt-3 flex items-end gap-2", children: [_jsx(Textarea, { value: content, onChange: (e) => setContent(e.target.value), placeholder: "Write a comment as Human\u2026", rows: 2, onKeyDown: (e) => {
                            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                                void submit(e);
                            }
                        } }), _jsx(Button, { type: "submit", size: "icon", disabled: saving || !content.trim(), children: _jsx(Send, { className: "h-4 w-4" }) })] })] }));
}
