import { expect, test } from "@playwright/test";

test("an edge's evidence panel links to a prefilled problem report", async ({ page }) => {
  await page.goto("/map?center=MONDO%3A0009266");
  await page.getByRole("button", { name: /^Gene: GBA1\./ }).click();
  await page
    .getByRole("complementary", { name: "Node details" })
    .getByRole("region", { name: "Links on this map" })
    .getByRole("button")
    .first()
    .click();

  const panel = page.getByRole("complementary", { name: "Edge evidence" });
  const report = panel.getByRole("link", { name: /Report a problem/ });
  await expect(report).toBeVisible();
  const href = new URL((await report.getAttribute("href"))!);
  expect(href.searchParams.get("template")).toBe("edge-report.yml");
  expect(href.searchParams.get("edge_id")).toMatch(/^E:/);
  expect(href.searchParams.get("page")).toContain("/map?center=");
});
