import {
  expect,
  request,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
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

interface WorkbenchFixture {
  api: APIRequestContext;
  project: { id: number; name: string };
  subproject: { id: number; name: string };
  dependency: { id: number; title: string };
  candidate: { id: number; title: string };
  target: { id: number; title: string };
  claimed: { id: number; title: string };
}

async function seedWorkbench(): Promise<WorkbenchFixture> {
  const api = await authenticatedApi();
  const suffix = Date.now();
  const project = await (
    await api.post("projects", {
      data: {
        name: `Execution workbench ${suffix}`,
        description: "Isolated Playwright workbench state",
      },
    })
  ).json();
  const subproject = await (
    await api.post(`projects/${project.id}/subprojects`, {
      data: {
        name: `Delivery lane ${suffix}`,
        context_brief:
          "Ship a verified human-agent handoff while preserving evidence and review state.",
      },
    })
  ).json();
  const dependency = await (
    await api.post(`subprojects/${subproject.id}/tickets`, {
      data: {
        title: `Completed prerequisite ${suffix}`,
        status: "DONE",
        assignee: "AGENT",
      },
    })
  ).json();
  const candidate = await (
    await api.post(`subprojects/${subproject.id}/tickets`, {
      data: {
        title: `Additional execution dependency ${suffix}`,
        assignee: "HUMAN",
      },
    })
  ).json();
  const target = await (
    await api.post(`subprojects/${subproject.id}/tickets`, {
      data: {
        title: `Review blocked handoff ${suffix}`,
        description: "Preserve the current outcome while review is blocked.",
        status: "BLOCKED",
        assignee: "HUMAN",
        source_refs: ["node:32", "docs/frontend-design-system.md"],
        depends_on: [dependency.id],
      },
    })
  ).json();
  await api.patch(`tickets/${target.id}`, {
    data: {
      blocked_by: "WAITING_HUMAN",
      blocked_reason: "Needs product owner sign-off",
    },
  });
  await api.post(`tickets/${target.id}/comments`, {
    data: {
      author: "AGENT",
      content: "Implementation is ready for a human decision.",
    },
  });

  const claimed = await (
    await api.post(`subprojects/${subproject.id}/tickets`, {
      data: {
        title: `Claimed execution ${suffix}`,
        assignee: "AGENT",
      },
    })
  ).json();
  const claim = await api.post(`tickets/${claimed.id}/claim`, {
    data: { worker_id: "playwright-worker", lease_seconds: 3600 },
  });
  expect(claim.ok()).toBeTruthy();

  return { api, project, subproject, dependency, candidate, target, claimed };
}

async function openWorkbench(page: Page, fixture: WorkbenchFixture) {
  await authenticateBrowser(page);
  await page.goto("/app");

  const isMobile = (page.viewportSize()?.width ?? 1280) < 768;
  if (isMobile) {
    const navigationTrigger = page.getByRole("button", {
      name: "Open workspace navigation",
    });
    await expect(navigationTrigger).toBeVisible();
    await navigationTrigger.click();
  }
  await page
    .getByRole("button", { name: fixture.project.name, exact: true })
    .click();

  const workspaceNavigation = page.getByRole("dialog", {
    name: "Workspace navigation",
  });
  if (isMobile) {
    await expect(workspaceNavigation).toBeHidden();
    const navigationTrigger = page.getByRole("button", {
      name: "Open workspace navigation",
    });
    await navigationTrigger.click();
    await expect(workspaceNavigation).toBeVisible();
  }

  await page
    .getByRole("button", {
      name: `${fixture.subproject.name} PLAN`,
      exact: true,
    })
    .click();
  await expect(page.getByTestId(`ticket-${fixture.target.id}`)).toBeVisible();
}

test("execution workbench preserves CRUD, metadata, dependencies, and claim state", async ({
  page,
}) => {
  const fixture = await seedWorkbench();
  await openWorkbench(page, fixture);

  const targetCard = page.getByTestId(`ticket-${fixture.target.id}`);
  await expect(targetCard).toHaveAttribute("data-status", "BLOCKED");
  await expect(targetCard.getByText("Needs product owner sign-off")).toBeVisible();
  await expect(targetCard.getByText("2 evidence")).toBeVisible();
  await expect(
    targetCard.getByText(`#${fixture.dependency.id}`, { exact: true }),
  ).toBeVisible();

  await page
    .getByRole("button", {
      name: `Open ticket #${fixture.target.id}: ${fixture.target.title}`,
    })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAccessibleName(fixture.target.title);
  await expect(dialog.getByText("Human + agent discussion")).toBeVisible();
  await expect(
    dialog.getByText("Implementation is ready for a human decision."),
  ).toBeVisible();
  await expect(dialog.getByText("node:32", { exact: true })).toBeVisible();

  const updatedTitle = `${fixture.target.title} — updated`;
  await dialog.getByLabel("Ticket title").fill(updatedTitle);
  await dialog
    .getByLabel("Description")
    .fill("Updated outcome with explicit evidence and review ownership.");
  await expect(dialog.getByText("Unsaved changes")).toBeVisible();
  await dialog.getByRole("button", { name: "Save work content" }).click();
  await expect(dialog.getByText("Unsaved changes")).toHaveCount(0);

  await dialog
    .getByLabel("Add a human comment")
    .fill("Approved to proceed through review.");
  await dialog.getByRole("button", { name: "Post comment" }).click();
  await expect(
    dialog.getByText("Approved to proceed through review."),
  ).toBeVisible();

  const candidateCheckbox = dialog.getByRole("checkbox", {
    name: new RegExp(`#${fixture.candidate.id}`),
  });
  await candidateCheckbox.check();
  await dialog.getByRole("button", { name: "Save dependencies" }).click();
  await expect(
    dialog.getByRole("button", { name: "Save dependencies" }),
  ).toBeDisabled();

  await dialog
    .getByLabel("Merge request URL")
    .fill("https://github.com/andrewb1234/taskable/pull/33");
  await dialog.getByRole("button", { name: "Attach MR" }).click();
  await expect(
    dialog.getByRole("link", { name: "Open linked merge request" }),
  ).toBeVisible();

  await dialog.getByLabel("Ticket status").click();
  await page.getByRole("option", { name: "Review" }).click();
  await dialog.getByRole("button", { name: "Close" }).click();

  const reviewColumn = page.getByTestId("column-REVIEW");
  await expect(
    reviewColumn.getByTestId(`ticket-${fixture.target.id}`),
  ).toBeVisible();
  await expect(
    reviewColumn.getByText(updatedTitle, { exact: true }),
  ).toBeVisible();

  const claimedCard = page.getByTestId(`ticket-${fixture.claimed.id}`);
  await expect(claimedCard.getByText("playwright-worker")).toBeVisible();
  await expect(claimedCard.getByText("Lease active")).toBeVisible();
  await page
    .getByRole("button", {
      name: `Open ticket #${fixture.claimed.id}: ${fixture.claimed.title}`,
    })
    .click();
  const claimedDialog = page.getByRole("dialog", {
    name: fixture.claimed.title,
  });
  await expect(claimedDialog.getByText("Agent claim active")).toBeVisible();
  await expect(
    claimedDialog.getByText("playwright-worker", { exact: true }),
  ).toBeVisible();
  await claimedDialog.getByRole("button", { name: "Close" }).click();

  page.once("dialog", (confirmation) => confirmation.accept());
  await page
    .getByRole("button", { name: `Delete ticket ${updatedTitle}` })
    .click();
  await expect(page.getByTestId(`ticket-${fixture.target.id}`)).toHaveCount(0);
  await fixture.api.dispose();
});

test("open ticket reports remote deletion without erasing loaded content", async ({
  page,
}) => {
  const fixture = await seedWorkbench();
  await openWorkbench(page, fixture);
  await page
    .getByRole("button", {
      name: `Open ticket #${fixture.target.id}: ${fixture.target.title}`,
    })
    .click();
  const dialog = page.getByRole("dialog", { name: fixture.target.title });
  await expect(dialog.getByText(fixture.target.title, { exact: true })).toBeVisible();

  const deletion = await fixture.api.delete(`tickets/${fixture.target.id}`);
  expect(deletion.ok()).toBeTruthy();
  await expect(
    dialog.getByText("This ticket was deleted elsewhere"),
  ).toBeVisible({ timeout: 1000 });
  await expect(dialog.getByLabel("Ticket title")).toHaveValue(
    fixture.target.title,
  );
  await dialog
    .getByRole("button", { name: "Close deleted ticket" })
    .click();
  await expect(page.getByTestId(`ticket-${fixture.target.id}`)).toHaveCount(0);
  await fixture.api.dispose();
});

test("360px board contains horizontal scrolling and ticket detail becomes single-column", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const fixture = await seedWorkbench();
  await openWorkbench(page, fixture);

  const dimensions = (await page.evaluate(
    `({
      boardLeft: document.querySelector('[data-testid="kanban-scroll"]').getBoundingClientRect().left,
      boardRight: document.querySelector('[data-testid="kanban-scroll"]').getBoundingClientRect().right,
      viewportWidth: document.documentElement.clientWidth,
      boardScrollWidth: document.querySelector('[data-testid="kanban-scroll"]').scrollWidth,
      boardClientWidth: document.querySelector('[data-testid="kanban-scroll"]').clientWidth,
    })`,
  )) as {
    boardLeft: number;
    boardRight: number;
    viewportWidth: number;
    boardScrollWidth: number;
    boardClientWidth: number;
  };
  expect(dimensions.boardLeft).toBeGreaterThanOrEqual(0);
  expect(dimensions.boardRight).toBeLessThanOrEqual(dimensions.viewportWidth);
  expect(dimensions.boardScrollWidth).toBeGreaterThan(
    dimensions.boardClientWidth,
  );
  await page.evaluate(`window.scrollTo(1000, 0)`);
  expect(await page.evaluate(`window.scrollX`)).toBe(0);

  const trigger = page.getByRole("button", {
    name: `Open ticket #${fixture.target.id}: ${fixture.target.title}`,
  });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: fixture.target.title });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Ticket title")).toBeVisible();

  const modalBox = await dialog.boundingBox();
  expect(modalBox).not.toBeNull();
  const primaryBox = await dialog.getByTestId("ticket-primary-pane").boundingBox();
  const metadataBox = await dialog
    .getByTestId("ticket-metadata-pane")
    .boundingBox();
  expect(primaryBox).not.toBeNull();
  expect(metadataBox).not.toBeNull();
  expect(modalBox?.width).toBeLessThanOrEqual(page.viewportSize()?.width ?? 360);
  expect(primaryBox?.width).toBe(modalBox?.width);
  expect(metadataBox?.width).toBe(modalBox?.width);
  expect(metadataBox?.x).toBe(primaryBox?.x);
  expect(metadataBox?.y).toBeGreaterThan(primaryBox?.y ?? 0);

  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await fixture.api.dispose();
});
