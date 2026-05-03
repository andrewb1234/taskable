/**
 * Thin typed fetch wrapper for the Taskable API.
 *
 * The UI runs unauthenticated on localhost per the architecture decision
 * logged in `learnings.md`. All mutations go through these helpers so we have
 * a single seam for retry/logging/auth tweaks later.
 */
const API_BASE = import.meta.env
    .VITE_API_URL ?? "/api/v1";
export class ApiError extends Error {
    status;
    constructor(status, message) {
        super(message);
        this.status = status;
    }
}
async function request(path, init = {}) {
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
            const body = (await response.json());
            if (body?.detail)
                message = body.detail;
        }
        catch {
            /* ignore parse failure */
        }
        throw new ApiError(response.status, message);
    }
    if (response.status === 204)
        return undefined;
    return (await response.json());
}
// ---- Projects -----------------------------------------------------------
export const listProjects = () => request("/projects");
export const getProject = (id) => request(`/projects/${id}`);
export const createProject = (payload) => request("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
});
export const deleteProject = (id) => request(`/projects/${id}`, { method: "DELETE" });
// ---- Subprojects --------------------------------------------------------
export const listSubprojects = (projectId) => request(`/projects/${projectId}/subprojects`);
export const getSubproject = (id) => request(`/subprojects/${id}`);
export const createSubproject = (projectId, payload) => request(`/projects/${projectId}/subprojects`, {
    method: "POST",
    body: JSON.stringify(payload),
});
export const updateSubproject = (id, payload) => request(`/subprojects/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
});
export const deleteSubproject = (id) => request(`/subprojects/${id}`, { method: "DELETE" });
// ---- Tickets ------------------------------------------------------------
export const getTicket = (id) => request(`/tickets/${id}`);
export const createTicket = (subprojectId, payload) => request(`/subprojects/${subprojectId}/tickets`, {
    method: "POST",
    body: JSON.stringify(payload),
});
export const updateTicket = (id, payload) => request(`/tickets/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
});
export const linkTicketMR = (id, url) => request(`/tickets/${id}/mr`, {
    method: "POST",
    body: JSON.stringify({ url }),
});
export const deleteTicket = (id) => request(`/tickets/${id}`, { method: "DELETE" });
// ---- Knowledge nodes ----------------------------------------------------
export const listKnowledgeNodes = (projectId) => request(`/projects/${projectId}/knowledge`);
export const getKnowledgeNode = (id) => request(`/knowledge/${id}`);
export const createKnowledgeNode = (projectId, payload) => request(`/projects/${projectId}/knowledge`, {
    method: "POST",
    body: JSON.stringify(payload),
});
export const updateKnowledgeNode = (id, payload) => request(`/knowledge/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
});
export const deleteKnowledgeNode = (id) => request(`/knowledge/${id}`, { method: "DELETE" });
// ---- Comments -----------------------------------------------------------
export const createComment = (ticketId, payload) => request(`/tickets/${ticketId}/comments`, {
    method: "POST",
    body: JSON.stringify(payload),
});
export const apiBase = API_BASE;
