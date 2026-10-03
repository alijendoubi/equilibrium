import { expect, test } from "@playwright/test";

test("landing page renders search and Maria's questions", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: "Equilibrium · Rare Disease Atlas" }),
  ).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Search the atlas" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Who shares our disease characteristics?" }),
  ).toBeVisible();
});
