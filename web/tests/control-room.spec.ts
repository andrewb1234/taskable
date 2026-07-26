import { expect, request, test, type Page } from "@playwright/test";
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

test("Control Room composes project attention, continuity, and provenance", async ({
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
  await expect(page.getByText(project.description)).toBeVisible();
  await expect(page.getByText("Resolve release blocker")).toBeVisible();
  await expect(page.getByText("1 pending proposal")).toBeVisible();
  await expect(page.getByText("Verify the release train")).toBeVisible();
  await expect(
    page.getByText("Resume from the verified release evidence."),
  ).toBeVisible();

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
  await page
    .getByRole("button", { name: "Open workspace navigation" })
    .click();
  await page
    .getByRole("button", { name: project.name, exact: true })
    .click();

  await expect(
    page.getByRole("heading", { name: "Control Room" }),
  ).toBeVisible();
  await api.post(`subprojects/${subproject.id}/tickets`, {
    data: {
      title: "New human review",
      status: "REVIEW",
      assignee: "HUMAN",
    },
  });
  await expect(page.getByText("New human review")).toBeVisible({
    timeout: 1_000,
  });

  const dimensions = (await page.evaluate(
    `({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    })`,
  )) as { scrollWidth: number; clientWidth: number };
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
});
