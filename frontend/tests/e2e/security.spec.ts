import { expect, test, type Page } from "@playwright/test";

// The CSP must protect the app without breaking it: every journey below runs its client scripts
// (orb trace server action, map canvas, explain panel) under the production policy.

function collectCspViolations(page: Page): string[] {
  const violations: string[] = [];
  page.on("console", (message) => {
    if (/Content Security Policy|Refused to (load|execute|connect|apply)/i.test(message.text())) {
      violations.push(message.text());
    }
  });
  page.on("pageerror", (error) => violations.push(`pageerror: ${error.message}`));
  return violations;
}

test("pages are served with a nonce CSP and the static security headers", async ({ page }) => {
  const response = await page.goto("/");
  const headers = response!.headers();
  const csp = headers["content-security-policy"] ?? "";

  expect(csp).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
  expect(csp).not.toContain("unsafe-eval");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["strict-transport-security"]).toContain("max-age=");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");

  const second = await page.request.get("/");
  expect(second.headers()["content-security-policy"]).not.toBe(csp);
});

test("core journeys run with no CSP violations", async ({ page }) => {
  const violations = collectCspViolations(page);

  await page.goto("/");
  await page.getByRole("button", { name: "Gaucher disease", exact: true }).click();
  await expect(page.getByRole("link", { name: /Open full map/ })).toBeVisible();

  await page.goto("/map?center=MONDO%3A0009266");
  await expect(page.getByRole("button", { name: /^Gene: GBA1\./ })).toBeVisible();

  await page.goto("/disease/MONDO%3A0009266");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  await page.goto("/clusters");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  expect(violations).toEqual([]);
});
