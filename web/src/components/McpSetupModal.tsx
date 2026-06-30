import { useState } from "react";
import { Check, Copy, Terminal, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface McpSetupModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiKey: string | null;
}

type Provider = "claude" | "windsurf" | "cursor" | "vscode";

const PROVIDERS: { id: Provider; label: string; file: string }[] = [
  { id: "claude", label: "Claude Desktop", file: "~/Library/Application Support/Claude/claude_desktop_config.json" },
  { id: "windsurf", label: "Windsurf", file: "~/.codeium/windsurf/mcp_config.json" },
  { id: "cursor", label: "Cursor", file: "~/.cursor/mcp.json" },
  { id: "vscode", label: "VS Code", file: "Settings → MCP" },
];

function buildConfig(apiKey: string, apiUrl: string): string {
  return JSON.stringify(
    {
      mcpServers: {
        taskable: {
          command: "taskable-mcp",
          args: [],
          env: {
            TASKABLE_API_URL: apiUrl,
            TASKABLE_API_KEY: apiKey,
          },
        },
      },
    },
    null,
    2,
  );
}

export function McpSetupModal({ open, onOpenChange, apiKey }: McpSetupModalProps) {
  const [provider, setProvider] = useState<Provider>("claude");
  const [copied, setCopied] = useState(false);

  const apiUrl = `${window.location.origin}/api/v1`;
  const config = apiKey
    ? buildConfig(apiKey, apiUrl)
    : 'Create an API key first, then paste it here.';

  function copyConfig() {
    navigator.clipboard.writeText(config);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const activeProvider = PROVIDERS.find((p) => p.id === provider)!;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            Configure MCP Server
          </DialogTitle>
          <DialogDescription>
            Add Taskable to your AI coding assistant so it can manage projects,
            tickets, and knowledge nodes.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 px-6 pb-6">
          {/* Provider tabs */}
          <div className="flex flex-wrap gap-2">
            {PROVIDERS.map((p) => (
              <button
                key={p.id}
                onClick={() => setProvider(p.id)}
                className={cn(
                  "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  provider === p.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent",
                )}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Config location */}
          <div className="rounded-md border border-border bg-muted/50 p-3">
            <p className="text-xs text-muted-foreground">
              <span className="font-semibold">Config location:</span>{" "}
              <code className="text-foreground">{activeProvider.file}</code>
            </p>
          </div>

          {/* JSON config */}
          <div className="relative">
            <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted/50 p-4 text-xs">
              <code>{config}</code>
            </pre>
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-2 top-2 h-7 w-7"
              onClick={copyConfig}
              disabled={!apiKey}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-green-500" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>

          {/* Warning */}
          {!apiKey && (
            <div className="flex items-start gap-2 rounded-md border border-yellow-500/30 bg-yellow-500/10 p-3">
              <X className="mt-0.5 h-4 w-4 shrink-0 text-yellow-600" />
              <p className="text-xs text-yellow-700 dark:text-yellow-400">
                You need to create an API key first. Close this dialog, generate
                a key, then reopen this dialog to get the full config.
              </p>
            </div>
          )}

          {/* Steps */}
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-muted-foreground">
              Setup steps:
            </p>
            <ol className="ml-4 list-decimal space-y-1 text-xs text-muted-foreground">
              <li>Install the Taskable MCP server: <code className="text-foreground">pipx install taskable</code> or <code className="text-foreground">uv tool install taskable</code></li>
              <li>Copy the JSON config above</li>
              <li>Paste it into the config file for {activeProvider.label}</li>
              <li>Restart {activeProvider.label}</li>
              <li>Your AI assistant can now use Taskable tools</li>
            </ol>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
