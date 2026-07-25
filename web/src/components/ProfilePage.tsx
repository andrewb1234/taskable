import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  Copy,
  Check,
  KeyRound,
  Plus,
  Trash2,
  Terminal,
  AlertCircle,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  listApiKeys,
  createApiKey,
  revokeApiKey,
  listProjects,
  listWorkspaces,
  listBrowserSessions,
  revokeBrowserSession,
} from "@/lib/api";
import type {
  ApiKey,
  ApiKeyCreated,
  BrowserSession,
  Project,
  Workspace,
} from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { McpSetupModal } from "@/components/McpSetupModal";

interface ProfilePageProps {
  onBack: () => void;
}

export function ProfilePage({ onBack }: ProfilePageProps) {
  const { user, logout } = useAuth();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyExpiry, setNewKeyExpiry] = useState("");
  const [newKeyWorkspaceId, setNewKeyWorkspaceId] = useState("");
  const [newKeyAccess, setNewKeyAccess] = useState<"read" | "read-write">(
    "read-write",
  );
  const [newKeyProjectIds, setNewKeyProjectIds] = useState<number[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [browserSessions, setBrowserSessions] = useState<BrowserSession[]>([]);
  const [creating, setCreating] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [mcpOpen, setMcpOpen] = useState(false);

  const fetchKeys = useCallback(async () => {
    try {
      const data = await listApiKeys();
      setKeys(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load API keys");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  useEffect(() => {
    Promise.all([listWorkspaces(), listProjects(), listBrowserSessions()])
      .then(([workspaceRows, projectRows, sessionRows]) => {
        setWorkspaces(workspaceRows);
        setProjects(projectRows);
        setBrowserSessions(sessionRows);
        setNewKeyWorkspaceId((current) =>
          current || (workspaceRows[0] ? String(workspaceRows[0].id) : ""),
        );
      })
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load workspace access options",
        );
      });
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newKeyName.trim() || !newKeyWorkspaceId) return;
    setCreating(true);
    setError(null);
    try {
      const payload: {
        name: string;
        workspace_id: number;
        scopes: Array<"read" | "write">;
        project_ids: number[];
        expires_in_days?: number;
      } = {
        name: newKeyName.trim(),
        workspace_id: Number(newKeyWorkspaceId),
        scopes: newKeyAccess === "read" ? ["read"] : ["read", "write"],
        project_ids: newKeyProjectIds,
      };
      if (newKeyExpiry) {
        const days = parseInt(newKeyExpiry, 10);
        if (!isNaN(days) && days > 0) {
          payload.expires_in_days = days;
        }
      }
      const created = await createApiKey(payload);
      setNewlyCreatedKey(created);
      setNewKeyName("");
      setNewKeyExpiry("");
      setNewKeyProjectIds([]);
      fetchKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create API key");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id: number) {
    if (!window.confirm("Revoke this API key? Agents using it will lose access immediately.")) {
      return;
    }
    try {
      await revokeApiKey(id);
      fetchKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke key");
    }
  }

  async function handleRevokeSession(id: string, current: boolean) {
    const message = current
      ? "Sign out this browser session now?"
      : "Revoke this browser session?";
    if (!window.confirm(message)) return;
    try {
      await revokeBrowserSession(id);
      if (current) {
        window.location.assign("/");
        return;
      }
      setBrowserSessions((sessions) =>
        sessions.filter((session) => session.id !== id),
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to revoke browser session",
      );
    }
  }

  function copyKey(key: string) {
    navigator.clipboard.writeText(key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "—";
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  const activeKeys = keys.filter((k) => !k.revoked);
  const revokedKeys = keys.filter((k) => k.revoked);
  const selectedWorkspaceProjects = projects.filter(
    (project) => project.workspace_id === Number(newKeyWorkspaceId),
  );
  const workspaceName = (workspaceId: number | null) =>
    workspaces.find((workspace) => workspace.id === workspaceId)?.name ??
    "Unknown workspace";

  return (
    <div className="flex h-screen w-screen flex-col bg-background">
      {/* Header */}
      <header className="flex items-center gap-3 border-b border-border px-6 py-4">
        <Button variant="ghost" size="icon" onClick={onBack} aria-label="Back">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-lg font-semibold">Profile & Settings</h1>
      </header>

      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-3xl space-y-8 px-6 py-8">
          {/* User info */}
          <section className="flex items-center gap-4">
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.name}
                className="h-16 w-16 rounded-full"
              />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-xl font-medium text-primary-foreground">
                {user?.name?.charAt(0).toUpperCase() ?? "?"}
              </div>
            )}
            <div>
              <p className="text-lg font-semibold">{user?.name}</p>
              <p className="text-sm text-muted-foreground">{user?.email}</p>
            </div>
          </section>

          {/* MCP Setup */}
          <section className="rounded-lg border border-border bg-card p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  <Terminal className="h-4 w-4" />
                  MCP Server Configuration
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Connect your AI coding assistant (Claude, Windsurf, Cursor, etc.)
                  to mouvadah. You'll need an API key first.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setMcpOpen(true)}
              >
                <Terminal className="mr-1.5 h-3.5 w-3.5" />
                Setup Guide
              </Button>
            </div>
          </section>

          {/* API Keys */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <KeyRound className="h-4 w-4" />
                API Keys
              </h2>
              <span className="text-xs text-muted-foreground">
                {activeKeys.length} active
              </span>
            </div>

            {/* New key form */}
            <form
              onSubmit={handleCreate}
              className="grid gap-3 rounded-lg border border-border bg-card p-4 sm:grid-cols-2"
            >
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Key name
                </label>
                <Input
                  autoFocus
                  placeholder="e.g. Claude Desktop, Windsurf, CI bot"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Workspace
                </label>
                <select
                  value={newKeyWorkspaceId}
                  onChange={(event) => {
                    setNewKeyWorkspaceId(event.target.value);
                    setNewKeyProjectIds([]);
                  }}
                  className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                >
                  {workspaces.map((workspace) => (
                    <option key={workspace.id} value={workspace.id}>
                      {workspace.name} · {workspace.role}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Access
                </label>
                <select
                  value={newKeyAccess}
                  onChange={(event) =>
                    setNewKeyAccess(event.target.value as "read" | "read-write")
                  }
                  className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
                >
                  <option value="read-write">Read and write</option>
                  <option value="read">Read only</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Expires (days)
                </label>
                <Input
                  type="number"
                  min="1"
                  max="365"
                  placeholder="Never"
                  value={newKeyExpiry}
                  onChange={(e) => setNewKeyExpiry(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
              {selectedWorkspaceProjects.length > 0 && (
                <fieldset className="space-y-2 sm:col-span-2">
                  <legend className="text-xs font-medium text-muted-foreground">
                    Project restriction (optional)
                  </legend>
                  <p className="text-[11px] text-muted-foreground">
                    No selection grants the key access to every project in this
                    workspace.
                  </p>
                  <div className="grid max-h-32 gap-1 overflow-auto rounded-md border border-border p-2 sm:grid-cols-2">
                    {selectedWorkspaceProjects.map((project) => (
                      <label
                        key={project.id}
                        className="flex items-center gap-2 text-xs"
                      >
                        <input
                          type="checkbox"
                          checked={newKeyProjectIds.includes(project.id)}
                          onChange={(event) =>
                            setNewKeyProjectIds((current) =>
                              event.target.checked
                                ? [...current, project.id]
                                : current.filter((id) => id !== project.id),
                            )
                          }
                        />
                        <span className="truncate">{project.name}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              )}
              <div className="sm:col-span-2">
                <Button
                  type="submit"
                  size="sm"
                  disabled={creating || !newKeyName.trim() || !newKeyWorkspaceId}
                >
                {creating ? (
                  <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Plus className="mr-1 h-3.5 w-3.5" />
                )}
                Create Key
                </Button>
              </div>
            </form>

            {/* Newly created key banner */}
            {newlyCreatedKey && (
              <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-4">
                <div className="flex items-start gap-2">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-green-600" />
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-green-700 dark:text-green-400">
                      API key created — copy it now!
                    </p>
                    <p className="mt-0.5 text-xs text-green-600 dark:text-green-500">
                      This key won't be shown again. Store it securely.
                    </p>
                    <div className="mt-2 flex items-center gap-2">
                      <code className="flex-1 truncate rounded bg-green-500/10 px-2 py-1.5 text-xs font-mono">
                        {newlyCreatedKey.key}
                      </code>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 shrink-0"
                        onClick={() => copyKey(newlyCreatedKey.key)}
                      >
                        {copied ? (
                          <Check className="h-3.5 w-3.5 text-green-600" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() => {
                        setMcpOpen(true);
                      }}
                    >
                      <Terminal className="mr-1.5 h-3.5 w-3.5" />
                      Configure MCP with this key
                    </Button>
                    <button
                      className="ml-2 text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => setNewlyCreatedKey(null)}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive-foreground/80">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}

            {/* Key list */}
            {loading ? (
              <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading keys…
              </div>
            ) : (
              <div className="space-y-2">
                {activeKeys.map((key) => (
                  <div
                    key={key.id}
                    className="flex items-center gap-3 rounded-lg border border-border bg-card p-3"
                  >
                    <KeyRound className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium">{key.name}</p>
                        {key.expires_at && (
                          <span className="rounded bg-yellow-500/10 px-1.5 py-0.5 text-[10px] text-yellow-600 dark:text-yellow-400">
                            Expires {formatDate(key.expires_at)}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        <code>{key.key_prefix}…</code>
                        {" · "}{workspaceName(key.workspace_id)}
                        {" · "}{key.scopes.includes("write") ? "Read/write" : "Read only"}
                        {" · "}
                        {key.project_ids.length
                          ? `${key.project_ids.length} project${key.project_ids.length === 1 ? "" : "s"}`
                          : "All projects"}
                        {" · "}Created {formatDate(key.created_at)}
                        {" · "}Last used {formatDate(key.last_used_at)}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive-foreground"
                      onClick={() => handleRevoke(key.id)}
                      aria-label={`Revoke ${key.name}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}

                {revokedKeys.length > 0 && (
                  <>
                    <p className="pt-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Revoked
                    </p>
                    {revokedKeys.map((key) => (
                      <div
                        key={key.id}
                        className="flex items-center gap-3 rounded-lg border border-border bg-muted/30 p-3 opacity-60"
                      >
                        <KeyRound className="h-4 w-4 shrink-0" />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium line-through">{key.name}</p>
                          <p className="text-xs text-muted-foreground">
                            <code>{key.key_prefix}…</code>
                          </p>
                        </div>
                      </div>
                    ))}
                  </>
                )}

                {keys.length === 0 && !loading && (
                  <div className="rounded-lg border border-dashed border-border p-8 text-center">
                    <KeyRound className="mx-auto h-8 w-8 text-muted-foreground/50" />
                    <p className="mt-2 text-sm text-muted-foreground">
                      No API keys yet. Create one to let your AI agent access mouvadah.
                    </p>
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Browser sessions */}
          <section className="space-y-4">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <ShieldCheck className="h-4 w-4" />
                Browser Sessions
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Revoke sessions you no longer recognize. Revocation takes effect
                immediately.
              </p>
            </div>
            <div className="space-y-2">
              {browserSessions.map((browserSession) => (
                <div
                  key={browserSession.id}
                  className="flex items-center gap-3 rounded-lg border border-border bg-card p-3"
                >
                  <ShieldCheck className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">
                      {browserSession.current ? "This browser" : "Browser session"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Last active {formatDate(browserSession.last_seen_at)}
                      {" · "}Expires {formatDate(browserSession.expires_at)}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      handleRevokeSession(
                        browserSession.id,
                        browserSession.current,
                      )
                    }
                  >
                    {browserSession.current ? "Sign out" : "Revoke"}
                  </Button>
                </div>
              ))}
            </div>
          </section>

          {/* Sign out */}
          <section className="pt-4">
            <Button variant="outline" onClick={logout}>
              Sign out
            </Button>
          </section>
        </div>
      </div>

      <McpSetupModal
        open={mcpOpen}
        onOpenChange={setMcpOpen}
        apiKey={newlyCreatedKey?.key ?? null}
      />
    </div>
  );
}
