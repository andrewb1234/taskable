/**
 * Thin typed fetch wrapper for the mouvadah API.
 *
 * The UI runs unauthenticated on localhost per the architecture decision
 * logged in `learnings.md`. All mutations go through these helpers so we have
 * a single seam for retry/logging/auth tweaks later.
 */

import type {
  AgentSession,
  ApiKey,
  ApiKeyCreated,
  BlockedByCategory,
  Comment,
  ContextTrail,
  KnowledgeNode,
  KnowledgeNodeStatus,
  KnowledgeNodeType,
  KnowledgeProposal,
  Project,
  Subproject,
  SubprojectDetail,
  Ticket,
  TicketAssignee,
  TicketDetail,
  TicketRef,
  TicketStatus,
  ActorRole,
} from "@/types";

const API_BASE =
  (import.meta as unknown as { env: Record<string, string> }).env
    .VITE_API_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body?.detail) message = body.detail;
    } catch {
      /* ignore parse failure */
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ---- Projects -----------------------------------------------------------

export const listProjects = () => request<Project[]>("/projects");
export const getProject = (id: number) => request<Project>(`/projects/${id}`);
export const createProject = (payload: {
  name: string;
  description?: string;
}) =>
  request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const deleteProject = (id: number) =>
  request<void>(`/projects/${id}`, { method: "DELETE" });

// ---- Subprojects --------------------------------------------------------

export const listSubprojects = (projectId: number) =>
  request<Subproject[]>(`/projects/${projectId}/subprojects`);

export const getSubproject = (id: number) =>
  request<SubprojectDetail>(`/subprojects/${id}`);

export const createSubproject = (
  projectId: number,
  payload: { name: string; context_brief?: string },
) =>
  request<Subproject>(`/projects/${projectId}/subprojects`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const updateSubproject = (
  id: number,
  payload: Partial<Pick<Subproject, "name" | "context_brief" | "status">>,
) =>
  request<Subproject>(`/subprojects/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const deleteSubproject = (id: number) =>
  request<void>(`/subprojects/${id}`, { method: "DELETE" });

// ---- Tickets ------------------------------------------------------------

export const getTicket = (id: number) =>
  request<TicketDetail>(`/tickets/${id}`);

export const createTicket = (
  subprojectId: number,
  payload: {
    title: string;
    description?: string;
    assignee?: TicketAssignee;
    status?: TicketStatus;
  },
) =>
  request<Ticket>(`/subprojects/${subprojectId}/tickets`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const updateTicket = (
  id: number,
  payload: Partial<{
    title: string;
    description: string | null;
    status: TicketStatus;
    assignee: TicketAssignee;
    mr_link: string | null;
    blocked_by: BlockedByCategory | null;
    blocked_reason: string | null;
    source_refs: string[];
  }>,
) =>
  request<Ticket>(`/tickets/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const linkTicketMR = (id: number, url: string) =>
  request<Ticket>(`/tickets/${id}/mr`, {
    method: "POST",
    body: JSON.stringify({ url }),
  });

export const deleteTicket = (id: number) =>
  request<void>(`/tickets/${id}`, { method: "DELETE" });

// ---- Knowledge nodes ----------------------------------------------------

export const listKnowledgeNodes = (projectId: number) =>
  request<KnowledgeNode[]>(`/projects/${projectId}/knowledge`);

export const getContextTrail = (
  projectId: number,
  query: string,
  limit = 6,
) =>
  request<ContextTrail>(
    `/projects/${projectId}/knowledge/context-trail?query=${encodeURIComponent(query)}&limit=${limit}`,
  );

export const getKnowledgeNode = (id: number) =>
  request<KnowledgeNode>(`/knowledge/${id}`);

export const createKnowledgeNode = (
  projectId: number,
  payload: {
    title: string;
    node_type?: KnowledgeNodeType;
    content?: string;
    parent_id?: number | null;
    source_refs?: string[];
  },
) =>
  request<KnowledgeNode>(`/projects/${projectId}/knowledge`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const listKnowledgeNodesAll = (projectId: number) =>
  request<KnowledgeNode[]>(`/projects/${projectId}/knowledge?include_stale=true`);

export const updateKnowledgeNode = (
  id: number,
  payload: Partial<{
    title: string;
    node_type: KnowledgeNodeType;
    status: KnowledgeNodeStatus;
    superseded_by: number | null;
    content: string;
    parent_id: number | null;
    source_refs: string[];
  }>,
) =>
  request<KnowledgeNode>(`/knowledge/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

export const deleteKnowledgeNode = (id: number) =>
  request<void>(`/knowledge/${id}`, { method: "DELETE" });

export const getTicketsForNode = (nodeId: number) =>
  request<TicketRef[]>(`/tickets/knowledge/${nodeId}/tickets`);

// ---- Knowledge proposals ------------------------------------------------

export const createProposal = (
  nodeId: number,
  payload: { proposed_changes: Record<string, unknown>; rationale?: string },
) =>
  request<KnowledgeProposal>(`/knowledge/${nodeId}/proposals`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const listProposalsForNode = (nodeId: number) =>
  request<KnowledgeProposal[]>(`/knowledge/${nodeId}/proposals`);

export const listProjectProposals = (projectId: number) =>
  request<KnowledgeProposal[]>(`/projects/${projectId}/knowledge/proposals`);

export const reviewProposal = (
  proposalId: number,
  action: "accept" | "reject",
  reviewedBy = "HUMAN",
) =>
  request<KnowledgeProposal>(`/knowledge/proposals/${proposalId}`, {
    method: "PATCH",
    body: JSON.stringify({ action, reviewed_by: reviewedBy }),
  });

// ---- Agent sessions -------------------------------------------------------

export const startSession = (
  projectId: number,
  payload: { intent: string; loaded_node_ids?: number[] },
) =>
  request<AgentSession>(`/projects/${projectId}/sessions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const listSessions = (projectId: number) =>
  request<AgentSession[]>(`/projects/${projectId}/sessions`);

export const updateSession = (
  sessionId: number,
  payload: Partial<{ handoff_note: string; status: string; loaded_node_ids: number[] }>,
) =>
  request<AgentSession>(`/agent/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });

// ---- Comments -----------------------------------------------------------

export const createComment = (
  ticketId: number,
  payload: { author: ActorRole; content: string },
) =>
  request<Comment>(`/tickets/${ticketId}/comments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const apiBase = API_BASE;

// ---- Auth ----------------------------------------------------------------

export interface AuthUser {
  id: number;
  email: string;
  name: string;
  avatar_url: string | null;
}

export const getMe = () => request<AuthUser>("/auth/me");

export const logout = () =>
  request<void>("/auth/logout", { method: "POST" });

export const getLoginUrl = () => `${API_BASE}/auth/login`;

// ---- API Keys ------------------------------------------------------------

export const listApiKeys = () => request<ApiKey[]>("/apikeys");

export const createApiKey = (payload: {
  name: string;
  expires_in_days?: number;
}) =>
  request<ApiKeyCreated>("/apikeys", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const revokeApiKey = (id: number) =>
  request<void>(`/apikeys/${id}`, { method: "DELETE" });
