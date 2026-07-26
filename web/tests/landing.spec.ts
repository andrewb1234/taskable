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
  await expect(
    page.getByRole("heading", {
      name: "The race, resolved in six events.",
    }),
  ).toBeVisible();
  await expect(page.getByText("Claim responses")).toBeVisible();
  await expect(
    page.getByText("409 · already claimed", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "In an isolated Northstar Commerce workspace, agent-cobalt and agent-ember",
      { exact: false },
    ),
  ).toBeAttached();

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

  const proof = await page.getByTestId("landing-claim-workflow").boundingBox();
  expect(proof).not.toBeNull();
  expect(proof!.x).toBeGreaterThanOrEqual(0);
  expect(proof!.x + proof!.width).toBeLessThanOrEqual(360);
});

test("reduced-motion landing exposes the complete static claim workflow", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");

  await expect(
    page.getByText("agent-ember takes the next ready task.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Next state" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pause" })).toHaveCount(0);
  const entryAnimations = (await page.evaluate(
    `[...document.querySelectorAll(".motion-enter")].map(
      (element) => getComputedStyle(element).animationName,
    )`,
  )) as string[];
  expect(entryAnimations.every((name) => name === "none")).toBe(true);
});

test("claim workflow can be paused and replayed", async ({ page }) => {
  await page.goto("/");
  const workflow = page.getByTestId("landing-claim-workflow");
  const status = workflow.getByRole("status");

  await expect(status).toContainText("Both agents select the checkout fix.");
  await expect(status).toContainText("agent-cobalt becomes the owner.", {
    timeout: 5_000,
  });

  await workflow.getByRole("button", { name: "Pause" }).click();
  const pausedCopy = await status.textContent();
  await page.waitForTimeout(1_800);
  await expect(status).toHaveText(pausedCopy ?? "");

  await workflow.getByRole("button", { name: "Replay" }).click();
  await expect(status).toContainText("Both agents select the checkout fix.");
});

test("claim workflow uses optimized, dimensioned local captures", async ({
  page,
}) => {
  await page.goto("/");
  const captures = page
    .getByTestId("landing-claim-workflow")
    .locator("img");
  await expect(captures).toHaveCount(3);

  const imageMetadata = await captures.evaluateAll((images) =>
    images.map((image) => {
      const capture = image as unknown as {
        currentSrc: string;
        width: number;
        height: number;
        naturalWidth: number;
        naturalHeight: number;
      };
      return {
        source: capture.currentSrc,
        width: capture.width,
        height: capture.height,
        naturalWidth: capture.naturalWidth,
        naturalHeight: capture.naturalHeight,
      };
    }),
  );
  for (const image of imageMetadata) {
    expect(image.source).toContain(".webp");
    expect(image.width).toBeGreaterThan(0);
    expect(image.height).toBeGreaterThan(0);
    expect(image.naturalWidth).toBe(680);
    expect(image.naturalHeight).toBe(680);
  }
});

test("landing skip link moves focus to the main content", async ({ page }) => {
  await page.goto("/");
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await skipLink.focus();
  await expect(skipLink).toBeFocused();
  await skipLink.press("Enter");
  await expect(page.locator("#landing-main")).toBeFocused();
});
