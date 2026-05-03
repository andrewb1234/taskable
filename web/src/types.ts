/**
 * TypeScript mirrors of the Pydantic schemas in `api/schemas.py`.
 * Keep these in lock-step with the backend to preserve type safety.
 */

export type SubprojectStatus = "PLANNING" | "ACTIVE" | "COMPLETED";

export type TicketStatus =
  | "TODO"
  | "IN_PROGRESS"
  | "BLOCKED"
  | "REVIEW"
  | "DONE";

export type TicketAssignee = "HUMAN" | "AGENT" | "UNASSIGNED";

export type ActorRole = "HUMAN" | "AGENT";

export type AuditAction = "STATUS_UPDATE" | "CONTENT_UPDATE" | "MR_LINKED";

export type SSEAction =
  | "PROJECT_CREATED"
  | "PROJECT_DELETED"
  | "SUBPROJECT_CREATED"
  | "SUBPROJECT_UPDATED"
  | "SUBPROJECT_DELETED"
  | "TICKET_CREATED"
  | "TICKET_UPDATED"
  | "TICKET_DELETED"
  | "COMMENT_CREATED"
  | "MR_LINKED"
  | "KNOWLEDGE_NODE_CREATED"
  | "KNOWLEDGE_NODE_UPDATED"
  | "KNOWLEDGE_NODE_DELETED";

export type KnowledgeNodeType = "RAW" | "SUMMARY" | "PRD" | "TDD";

export interface Project {
  id: number;
  name: string;
  description?: string | null;
  created_at: string;
}

export interface Subproject {
  id: number;
  project_id: number;
  name: string;
  context_brief: string;
  status: SubprojectStatus;
}

export interface Ticket {
  id: number;
  subproject_id: number;
  title: string;
  description?: string | null;
  status: TicketStatus;
  assignee: TicketAssignee;
  mr_link?: string | null;
}

export interface Comment {
  id: number;
  ticket_id: number;
  author: ActorRole;
  content: string;
  timestamp: string;
}

export interface AuditLog {
  id: number;
  ticket_id: number;
  action: AuditAction;
  actor: ActorRole;
  timestamp: string;
}

export interface SubprojectDetail extends Subproject {
  tickets: Ticket[];
}

export interface TicketDetail extends Ticket {
  comments: Comment[];
  audit_logs: AuditLog[];
}

export interface SSEPayload {
  action: SSEAction;
  entity: string;
  entity_id: number;
  parent_id: number | null;
}

export const TICKET_STATUSES: TicketStatus[] = [
  "TODO",
  "IN_PROGRESS",
  "BLOCKED",
  "REVIEW",
  "DONE",
];

export const TICKET_STATUS_LABELS: Record<TicketStatus, string> = {
  TODO: "Todo",
  IN_PROGRESS: "In Progress",
  BLOCKED: "Blocked",
  REVIEW: "Review",
  DONE: "Done",
};

export const ASSIGNEE_LABELS: Record<TicketAssignee, string> = {
  HUMAN: "Human",
  AGENT: "Agent",
  UNASSIGNED: "Unassigned",
};

export interface KnowledgeNode {
  id: number;
  project_id: number;
  parent_id: number | null;
  title: string;
  node_type: KnowledgeNodeType;
  content: string;
  source_refs: string[];
  created_by: ActorRole;
  created_at: string;
  updated_at: string;
}

export interface ContextTrailSegment {
  id: number;
  title: string;
  node_type: KnowledgeNodeType;
}

export interface ContextTrailChildHint extends ContextTrailSegment {
  content_preview: string;
  source_refs: string[];
}

export interface ContextTrailItem {
  id: number;
  title: string;
  node_type: KnowledgeNodeType;
  parent_id: number | null;
  path: ContextTrailSegment[];
  score: number;
  matched_terms: string[];
  reason: string;
  content_preview: string;
  source_refs: string[];
  child_count: number;
  children: ContextTrailChildHint[];
}

export interface ContextTrail {
  project_id: number;
  project_name: string;
  query: string;
  load_order: ContextTrailSegment[];
  items: ContextTrailItem[];
}

export const KNOWLEDGE_NODE_TYPES: KnowledgeNodeType[] = [
  "RAW",
  "SUMMARY",
  "PRD",
  "TDD",
];

export const KNOWLEDGE_NODE_TYPE_LABELS: Record<KnowledgeNodeType, string> = {
  RAW: "Raw",
  SUMMARY: "Summary",
  PRD: "PRD",
  TDD: "TDD",
};
