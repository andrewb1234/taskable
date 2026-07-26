import { expect, test, type Page } from "./uiFixture";
import { E2E_API_KEY } from "./authFixture";

async function authenticateBrowser(page: Page) {
  const response = await page.request.post("/api/v1/auth/local-session", {
    data: { api_key: E2E_API_KEY },
    headers: { Origin: "http://127.0.0.1:5173" },
  });
  expect(response.ok()).toBeTruthy();
}

test("public landing hands an unauthenticated visitor into sign in", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "What are you doing?" }),
  ).toBeVisible();
  await expect(
    page.getByText("Know what every human and agent is doing—and why."),
  ).toBeVisible();
  await expect(
    page.getByText("Mouvadah gives software teams one reviewable record"),
  ).toBeVisible();
  await expect(page.getByText("Outcome", { exact: true })).toBeVisible();
  await expect(page.getByText("Blocker", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Next safe action", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Intent", { exact: true })).not.toBeVisible();

  await page
    .getByRole("link", { name: "Sign in to your workspace" })
    .click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByLabel("Local API key")).toBeVisible();
});

test("authenticated root replace-navigates to the application", async ({
  page,
}) => {
  await authenticateBrowser(page);
  await page.goto("/");

  await expect(page).toHaveURL(/\/app$/);
  await expect(
    page.getByRole("heading", { name: "Mouvadah" }),
  ).toBeVisible();
  await expect(page.getByText("Playwright Owner", { exact: true })).toBeVisible();
});

test("authenticated application survives a direct refresh", async ({ page }) => {
  await authenticateBrowser(page);
  await page.goto("/app");
  await expect(page.getByText("Playwright Owner", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByText("Playwright Owner", { exact: true })).toBeVisible();
});

test("invitation fragments are preserved without becoming visible", async ({
  page,
}) => {
  const invitationToken = "invite-fixture-not-a-secret";
  await page.goto(`/#invite=${invitationToken}`);

  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByText(invitationToken, { exact: false })).toHaveCount(0);
  await expect
    .poll(() =>
      page.evaluate(
        `window.sessionStorage.getItem("mouvadah.pending-invitation")`,
      ),
    )
    .toBe(invitationToken);
});

test("landing remains contained at 360px", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "What are you doing?" }),
  ).toBeVisible();
  await expect(page.getByText("Shared project state")).toBeVisible();
  await expect(page.getByText("Human + agent control plane")).toHaveCount(0);
  const dimensions = (await page.evaluate(
    `({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    })`,
  )) as { scrollWidth: number; clientWidth: number };
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);

  const proof = await page.getByTestId("landing-project-proof").boundingBox();
  expect(proof).not.toBeNull();
  expect(proof!.x).toBeGreaterThanOrEqual(0);
  expect(proof!.x + proof!.width).toBeLessThanOrEqual(360);
});

test("reduced-motion landing exposes the complete static lifecycle", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  await page.getByText("How this state was reached").click();
  await expect(page.getByText("Intent", { exact: true })).toBeVisible();
  await expect(page.getByText("Handoff", { exact: true })).toBeVisible();
  const entryAnimations = (await page.evaluate(
    `[...document.querySelectorAll(".motion-enter")].map(
      (element) => getComputedStyle(element).animationName,
    )`,
  )) as string[];
  expect(entryAnimations.every((name) => name === "none")).toBe(true);
});

test("landing skip link moves focus to the main content", async ({ page }) => {
  await page.goto("/");
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await skipLink.focus();
  await expect(skipLink).toBeFocused();
  await skipLink.press("Enter");
  await expect(page.locator("#landing-main")).toBeFocused();
});
