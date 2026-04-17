/**
 * TypeScript mirrors of the Pydantic schemas in `api/schemas.py`.
 * Keep these in lock-step with the backend to preserve type safety.
 */
export const TICKET_STATUSES = [
    "TODO",
    "IN_PROGRESS",
    "BLOCKED",
    "REVIEW",
    "DONE",
];
export const TICKET_STATUS_LABELS = {
    TODO: "Todo",
    IN_PROGRESS: "In Progress",
    BLOCKED: "Blocked",
    REVIEW: "Review",
    DONE: "Done",
};
export const ASSIGNEE_LABELS = {
    HUMAN: "Human",
    AGENT: "Agent",
    UNASSIGNED: "Unassigned",
};
