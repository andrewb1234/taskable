import { expect, request, test, type Page } from "./uiFixture";
import { E2E_API_KEY } from "./authFixture";

const API_URL = "http://127.0.0.1:8000/api/v1/";

async function authenticateBrowser(page: Page) {
  const response = await page.request.post("/api/v1/auth/local-session", {
    data: { api_key: E2E_API_KEY },
    headers: { Origin: "http://127.0.0.1:5173" },
  });
  expect(response.ok()).toBeTruthy();
}

function authenticatedApi() {
  return request.newContext({
    baseURL: API_URL,
    extraHTTPHeaders: { Authorization: `Bearer ${E2E_API_KEY}` },
  });
}

test("Control Room prioritizes attention, work in flight, and recovery", async ({
  page,
}) => {
  await authenticateBrowser(page);
  const api = await authenticatedApi();
  const suffix = Date.now();
  const project = await (
    await api.post("projects", {
      data: {
        name: `Control Room ${suffix}`,
        description: "A project brief grounded in existing project state.",
      },
    })
  ).json();
  const subproject = await (
    await api.post(`projects/${project.id}/subprojects`, {
      data: {
        name: `Release train ${suffix}`,
        context_brief: "Ship the verified project milestone.",
      },
    })
  ).json();
  const blocked = await (
    await api.post(`subprojects/${subproject.id}/tickets`, {
      data: {
        title: "Resolve release blocker",
        status: "BLOCKED",
        assignee: "HUMAN",
      },
    })
  ).json();
  await api.post(`subprojects/${subproject.id}/tickets`, {
    data: {
      title: "Review verified artifact",
      status: "REVIEW",
      assignee: "AGENT",
    },
  });
  await api.post(`subprojects/${subproject.id}/tickets`, {
    data: {
      title: "Implement the release candidate",
      status: "IN_PROGRESS",
      assignee: "AGENT",
    },
  });
  const node = await (
    await api.post(`projects/${project.id}/knowledge`, {
      data: {
        title: "Release evidence",
        node_type: "SUMMARY",
        content: "Verified project evidence.",
      },
    })
  ).json();
  await api.post(`knowledge/${node.id}/proposals`, {
    data: {
      proposed_changes: { content: "Human review remains required." },
      rationale: "Keep the evidence current.",
    },
  });
  const session = await (
    await api.post(`projects/${project.id}/sessions`, {
      data: {
        intent: "Verify the release train",
        loaded_node_ids: [node.id],
      },
    })
  ).json();
  await api.patch(`agent/sessions/${session.id}`, {
    data: {
      status: "INTERRUPTED",
      handoff_note: "Resume from the verified release evidence.",
    },
  });

  await page.goto("/app");
  await page
    .getByRole("button", { name: project.name, exact: true })
    .click();

  await expect(
    page.getByRole("heading", { name: "Control Room" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /^Control Room Project state/ }),
  ).toHaveAttribute("aria-current", "page");
  await expect(
    page
      .locator('[aria-labelledby="control-room-title"]')
      .getByText(project.description, { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Needs your attention")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Work in flight", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Resolve release blocker")).toBeVisible();
  await expect(page.getByText("Implement the release candidate")).toBeVisible();
  await expect(page.getByText("1 pending proposal")).toBeVisible();
  await expect(page.getByText("Verify the release train")).toBeVisible();
  await expect(
    page.getByText("Resume from the verified release evidence."),
  ).toBeVisible();
  await expect(page.getByText("Agent continuity")).toHaveCount(0);
  await expect(page.getByText("Bound outcome")).toHaveCount(0);

  await page.getByText("Resolve release blocker").click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByText(`#${blocked.id}`, { exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");

  await page
    .getByRole("region", { name: "Subproject map" })
    .getByRole("button", { name: new RegExp(subproject.name) })
    .click();
  await expect(
    page.getByRole("heading", { name: subproject.name }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /^Kanban Execute/ }),
  ).toHaveAttribute("aria-current", "page");

  await page
    .getByRole("button", { name: /^Control Room Project state/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "Control Room" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /^Control Room Project state/ }),
  ).toHaveAttribute("aria-current", "page");
  await page
    .getByRole("button", { name: /^Kanban Execute/ })
    .click();
  await expect(
    page.getByRole("heading", { name: subproject.name }),
  ).toBeVisible();
});

test("Control Room updates attention from SSE and stays contained at 360px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.addInitScript(`
    (() => {
      const NativeEventSource = window.EventSource;
      class ObservableEventSource extends NativeEventSource {
        constructor(url, eventSourceInitDict) {
          super(url, eventSourceInitDict);
          this.addEventListener(
            "ready",
            () => {
              window.__mouvadahSseReady = true;
            },
            { once: true },
          );
          this.addEventListener("message", (event) => {
            try {
              const payload = JSON.parse(event.data);
              if (payload.entity === "ticket") {
                window.__mouvadahTicketEvents =
                  (window.__mouvadahTicketEvents || 0) + 1;
              }
            } catch {
              // The application owns payload validation.
            }
          });
        }
      }
      Object.defineProperty(window, "EventSource", {
        configurable: true,
        value: ObservableEventSource,
      });
    })();
  `);
  await authenticateBrowser(page);
  const api = await authenticatedApi();
  const suffix = Date.now();
  const project = await (
    await api.post("projects", {
      data: { name: `Realtime control ${suffix}` },
    })
  ).json();
  const subproject = await (
    await api.post(`projects/${project.id}/subprojects`, {
      data: { name: `Mobile project ${suffix}` },
    })
  ).json();

  await page.goto("/app");
  await expect
    .poll(() => page.evaluate("window.__mouvadahSseReady === true"))
    .toBe(true);
  await page
    .getByRole("button", { name: "Open workspace navigation" })
    .click();
  await page
    .getByRole("button", { name: project.name, exact: true })
    .click();

  await expect(
    page.getByRole("heading", { name: "Control Room" }),
  ).toBeVisible();
  // The project resources and EventSource settle independently. The stream's
  // ready event is awaited above so the mutation cannot race subscription;
  // these assertions confirm both ticket and subproject state before
  // publishing because ticket invalidation is scoped through that map.
  await expect(page.getByText("Nothing needs attention")).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Subproject map" })
      .getByRole("button", { name: new RegExp(subproject.name) }),
  ).toBeVisible();
  await expect(page.getByText("Refreshing")).toHaveCount(0);
  const ticketEventsBeforeMutation = (await page.evaluate(
    "window.__mouvadahTicketEvents || 0",
  )) as number;
  let summaryRequestsAfterMutation = 0;
  page.on("request", (request) => {
    if (
      request.method() === "GET" &&
      request.url().includes(`/projects/${project.id}/control-room`)
    ) {
      summaryRequestsAfterMutation += 1;
    }
  });
  await api.post(`subprojects/${subproject.id}/tickets`, {
    data: {
      title: "New human review",
      status: "REVIEW",
      assignee: "HUMAN",
    },
  });
  await expect
    .poll(() => page.evaluate("window.__mouvadahTicketEvents || 0"))
    .toBe(ticketEventsBeforeMutation + 1);
  await expect(page.getByText("New human review")).toBeVisible();
  await expect
    .poll(() => summaryRequestsAfterMutation)
    .toBe(1);
  await page.waitForTimeout(200);
  expect(summaryRequestsAfterMutation).toBe(1);

  const dimensions = (await page.evaluate(
    `({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    })`,
  )) as { scrollWidth: number; clientWidth: number };
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);

  const statusSummary = await page
    .locator('dl[aria-label="Ticket status summary"] > div')
    .filter({ hasText: "In Progress" })
    .boundingBox();
  expect(statusSummary).not.toBeNull();
  expect(statusSummary!.x).toBeGreaterThanOrEqual(0);
  expect(statusSummary!.x + statusSummary!.width).toBeLessThanOrEqual(360);
});

test("Control Room performs a trailing refresh for overlapping agent updates", async ({
  page,
}) => {
  await page.addInitScript(`
    (() => {
      const NativeEventSource = window.EventSource;
      class ObservableEventSource extends NativeEventSource {
        constructor(url, eventSourceInitDict) {
          super(url, eventSourceInitDict);
          this.addEventListener("ready", () => {
            window.__mouvadahSseReady = true;
          });
          this.addEventListener("message", (event) => {
            try {
              const payload = JSON.parse(event.data);
              if (payload.entity === "ticket") {
                window.__mouvadahTicketEvents =
                  (window.__mouvadahTicketEvents || 0) + 1;
              }
            } catch {
              // The application owns payload validation; this observer only
              // provides a deterministic synchronization point for the test.
            }
          });
        }
      }
      Object.defineProperty(window, "EventSource", {
        configurable: true,
        value: ObservableEventSource,
      });
    })();
  `);
  await authenticateBrowser(page);
  const api = await authenticatedApi();
  const suffix = Date.now();
  const project = await (
    await api.post("projects", {
      data: { name: `Overlapping refresh ${suffix}` },
    })
  ).json();
  const subproject = await (
    await api.post(`projects/${project.id}/subprojects`, {
      data: { name: `Refresh queue ${suffix}` },
    })
  ).json();

  let holdNextSummary = false;
  let summaryRequests = 0;
  let releaseHeldResponse!: () => void;
  let markResponseHeld!: () => void;
  const heldResponseReleased = new Promise<void>((resolve) => {
    releaseHeldResponse = resolve;
  });
  const responseHeld = new Promise<void>((resolve) => {
    markResponseHeld = resolve;
  });
  await page.route(
    `**/api/v1/projects/${project.id}/control-room`,
    async (route) => {
      summaryRequests += 1;
      if (!holdNextSummary) {
        await route.continue();
        return;
      }
      holdNextSummary = false;
      const response = await route.fetch();
      markResponseHeld();
      await heldResponseReleased;
      await route.fulfill({ response });
    },
  );

  await page.goto("/app");
  await expect
    .poll(() => page.evaluate("window.__mouvadahSseReady === true"))
    .toBe(true);
  await page
    .getByRole("button", { name: project.name, exact: true })
    .click();
  await expect(page.getByText("Nothing needs attention")).toBeVisible();
  const requestsBeforeMutations = summaryRequests;
  const eventsBeforeMutations = (await page.evaluate(
    "window.__mouvadahTicketEvents || 0",
  )) as number;

  holdNextSummary = true;
  const ticket = await (
    await api.post(`subprojects/${subproject.id}/tickets`, {
      data: {
        title: "Overlapping agent update",
        status: "REVIEW",
        assignee: "AGENT",
      },
    })
  ).json();
  await responseHeld;

  await api.patch(`tickets/${ticket.id}`, {
    data: { status: "DONE" },
  });
  await expect
    .poll(() =>
      page.evaluate("window.__mouvadahTicketEvents || 0"),
    )
    .toBe(eventsBeforeMutations + 2);
  releaseHeldResponse();

  await expect(page.getByText("Nothing needs attention")).toBeVisible();
  await expect
    .poll(() => summaryRequests - requestsBeforeMutations)
    .toBe(2);
  await expect(
    page
      .locator('dl[aria-label="Ticket status summary"] > div')
      .filter({ hasText: "Done" }),
  ).toContainText("1");
});

test("agent events invalidate warm Control Room data while its view is unmounted", async ({
  page,
}) => {
  await page.addInitScript(`
    (() => {
      const NativeEventSource = window.EventSource;
      class ObservableEventSource extends NativeEventSource {
        constructor(url, eventSourceInitDict) {
          super(url, eventSourceInitDict);
          this.addEventListener("ready", () => {
            window.__mouvadahSseReady = true;
          });
          this.addEventListener("message", (event) => {
            try {
              const payload = JSON.parse(event.data);
              const key = "__mouvadahEvent_" + payload.entity;
              window[key] = (window[key] || 0) + 1;
            } catch {
              // The application owns payload validation.
            }
          });
        }
      }
      Object.defineProperty(window, "EventSource", {
        configurable: true,
        value: ObservableEventSource,
      });
    })();
  `);
  await authenticateBrowser(page);
  const api = await authenticatedApi();
  const suffix = Date.now();
  const firstProject = await (
    await api.post("projects", {
      data: { name: `Warm cache target ${suffix}` },
    })
  ).json();
  const firstSubproject = await (
    await api.post(`projects/${firstProject.id}/subprojects`, {
      data: { name: `Agent-owned work ${suffix}` },
    })
  ).json();
  const secondProject = await (
    await api.post("projects", {
      data: { name: `Current view ${suffix}` },
    })
  ).json();

  await page.goto("/app");
  await expect
    .poll(() => page.evaluate("window.__mouvadahSseReady === true"))
    .toBe(true);
  await page
    .getByRole("button", { name: firstProject.name, exact: true })
    .click();
  await expect(page.getByText("Nothing needs attention")).toBeVisible();
  await expect(page.getByText("Refreshing")).toHaveCount(0);

  await page
    .getByRole("button", { name: secondProject.name, exact: true })
    .click();
  await expect(
    page
      .locator('[aria-labelledby="control-room-title"]')
      .getByText(secondProject.name, { exact: true }),
  ).toBeVisible();

  const ticketEventsBefore = (await page.evaluate(
    "window.__mouvadahEvent_ticket || 0",
  )) as number;
  const knowledgeEventsBefore = (await page.evaluate(
    "window.__mouvadahEvent_knowledge_node || 0",
  )) as number;
  await api.post(`subprojects/${firstSubproject.id}/tickets`, {
    data: {
      title: "Agent update while unmounted",
      status: "REVIEW",
      assignee: "AGENT",
    },
  });
  await api.post(`projects/${secondProject.id}/knowledge`, {
    data: {
      title: "Later unrelated event",
      content: "Replaces the latest mounted-view event.",
    },
  });
  await expect
    .poll(() => page.evaluate("window.__mouvadahEvent_ticket || 0"))
    .toBe(ticketEventsBefore + 1);
  await expect
    .poll(() => page.evaluate("window.__mouvadahEvent_knowledge_node || 0"))
    .toBe(knowledgeEventsBefore + 1);

  await page
    .getByRole("button", { name: firstProject.name, exact: true })
    .click();
  await expect(page.getByText("Agent update while unmounted")).toBeVisible();
});
