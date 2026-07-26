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

test("desktop shell keeps planning, execution, and profile discoverable", async ({
  page,
}) => {
  await authenticateBrowser(page);
  await page.goto("/");

  const workspaceViews = page.getByLabel("Workspace views");
  await expect(workspaceViews).toBeVisible();
  await expect(
    workspaceViews.getByRole("button", { name: /Knowledge/ }),
  ).toBeVisible();
  await expect(
    workspaceViews.getByRole("button", { name: /Kanban/ }),
  ).toBeVisible();
  await expect(page.getByText("Active context")).toBeVisible();

  await page.getByRole("button", { name: "Profile & settings" }).click();
  await expect(
    page.getByRole("heading", { name: "Profile & Settings" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page.getByLabel("Workspace views")).toBeVisible();
});

test("desktop navigation width is keyboard-resizable and persists", async ({
  page,
}) => {
  await authenticateBrowser(page);
  await page.goto("/");

  const separator = page.getByRole("separator", {
    name: "Resize workspace navigation",
  });
  await expect(separator).toHaveAttribute("aria-valuenow", "288");
  await separator.focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await expect(separator).toHaveAttribute("aria-valuenow", "320");
  await expect
    .poll(() =>
      page.evaluate(`localStorage.getItem("taskable.sidebar.width")`),
    )
    .toBe("320");

  await page.reload();
  await expect(
    page.getByRole("separator", { name: "Resize workspace navigation" }),
  ).toHaveAttribute("aria-valuenow", "320");
});

test("navigation resizing survives unavailable persistence", async ({ page }) => {
  await page.addInitScript(() => {
    const getItem = Storage.prototype.getItem;
    const setItem = Storage.prototype.setItem;
    Storage.prototype.getItem = function (key: string) {
      if (key === "taskable.sidebar.width") {
        throw new DOMException("Storage denied", "SecurityError");
      }
      return getItem.call(this, key);
    };
    Storage.prototype.setItem = function (key: string, value: string) {
      if (key === "taskable.sidebar.width") {
        throw new DOMException("Storage denied", "SecurityError");
      }
      return setItem.call(this, key, value);
    };
  });
  await authenticateBrowser(page);
  await page.goto("/");

  const separator = page.getByRole("separator", {
    name: "Resize workspace navigation",
  });
  await expect(separator).toHaveAttribute("aria-valuenow", "288");
  await separator.focus();
  await page.keyboard.press("ArrowRight");
  await expect(separator).toHaveAttribute("aria-valuenow", "304");
});

test("mobile navigation traps focus, closes with Escape, and contains overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await authenticateBrowser(page);
  await page.goto("/");

  const trigger = page.getByRole("button", {
    name: "Open workspace navigation",
  });
  await trigger.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Control plane")).toHaveCount(0);
  expect(
    await page.evaluate(
      `document.querySelector('[role="dialog"]').contains(document.activeElement)`,
    ),
  ).toBe(true);

  const lockup = await dialog.getByLabel("Mouvadah").boundingBox();
  const close = await dialog.getByRole("button", { name: "Close" }).boundingBox();
  expect(lockup).not.toBeNull();
  expect(close).not.toBeNull();
  const overlaps =
    lockup!.x < close!.x + close!.width &&
    lockup!.x + lockup!.width > close!.x &&
    lockup!.y < close!.y + close!.height &&
    lockup!.y + lockup!.height > close!.y;
  expect(overlaps).toBe(false);

  const dialogDimensions = await dialog.evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }));
  expect(dialogDimensions.scrollWidth).toBeLessThanOrEqual(
    dialogDimensions.clientWidth,
  );

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(trigger).toBeFocused();

  const dimensions = (await page.evaluate(
    `({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    })`,
  )) as { scrollWidth: number; clientWidth: number };
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);

  const viewportWidth = page.viewportSize()!.width;
  for (const tab of await page.getByLabel("Workspace views").getByRole("button").all()) {
    const box = await tab.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(viewportWidth);
  }
});

test("sidebar reports project creation failures without an unhandled error", async ({
  page,
}) => {
  await authenticateBrowser(page);
  await page.route("**/api/v1/projects", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Project creation unavailable" }),
      });
      return;
    }
    await route.continue();
  });
  await page.goto("/");

  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Project name").fill("Failure fixture");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Project creation unavailable",
  );
});

test("profile round trip preserves the selected project and subproject", async ({
  page,
}) => {
  await authenticateBrowser(page);
  const api = await authenticatedApi();
  const suffix = Date.now();
  const project = await (
    await api.post("projects", {
      data: { name: `Persistent context ${suffix}` },
    })
  ).json();
  const subproject = await (
    await api.post(`projects/${project.id}/subprojects`, {
      data: {
        name: `Selected work ${suffix}`,
        context_brief: "Context survives profile navigation.",
      },
    })
  ).json();

  await page.goto("/");
  await page.getByRole("button", { name: project.name, exact: true }).click();
  await page.locator(`button[title="${subproject.name}"]`).click();
  await expect(
    page.getByRole("heading", { name: subproject.name }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Profile & settings" }).click();
  await expect(
    page.getByRole("heading", { name: "Profile & Settings" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Back" }).click();
  await expect(
    page.getByRole("heading", { name: subproject.name }),
  ).toBeVisible();
});

test("remote subproject deletion clears stale active context", async ({
  page,
}) => {
  await authenticateBrowser(page);
  const api = await authenticatedApi();
  const suffix = Date.now();
  const project = await (
    await api.post("projects", {
      data: { name: `Shell project ${suffix}` },
    })
  ).json();
  const subproject = await (
    await api.post(`projects/${project.id}/subprojects`, {
      data: {
        name: `Remote deletion ${suffix}`,
        context_brief: "Shell deletion cleanup",
      },
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
  await expect(
    page.getByRole("heading", { name: subproject.name }),
  ).toBeVisible();

  const deletion = await api.delete(`subprojects/${subproject.id}`);
  expect(deletion.ok()).toBeTruthy();
  await expect(
    page.getByText(
      "Select a subproject from the sidebar to open the Kanban board.",
    ),
  ).toBeVisible({ timeout: 1000 });
  await expect(page.getByText(subproject.name, { exact: true })).toHaveCount(0);
});
