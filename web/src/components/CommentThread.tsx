import { useState } from "react";
import { Bot, Send, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { createComment } from "@/lib/api";
import type { Comment } from "@/types";

interface Props {
  ticketId: number;
  comments: Comment[];
  onPosted: () => void;
}

export function CommentThread({ ticketId, comments, onPosted }: Props) {
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!content.trim()) return;
    setSaving(true);
    try {
      await createComment(ticketId, {
        author: "HUMAN",
        content: content.trim(),
      });
      setContent("");
      onPosted();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Discussion
      </h4>
      <div className="flex-1 space-y-3 overflow-y-auto pr-2">
        {comments.length === 0 && (
          <p className="text-xs text-muted-foreground">
            No messages yet. Comments from the agent will appear here.
          </p>
        )}
        {comments.map((comment) => (
          <div
            key={comment.id}
            className={cn(
              "flex gap-2",
              comment.author === "AGENT" ? "flex-row-reverse" : "",
            )}
          >
            <div
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                comment.author === "AGENT"
                  ? "bg-fuchsia-500/20 text-fuchsia-200"
                  : "bg-sky-500/20 text-sky-200",
              )}
            >
              {comment.author === "AGENT" ? (
                <Bot className="h-3.5 w-3.5" />
              ) : (
                <User className="h-3.5 w-3.5" />
              )}
            </div>
            <div
              className={cn(
                "max-w-[85%] rounded-md border border-border bg-background/70 px-3 py-2 text-xs",
                comment.author === "AGENT" ? "text-right" : "",
              )}
            >
              <p className="whitespace-pre-wrap">{comment.content}</p>
              <p className="mt-1 text-[10px] text-muted-foreground">
                {new Date(comment.timestamp + "Z").toLocaleString()}
              </p>
            </div>
          </div>
        ))}
      </div>
      <form onSubmit={submit} className="mt-3 flex items-end gap-2">
        <Textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Write a comment as Human…"
          rows={2}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              void submit(e);
            }
          }}
        />
        <Button type="submit" size="icon" disabled={saving || !content.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
