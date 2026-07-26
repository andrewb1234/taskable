import {
  expect,
  request,
  test,
  type APIRequestContext,
  type APIResponse,
  type Page,
} from "./uiFixture";
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

async function json<T>(response: APIResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<T>;
}

interface KnowledgeFixture {
  api: APIRequestContext;
  project: { id: number; name: string };
  root: { id: number; title: string };
  child: { id: number; title: string };
  stale: { id: number; title: string };
  archived: { id: number; title: string };
  proposal: { id: number };
}

async function seedKnowledge(): Promise<KnowledgeFixture> {
  const api = await authenticatedApi();
  const suffix = Date.now();
  const project = await json<{ id: number; name: string }>(
    await api.post("projects", {
      data: {
        name: `Knowledge workbench ${suffix}`,
        description: "Trace decisions to verified release evidence.",
      },
    }),
  );
  const root = await json<{ id: number; title: string }>(
    await api.post(`projects/${project.id}/knowledge`, {
      data: {
        title: `Release proof ${suffix}`,
        node_type: "RAW",
        content:
          "Release proof starts with verified health, accessibility, and end-to-end evidence.",
        source_refs: ["https://example.com/release-proof"],
      },
    }),
  );
  const child = await json<{ id: number; title: string }>(
    await api.post(`projects/${project.id}/knowledge`, {
      data: {
        title: `Human review policy ${suffix}`,
        node_type: "SUMMARY",
        parent_id: root.id,
        content:
          "Human review is required before durable agent knowledge changes.",
        source_refs: [`node:${root.id}`, "docs/review-policy.md", "node:999999"],
      },
    }),
  );
  const stale = await json<{ id: number; title: string }>(
    await api.post(`projects/${project.id}/knowledge`, {
      data: {
        title: `Superseded release note ${suffix}`,
        node_type: "PRD",
        content: "Historical requirement retained for provenance.",
      },
    }),
  );
  expect(
    (
      await api.patch(`knowledge/${stale.id}`, {
        data: { status: "STALE" },
      })
    ).ok(),
  ).toBeTruthy();
  const archived = await json<{ id: number; title: string }>(
    await api.post(`projects/${project.id}/knowledge`, {
      data: {
        title: `Archived architecture ${suffix}`,
        node_type: "TDD",
        content: "Archived technical direction.",
      },
    }),
  );
  expect(
    (
      await api.patch(`knowledge/${archived.id}`, {
        data: { status: "ARCHIVED" },
      })
    ).ok(),
  ).toBeTruthy();
  const proposal = await json<{ id: number }>(
    await api.post(`knowledge/${child.id}/proposals`, {
      data: {
        proposed_changes: {
          title: `Human-reviewed policy ${suffix}`,
          content: "Human review remains explicit and accountable.",
        },
        rationale: "Clarify who owns the durable decision.",
      },
    }),
  );
  return { api, project, root, child, stale, archived, proposal };
}

