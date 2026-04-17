/**
 * Thin typed fetch wrapper for the Taskable API.
 *
 * The UI runs unauthenticated on localhost per the architecture decision
 * logged in `learnings.md`. All mutations go through these helpers so we have
 * a single seam for retry/logging/auth tweaks later.
 */

import type {
  Comment,
  Project,
  Subproject,
  SubprojectDetail,
  Ticket,
  TicketAssignee,
  TicketDetail,
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
