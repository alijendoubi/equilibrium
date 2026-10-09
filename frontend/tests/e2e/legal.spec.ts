import { expect, test } from "@playwright/test";

test("every page footer links the legal pages, and each one loads", async ({ page }) => {
  for (const start of ["/", "/map", "/disease/MONDO%3A0009266"]) {
    await page.goto(start);
    const footer = page.getByRole("navigation", { name: "Legal and project" });
    await expect(footer.getByRole("link", { name: "Medical disclaimer" })).toBeVisible();
  }

  for (const [name, heading] of [
    ["About", "About Equilibrium"],
    ["Medical disclaimer", "Medical disclaimer"],
    ["Privacy", "Privacy"],
    ["Terms", "Terms of use"],
  ]) {
    await page.goto("/");
    await page
      .getByRole("navigation", { name: "Legal and project" })
      .getByRole("link", { name })
      .click();
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
});