async function openKnowledge(page: Page, fixture: KnowledgeFixture) {
  await authenticateBrowser(page);
  await page.goto("/app");
  if ((page.viewportSize()?.width ?? 1280) < 768) {
    await page
      .getByRole("button", { name: "Open workspace navigation" })
      .click();
  }
  await page
    .getByRole("button", { name: fixture.project.name, exact: true })
    .click();
  await page
    .getByRole("button", {
      name:
        (page.viewportSize()?.width ?? 1280) < 768
          ? "Knowledge"
          : /^Knowledge Plan and review evidence/,
      exact: (page.viewportSize()?.width ?? 1280) < 768,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Knowledge workbench" }),
  ).toBeVisible();
}

test("Knowledge workbench preserves provenance, history, review, and mutations", async ({
  page,
}) => {
  const fixture = await seedKnowledge();
  await openKnowledge(page, fixture);

  await expect(page.getByText(fixture.stale.title)).toBeVisible();
  await expect(page.getByText(fixture.archived.title)).toBeVisible();
  await expect(page.getByLabel("1 Stale nodes")).toBeVisible();
  await expect(page.getByLabel("1 Archived nodes")).toBeVisible();
  await expect(
    page.getByRole("button", { name: `Collapse ${fixture.root.title}` }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: `Add child under ${fixture.root.title}` }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Root node" }).click();
  const createRoot = page.getByRole("form", {
    name: "Create root knowledge node",
  });
  await createRoot.getByLabel("Node title").fill("Temporary review checkpoint");
  await createRoot.getByRole("button", { name: "Create" }).click();
  await expect(page.getByLabel("Node title")).toHaveValue(
    "Temporary review checkpoint",
  );
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("region", { name: "Knowledge node review" })
    .getByRole("button", { name: "Delete", exact: true })
    .click();
  await expect(page.getByText("Temporary review checkpoint")).toHaveCount(0);

  await page.getByText(fixture.child.title, { exact: true }).click();
  await expect(page.getByLabel("Node title")).toHaveValue(fixture.child.title);
  await expect(page.getByRole("link", { name: /example.com/ })).toHaveCount(0);
  await expect(
    page.getByRole("button", {
      name: `Open referenced node ${fixture.root.title}`,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Missing referenced node 999999" }),
  ).toBeVisible();
  await expect(page.getByText("Proposed by AGENT")).toBeVisible();
  await expect(
    page.getByText("Clarify who owns the durable decision."),
  ).toBeVisible();
  await expect(page.getByText(/Human-reviewed policy/)).toBeVisible();
  await page
    .getByRole("button", { name: "Reject proposal" })
    .click();
  await expect(page.getByText("No pending proposals.")).toBeVisible();
  const nextProposal = await fixture.api.post(
    `knowledge/${fixture.child.id}/proposals`,
    {
      data: {
        proposed_changes: {
          content: "Human review accepted this accountable update.",
        },
        rationale: "Exercise live proposal review.",
      },
    },
  );
  expect(nextProposal.ok()).toBeTruthy();
  await expect(page.getByText("Exercise live proposal review.")).toBeVisible({
    timeout: 1_000,
  });
  await page
    .getByRole("button", { name: "Accept as human review" })
    .click();
  await expect(page.getByLabel("Node content")).toHaveValue(
    "Human review accepted this accountable update.",
  );

  await page.getByLabel("Node title").fill(`${fixture.child.title} updated`);
  await page
    .getByLabel("Node content")
    .fill("Human-reviewed knowledge keeps exact source references.");
  await page.getByLabel("Source references").fill(
    [
      `node:${fixture.root.id}`,
      "https://example.com/release-proof",
      "docs/review-policy.md",
    ].join("\n"),
  );
  await expect(page.getByText("Unsaved draft")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "https://example.com/release-proof" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Save", exact: true }).last().click();
  await expect(page.getByText("Unsaved draft")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "https://example.com/release-proof" }),
  ).toHaveAttribute("rel", /noopener/);

  const statusSelect = page.getByRole("combobox", {
    name: "Knowledge status",
  });
  await statusSelect.click();
  await page.getByRole("option", { name: "Stale" }).click();
  await expect(statusSelect).toContainText("Stale");
  await expect(page.getByLabel("2 Stale nodes")).toBeVisible();

  await page
    .getByLabel("Correction details")
    .fill("Verify this policy against the latest production review flow.");
  await page.getByRole("button", { name: "Request update" }).click();
  await expect(page.getByLabel("Node title")).toHaveValue(
    `Correction request: ${fixture.child.title} updated`,
  );

  await page
    .getByLabel("What context are you trying to load?")
    .fill("release proof human review");
  await page.getByRole("button", { name: "Find trail" }).click();
  await expect(page.getByText("Matched:", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "Save checkpoint" }).click();
  await expect(page.getByText(/Checkpoint #\d+ created with/)).toBeVisible();

  const separator = page.getByRole("separator", {
    name: "Resize knowledge map",
  });
  await separator.focus();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(() =>
      page.evaluate(`localStorage.getItem("taskable.knowledge.treeWidth")`),
    )
    .toBe("336");
});

test("Knowledge workbench preserves a dirty draft across a remote update", async ({
  page,
}) => {
  const fixture = await seedKnowledge();
  await openKnowledge(page, fixture);
  await page.getByText(fixture.child.title, { exact: true }).click();

  await page
    .getByLabel("Node content")
    .fill("Local draft that must not be overwritten.");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByText(fixture.root.title, { exact: true }).click();
  await expect(page.getByLabel("Node content")).toHaveValue(
    "Local draft that must not be overwritten.",
  );
  const remote = await fixture.api.patch(`knowledge/${fixture.child.id}`, {
    data: { content: "Remote content from another worker." },
  });
  expect(remote.ok()).toBeTruthy();

  await expect(page.getByText("Remote update available")).toBeVisible({
    timeout: 1_000,
  });
  await expect(page.getByLabel("Node content")).toHaveValue(
    "Local draft that must not be overwritten.",
  );
  await expect(
    page.getByRole("button", { name: "Save", exact: true }).last(),
  ).toBeDisabled();

  await page.getByRole("button", { name: "Load remote version" }).click();
  await expect(page.getByLabel("Node content")).toHaveValue(
    "Remote content from another worker.",
  );
  await expect(page.getByText("Remote update available")).toHaveCount(0);

  const deletion = await fixture.api.delete(`knowledge/${fixture.child.id}`);
  expect(deletion.ok()).toBeTruthy();
  await expect(page.getByText("This node was deleted remotely")).toBeVisible({
    timeout: 1_000,
  });
  await expect(page.getByLabel("Node content")).toHaveValue(
    "Remote content from another worker.",
  );
});

test("Knowledge workbench drills from map to a full-width node at 360px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const fixture = await seedKnowledge();
  await openKnowledge(page, fixture);

  await expect(
    page.getByRole("list", { name: "Knowledge hierarchy" }),
  ).toBeVisible();
  await page.getByText(fixture.root.title, { exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Back to knowledge map" }),
  ).toBeVisible();
  await expect(page.getByLabel("Node title")).toHaveValue(fixture.root.title);
  const dimensions = (await page.evaluate(
    `({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    })`,
  )) as { scrollWidth: number; clientWidth: number };
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);

  await page.getByRole("button", { name: "Back to knowledge map" }).click();
  await expect(
    page.getByRole("list", { name: "Knowledge hierarchy" }),
  ).toBeVisible();
  await expect(
    page.getByRole("separator", { name: "Resize knowledge map" }),
  ).toHaveCount(0);
});
