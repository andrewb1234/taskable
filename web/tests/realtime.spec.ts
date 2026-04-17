import { test, expect, request } from "@playwright/test";

/**
 * Ghost Agent SSE Realtime Spec.
 *
 * Proves the real-time contract described in docs/client_server.md:
 *
 *   "When an agent updates a ticket via REST, every connected UI must
 *    reflect the change within one second without a page reload."
 *
 * Test shape:
 *   1. Open the Taskable UI
 *   2. Seed a fresh project → subproject → ticket via the REST API
 *   3. Click the sidebar entry so the Kanban board is loaded
 *   4. Assert the ticket is in the TODO column
 *   5. Issue a PATCH /tickets/{id} directly to the API (ghost agent)
 *   6. Assert the DOM reflects IN_PROGRESS within 1000ms — without reload
 */

// Trailing slash matters: Playwright resolves request paths via WHATWG URL
// rules, so a leading-slash path on a baseURL without a trailing slash wipes
// the existing path segment. Keep the trailing slash and use relative paths.
const API_URL = "http://127.0.0.1:8000/api/v1/";
const PROJECT_NAME = `Realtime Test ${Date.now()}`;

test.describe("SSE realtime contract", () => {
  test("ticket status PATCHed via API appears in the UI within 1s", async ({
    page,
  }) => {
    const api = await request.newContext({ baseURL: API_URL });

    const projectResp = await api.post("projects", {
      data: { name: PROJECT_NAME, description: "Playwright realtime test" },
    });
    if (!projectResp.ok()) {
      throw new Error(
        `project POST failed: ${projectResp.status()} ${await projectResp.text()}`,
      );
    }
    const project = await projectResp.json();

    const subprojectResp = await api.post(
      `projects/${project.id}/subprojects`,
      {
        data: {
          name: "Realtime subproject",
          context_brief: "Seeded by the realtime spec",
        },
      },
    );
    expect(subprojectResp.ok()).toBeTruthy();
    const subproject = await subprojectResp.json();

    const ticketResp = await api.post(
      `subprojects/${subproject.id}/tickets`,
      {
        data: {
          title: "Ghost agent target",
          description: "This card should hop from TODO → IN_PROGRESS via SSE.",
          assignee: "HUMAN",
        },
      },
    );
    expect(ticketResp.ok()).toBeTruthy();
    const ticket = await ticketResp.json();

    // Load the UI and pin the freshly-seeded subproject.
    await page.goto("/");

    // The sidebar auto-selects the first project on load; our test project is
    // likely to come later because the auto-select is a first-wins race. So
    // instead of relying on that, click the project row explicitly.
    const projectButton = page
      .locator("button", { hasText: PROJECT_NAME })
      .first();
    await expect(projectButton).toBeVisible();
    await projectButton.click();

    const subprojectButton = page
      .locator("button", { hasText: "Realtime subproject" })
      .first();
    await expect(subprojectButton).toBeVisible();
    await subprojectButton.click();

    // Wait for the ticket card to render in the TODO column.
    const ticketCard = page.getByTestId(`ticket-${ticket.id}`);
    await expect(ticketCard).toBeVisible();
    await expect(ticketCard).toHaveAttribute("data-status", "TODO");

    // The ticket should live under the TODO column specifically.
    const todoColumn = page.getByTestId("column-TODO");
    await expect(todoColumn.getByTestId(`ticket-${ticket.id}`)).toBeVisible();

    // Arm a timer, then ghost-agent the PATCH.
    const patchStart = Date.now();
    const patchResp = await api.patch(`tickets/${ticket.id}`, {
      data: { status: "IN_PROGRESS", assignee: "AGENT" },
    });
    expect(patchResp.ok()).toBeTruthy();

    // Key assertion: within 1000ms the card must have moved to IN_PROGRESS
    // and be inside the IN_PROGRESS column — with no page reload.
    const inProgressColumn = page.getByTestId("column-IN_PROGRESS");
    await expect(inProgressColumn.getByTestId(`ticket-${ticket.id}`))
      .toBeVisible({ timeout: 1000 });
    await expect(page.getByTestId(`ticket-${ticket.id}`))
      .toHaveAttribute("data-status", "IN_PROGRESS", { timeout: 1000 });
    const totalMs = Date.now() - patchStart;
    test.info().annotations.push({
      type: "sse-latency",
      description: `${totalMs}ms from PATCH to DOM update`,
    });

    // And the TODO column should no longer contain the card.
    await expect(todoColumn.getByTestId(`ticket-${ticket.id}`))
      .toHaveCount(0);
  });

  test("handles a fast burst of agent updates without dropping events", async ({
    page,
  }) => {
    const api = await request.newContext({ baseURL: API_URL });

    const project = await (
      await api.post("projects", {
        data: { name: `Burst Test ${Date.now()}` },
      })
    ).json();
    const subproject = await (
      await api.post(`projects/${project.id}/subprojects`, {
        data: { name: "Burst sub", context_brief: "." },
      })
    ).json();
    const ticket = await (
      await api.post(`subprojects/${subproject.id}/tickets`, {
        data: { title: "Bouncing ticket", assignee: "HUMAN" },
      })
    ).json();

    await page.goto("/");
    await page
      .locator("button", { hasText: project.name })
      .first()
      .click();
    await page
      .locator("button", { hasText: subproject.name })
      .first()
      .click();
    await expect(page.getByTestId(`ticket-${ticket.id}`)).toBeVisible();

    // Fire a rapid sequence: TODO → IN_PROGRESS → REVIEW → DONE. Only the
    // terminal state should matter; the UI must eventually settle on DONE.
    const statuses = ["IN_PROGRESS", "REVIEW", "DONE"] as const;
    for (const status of statuses) {
      await api.patch(`tickets/${ticket.id}`, { data: { status } });
    }

    await expect(page.getByTestId("column-DONE").getByTestId(`ticket-${ticket.id}`))
      .toBeVisible({ timeout: 2000 });
    await expect(page.getByTestId(`ticket-${ticket.id}`))
      .toHaveAttribute("data-status", "DONE", { timeout: 2000 });
  });
});
