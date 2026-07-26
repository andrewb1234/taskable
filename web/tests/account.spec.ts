import { expect, test, type Page } from "./uiFixture";
import { E2E_API_KEY } from "./authFixture";

async function authenticateBrowser(page: Page) {
  const response = await page.request.post("/api/v1/auth/local-session", {
    data: { api_key: E2E_API_KEY },
    headers: { Origin: "http://127.0.0.1:5173" },
  });
  expect(response.ok()).toBeTruthy();
}

async function openProfile(page: Page) {
  await authenticateBrowser(page);
  await page.goto("/app");
  await expect(page.getByLabel("Workspace views")).toBeVisible();
  if (
    (await page.getByRole("button", { name: "Profile & settings" }).count()) ===
    0
  ) {
    await page
      .getByRole("button", { name: "Open workspace navigation" })
      .click();
  }
  await page.getByRole("button", { name: "Profile & settings" }).click();
  await expect(
    page.getByRole("heading", { name: "Profile & Settings" }),
  ).toBeVisible();
}

test("sign-in names only the configured authentication methods", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/providers", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ google: true, local_api_key: true }),
    });
  });

  await page.goto("/app");
  await expect(
    page.getByRole("button", { name: "Continue with Google" }),
  ).toBeVisible();
  await expect(page.getByText("Google sign-in", { exact: true })).toHaveCount(2);
  await expect(page.getByText("API-key sign-in", { exact: true })).toHaveCount(
    2,
  );
  await expect(page.getByLabel("Local API key")).toHaveAttribute(
    "type",
    "password",
  );
  await expect(
    page.getByText("never saved by this UI", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Hosted workspace")).toHaveCount(0);
  await expect(page.getByText("Local installation")).toHaveCount(0);
});

test("sign-in explains an environment with no configured provider", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/providers", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ google: false, local_api_key: false }),
    });
  });

  await page.goto("/app");
  await expect(
    page.getByRole("status").getByText("No sign-in method is configured"),
  ).toBeVisible();
  await expect(
    page.getByText("ask the deployment operator", { exact: false }),
  ).toBeVisible();
});

test("sign-in heading stack stays separate at tablet width", async ({
  page,
}) => {
  await page.setViewportSize({ width: 904, height: 800 });
  await page.goto("/app");

  const back = await page
    .getByRole("button", { name: "Back to overview" })
    .boundingBox();
  const heading = await page
    .getByRole("heading", { name: "Sign in to Mouvadah" })
    .boundingBox();
  expect(back).not.toBeNull();
  expect(heading).not.toBeNull();
  expect(heading!.y).toBeGreaterThanOrEqual(back!.y + back!.height);
  await expect(page.getByText("Workspace access")).toHaveCount(0);
});

test("profile groups trust surfaces and completes an API-key lifecycle", async ({
  page,
}) => {
  await page
    .context()
    .grantPermissions(["clipboard-read", "clipboard-write"]);
  await openProfile(page);

  const sectionNavigation = page.getByRole("navigation", {
    name: "Profile settings sections",
  });
  await expect(
    sectionNavigation.getByRole("button", { name: "Identity" }),
  ).toBeVisible();
  await expect(
    sectionNavigation.getByRole("button", { name: "Workspace access" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Browser Sessions" }),
  ).toBeVisible();
  await expect(page.getByText("This browser", { exact: true })).toBeVisible();

  const keyName = `Playwright account ${Date.now()}`;
  await page.getByLabel("Key name").fill(keyName);
  await page.getByLabel("Expires (days)").fill("1");
  await page.getByRole("button", { name: "Create Key" }).click();

  await expect(
    page.getByText("API key created — copy it now!"),
  ).toBeVisible();
  const copyButton = page.getByRole("button", { name: "Copy new API key" });
  await copyButton.click();
  await expect(
    page.getByRole("button", { name: "API key copied" }),
  ).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: `Revoke ${keyName}` }).click();
  await expect(page.getByText(keyName, { exact: true })).toHaveClass(
    /line-through/,
  );
});

test("invalid invitation is never exposed and terminal state is cleaned up", async ({
  page,
}) => {
  await authenticateBrowser(page);
  const invitationToken = "invalid-invitation-fixture";
  await page.goto(`/#invite=${invitationToken}`);

  await expect(
    page.getByRole("heading", {
      name: "Workspace invitation for playwright@example.invalid",
    }),
  ).toBeVisible();
  await expect(page.getByText(invitationToken, { exact: false })).toHaveCount(0);

  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        `window.sessionStorage.getItem("mouvadah.pending-invitation")`,
      ),
    )
    .toBeNull();
});

test("profile remains usable without horizontal overflow at 360px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await openProfile(page);

  await expect(
    page.getByRole("navigation", { name: "Profile settings sections" }),
  ).toBeVisible();
  await page
    .getByRole("navigation", { name: "Profile settings sections" })
    .getByRole("button", { name: "Browser sessions" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Browser Sessions" }),
  ).toBeVisible();

  const dimensions = (await page.evaluate(
    `({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    })`,
  )) as { scrollWidth: number; clientWidth: number };
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
  await page.getByRole("button", { name: "Back to workspace" }).click();
  await expect(page.getByLabel("Workspace views")).toBeVisible();
});
