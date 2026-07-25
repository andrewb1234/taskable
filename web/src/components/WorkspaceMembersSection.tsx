import { useCallback, useEffect, useState } from "react";
import {
  Check,
  Copy,
  Loader2,
  Shield,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import {
  createWorkspaceInvitation,
  listWorkspaceInvitations,
  listWorkspaceMembers,
  removeWorkspaceMember,
  revokeWorkspaceInvitation,
  transferWorkspaceOwnership,
  updateWorkspaceMemberRole,
} from "@/lib/api";
import type {
  Workspace,
  WorkspaceInvitation,
  WorkspaceInvitationCreated,
  WorkspaceMember,
} from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface WorkspaceMembersSectionProps {
  workspaces: Workspace[];
  currentUserId: number;
  onWorkspacesChanged: () => Promise<void>;
  onError: (message: string) => void;
}

type HumanRole = "ADMIN" | "MEMBER" | "VIEWER";

export function WorkspaceMembersSection({
  workspaces,
  currentUserId,
  onWorkspacesChanged,
  onError,
}: WorkspaceMembersSectionProps) {
  const ownerWorkspaces = workspaces.filter(
    (workspace) =>
      workspace.role === "OWNER" && !workspace.deletion_requested_at,
  );
  const [members, setMembers] = useState<Record<number, WorkspaceMember[]>>({});
  const [invitations, setInvitations] = useState<
    Record<number, WorkspaceInvitation[]>
  >({});
  const [emails, setEmails] = useState<Record<number, string>>({});
  const [roles, setRoles] = useState<Record<number, HumanRole>>({});
  const [created, setCreated] = useState<
    Record<number, WorkspaceInvitationCreated | null>
  >({});
  const [busy, setBusy] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [loadingWorkspaceIds, setLoadingWorkspaceIds] = useState<number[]>([]);
  const [loadErrors, setLoadErrors] = useState<Record<number, string | null>>(
    {},
  );

  const loadWorkspace = useCallback(
    async (workspaceId: number) => {
      setLoadingWorkspaceIds((current) => [...current, workspaceId]);
      setLoadErrors((current) => ({ ...current, [workspaceId]: null }));
      try {
        const [memberRows, invitationRows] = await Promise.all([
          listWorkspaceMembers(workspaceId),
          listWorkspaceInvitations(workspaceId),
        ]);
        setMembers((current) => ({ ...current, [workspaceId]: memberRows }));
        setInvitations((current) => ({
          ...current,
          [workspaceId]: invitationRows,
        }));
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Failed to load workspace members";
        setLoadErrors((current) => ({ ...current, [workspaceId]: message }));
        throw error;
      } finally {
        setLoadingWorkspaceIds((current) =>
          current.filter((id) => id !== workspaceId),
        );
      }
    },
    [],
  );

  useEffect(() => {
    Promise.all(
      ownerWorkspaces.map((workspace) => loadWorkspace(workspace.id)),
    ).catch((error) =>
      onError(
        error instanceof Error
          ? error.message
          : "Failed to load workspace members",
      ),
    );
  }, [loadWorkspace, onError, workspaces]);

  if (ownerWorkspaces.length === 0) return null;

  async function invite(workspace: Workspace) {
    const email = emails[workspace.id]?.trim();
    if (!email) return;
    setBusy(`invite-${workspace.id}`);
    try {
      const invitation = await createWorkspaceInvitation(workspace.id, {
        email,
        role: roles[workspace.id] ?? "MEMBER",
        expires_in_days: 7,
      });
      setCreated((current) => ({
        ...current,
        [workspace.id]: invitation,
      }));
      setEmails((current) => ({ ...current, [workspace.id]: "" }));
      await loadWorkspace(workspace.id);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Failed to invite member");
    } finally {
      setBusy(null);
    }
  }

  async function revoke(workspaceId: number, invitationId: number) {
    if (!window.confirm("Revoke this invitation link?")) return;
    setBusy(`invite-${invitationId}`);
    try {
      await revokeWorkspaceInvitation(workspaceId, invitationId);
      await loadWorkspace(workspaceId);
    } catch (error) {
      onError(
        error instanceof Error ? error.message : "Failed to revoke invitation",
      );
    } finally {
      setBusy(null);
    }
  }

  async function changeRole(
    workspaceId: number,
    member: WorkspaceMember,
    role: HumanRole,
  ) {
    if (
      !window.confirm(
        `Change ${member.name}'s workspace role from ${member.role} to ${role}?`,
      )
    ) {
      return;
    }
    setBusy(`member-${member.user_id}`);
    try {
      await updateWorkspaceMemberRole(workspaceId, member.user_id, role);
      await loadWorkspace(workspaceId);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Failed to change role");
    } finally {
      setBusy(null);
    }
  }

  async function remove(workspaceId: number, member: WorkspaceMember) {
    if (
      !window.confirm(
        `Remove ${member.name}? Their keys for this workspace will be revoked and every browser session will be signed out.`,
      )
    ) {
      return;
    }
    setBusy(`member-${member.user_id}`);
    try {
      await removeWorkspaceMember(workspaceId, member.user_id);
      await loadWorkspace(workspaceId);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Failed to remove member");
    } finally {
      setBusy(null);
    }
  }

  async function transfer(workspace: Workspace, member: WorkspaceMember) {
    const confirmation = window.prompt(
      `Transfer ownership of ${workspace.name} to ${member.name}? You will become an ADMIN.\n\nType ${workspace.slug} to confirm:`,
    );
    if (confirmation === null) return;
    setBusy(`member-${member.user_id}`);
    try {
      await transferWorkspaceOwnership(
        workspace.id,
        member.user_id,
        confirmation,
      );
      await onWorkspacesChanged();
    } catch (error) {
      onError(
        error instanceof Error ? error.message : "Failed to transfer ownership",
      );
    } finally {
      setBusy(null);
    }
  }

  async function copyInvite(invitation: WorkspaceInvitationCreated) {
    try {
      await navigator.clipboard.writeText(invitation.accept_url);
      setCopiedId(invitation.id);
      window.setTimeout(() => setCopiedId(null), 2000);
    } catch {
      onError(
        "Clipboard access was denied. Select the one-time invitation link and copy it manually.",
      );
    }
  }

  return (
    <section aria-labelledby="workspace-members-heading" className="space-y-4">
      <div>
        <h2
          id="workspace-members-heading"
          className="flex items-center gap-2 text-sm font-semibold"
        >
          <Users className="h-4 w-4" />
          Workspace access
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Owners can invite people, assign access, remove members, and transfer
          ownership. Invitation links are shown once; send them securely.
        </p>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Admin</strong> manages workspace
          operations, <strong className="text-foreground">Member</strong> can
          contribute, and <strong className="text-foreground">Viewer</strong>{" "}
          has read-only access. Ownership transfer requires the exact workspace
          slug.
        </p>
      </div>

      {ownerWorkspaces.map((workspace) => {
        const workspaceMembers = members[workspace.id] ?? [];
        const pendingInvitations = (invitations[workspace.id] ?? []).filter(
          (invitation) =>
            !invitation.accepted_at &&
            !invitation.revoked_at &&
            new Date(invitation.expires_at).getTime() > Date.now(),
        );
        const createdInvitation = created[workspace.id];
        const loadingWorkspace = loadingWorkspaceIds.includes(workspace.id);
        const loadError = loadErrors[workspace.id];
        return (
          <div
            key={workspace.id}
            aria-busy={loadingWorkspace}
            className="space-y-4 rounded-sm border border-border bg-card p-4"
          >
            <div>
              <p className="text-sm font-semibold">{workspace.name}</p>
              <p className="text-xs text-muted-foreground">
                <code>{workspace.slug}</code> · Owner controls
              </p>
            </div>

            {loadError && (
              <div
                role="alert"
                className="flex flex-wrap items-center gap-2 rounded-sm border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive-foreground"
              >
                <span className="min-w-0 flex-1">{loadError}</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    void loadWorkspace(workspace.id).catch(() => undefined)
                  }
                >
                  Retry
                </Button>
              </div>
            )}

            <div className="grid gap-2 sm:grid-cols-[1fr_8rem_auto]">
              <Input
                type="email"
                placeholder="teammate@example.com"
                value={emails[workspace.id] ?? ""}
                onChange={(event) =>
                  setEmails((current) => ({
                    ...current,
                    [workspace.id]: event.target.value,
                  }))
                }
                className="min-h-10 text-sm"
                aria-label={`Invite email for ${workspace.name}`}
              />
              <select
                value={roles[workspace.id] ?? "MEMBER"}
                onChange={(event) =>
                  setRoles((current) => ({
                    ...current,
                    [workspace.id]: event.target.value as HumanRole,
                  }))
                }
                className="min-h-10 rounded-sm border border-input bg-background px-2 text-xs"
                aria-label={`Invitation role for ${workspace.name}`}
              >
                <option value="ADMIN">Admin</option>
                <option value="MEMBER">Member</option>
                <option value="VIEWER">Viewer</option>
              </select>
              <Button
                size="sm"
                disabled={
                  busy === `invite-${workspace.id}` ||
                  !emails[workspace.id]?.trim()
                }
                onClick={() => invite(workspace)}
              >
                {busy === `invite-${workspace.id}` ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <UserPlus className="mr-1.5 h-3.5 w-3.5" />
                )}
                Invite
              </Button>
            </div>

            {createdInvitation && (
              <div
                role="status"
                aria-live="polite"
                className="rounded-sm border border-success/40 bg-success/10 p-3"
              >
                <p className="text-xs font-medium text-success">
                  Copy this invitation link now. It will not be shown again.
                </p>
                <div className="mt-2 flex gap-2">
                  <code className="min-w-0 flex-1 truncate rounded bg-background/60 px-2 py-1 text-xs">
                    {createdInvitation.accept_url}
                  </code>
                  <Button
                    size="icon"
                    variant="outline"
                    className="h-7 w-7"
                    onClick={() => void copyInvite(createdInvitation)}
                    aria-label="Copy invitation link"
                  >
                    {copiedId === createdInvitation.id ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
              </div>
            )}

            <div className="space-y-2">
              {workspaceMembers.map((member) => {
                const isOwner = member.role === "OWNER";
                const isCurrentUser = member.user_id === currentUserId;
                const isBusy = busy === `member-${member.user_id}`;
                return (
                  <div
                    key={member.user_id}
                    className="flex flex-col gap-2 rounded-sm border border-border p-3 sm:flex-row sm:items-center"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {member.name}
                        {isCurrentUser ? " (you)" : ""}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {member.email}
                      </p>
                    </div>
                    {isOwner ? (
                      <span className="flex items-center gap-1 text-xs font-medium">
                        <Shield className="h-3.5 w-3.5" />
                        Owner
                      </span>
                    ) : (
                      <>
                        <select
                          value={member.role}
                          disabled={isBusy}
                          onChange={(event) =>
                            changeRole(
                              workspace.id,
                              member,
                              event.target.value as HumanRole,
                            )
                          }
                          className="min-h-10 rounded-sm border border-input bg-background px-2 text-xs"
                          aria-label={`Role for ${member.name}`}
                        >
                          <option value="ADMIN">Admin</option>
                          <option value="MEMBER">Member</option>
                          <option value="VIEWER">Viewer</option>
                        </select>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isBusy}
                          onClick={() => transfer(workspace, member)}
                        >
                          Transfer ownership
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 text-muted-foreground hover:text-destructive-foreground"
                          disabled={isBusy}
                          onClick={() => remove(workspace.id, member)}
                          aria-label={`Remove ${member.name}`}
                        >
                          {isBusy ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      </>
                    )}
                  </div>
                );
              })}
            </div>

            {loadingWorkspace && workspaceMembers.length === 0 && (
              <div
                role="status"
                className="flex items-center gap-2 py-3 text-xs text-muted-foreground"
              >
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                Loading members and invitations…
              </div>
            )}

            {pendingInvitations.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Pending invitations
                </p>
                {pendingInvitations.map((invitation) => (
                  <div
                    key={invitation.id}
                    className="flex items-center gap-2 rounded-md border border-dashed border-border p-3"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium">
                        {invitation.email}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {invitation.role} · expires{" "}
                        {new Date(invitation.expires_at).toLocaleDateString()}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy === `invite-${invitation.id}`}
                      onClick={() => revoke(workspace.id, invitation.id)}
                    >
                      Revoke
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
