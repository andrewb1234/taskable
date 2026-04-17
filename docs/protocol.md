# Progression & Checkpoint Protocol

## Objective
Establish a deterministic, autonomous loop for implementing features, tracking state, and preserving architectural decisions across sessions.

## The Implementation Loop
1. **Analyze Phase:** Ingest relevant specification markdown files before mutating code.
2. **Execution Phase:** Implement one isolated component or API endpoint at a time. 
3. **Checkpoint Phase:** Commit functional milestones immediately to Git. Do not bundle multiple distinct architectural changes into a single commit.
   * Commit Format: `feat(scope): brief description` or `fix(scope): description`.

## Knowledge Preservation (`learnings.md`)
You MUST maintain a `learnings.md` file in the project root. Append to this file when:
* Resolving a complex bug, race condition, or framework limitation.
* Making an architectural divergence from the original specifications.
* Discovering a specific workaround for local Docker or MCP stdio networking.

### Required Entry Format:
* **Date:** [ISO Timestamp]
* **Context:** [What operation was being attempted]
* **Friction:** [The specific error, block, or hallucination]
* **Resolution:** [The technical solution and reasoning]

## Rule of Continuity
You must read `learnings.md` at the initialization of every new session to prevent regressing or repeating past errors.
