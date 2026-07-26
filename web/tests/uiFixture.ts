import {
  expect,
  request,
  test as base,
  type ConsoleMessage,
} from "@playwright/test";

export type {
  APIRequestContext,
  APIResponse,
  Page,
} from "@playwright/test";

export const test = base.extend<{ browserErrorGuard: void }>({
  browserErrorGuard: [
    async ({ page }, use) => {
      const errors: string[] = [];
      const onPageError = (error: Error) => {
        errors.push(`pageerror: ${error.message}`);
      };
      const onConsole = (message: ConsoleMessage) => {
        const text = message.text();
        const isHandledHttpStatus =
          text.startsWith("Failed to load resource:") &&
          text.includes("server responded with a status of");
        if (message.type() === "error" && !isHandledHttpStatus) {
          errors.push(`console.error: ${text}`);
        }
      };

      page.on("pageerror", onPageError);
      page.on("console", onConsole);
      await use();
      page.off("pageerror", onPageError);
      page.off("console", onConsole);

      expect(
        errors,
        `Unexpected browser errors:\n${errors.join("\n")}`,
      ).toEqual([]);
    },
    { auto: true },
  ],
});

export { expect, request };
