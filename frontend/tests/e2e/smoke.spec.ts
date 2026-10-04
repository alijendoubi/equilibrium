import { expect, test } from "@playwright/test";

// Runs against mock mode (NEXT_PUBLIC_USE_MOCKS unset or "true"), the same data as the demo video.

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

test("golden flow: Gaucher -> type II -> ASPro-PD -> evidence -> actions -> brief", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("searchbox", { name: "Search the atlas" }).fill("Gaucher");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/search\?q=Gaucher/);

  await page.getByRole("link", { name: /Gaucher disease type II$/ }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Gaucher disease type II" }),
  ).toBeVisible();

  await page.getByText("What exists").click();
  await page.locator(`a[href*="to=clinicaltrials%3ANCT05778617"]`).first().click();
  await expect(page).toHaveURL(/to=clinicaltrials%3ANCT05778617/);
  await expect(page.getByRole("region", { name: "Route 1" })).toBeVisible();

  await page
    .getByRole("button", { name: /is a risk factor for/ })
    .first()
    .click();
  await expect(page.getByRole("complementary", { name: "Edge evidence" })).toContainText(
    "Confidence",
  );

  await page.getByRole("link", { name: /What to do next for Gaucher disease type II/ }).click();
  await expect(page).toHaveURL(/\/actions\/MONDO%3A0009266/);
  await expect(page.getByRole("region", { name: "Who to talk to" })).toContainText(
    "Cure Parkinson's",
  );

  await page.getByRole("button", { name: "Draft collaboration brief" }).nth(1).click();
  const brief = page.getByRole("region", {
    name: "Collaboration brief: Gaucher disease type II and Cure Parkinson's",
  });
  await expect(brief.getByText("Template (AI unavailable)")).toBeVisible();
  await brief.getByRole("button", { name: "For researchers" }).click();
  await expect(brief.getByText(/Source: /).first()).toBeVisible();
});

test("gap flow: Saposin C deficiency shows the honest gap card", async ({ page }) => {
  await page.goto("/search?q=Saposin%20C%20deficiency");
  await page
    .getByRole("link", { name: /saposin C deficiency/i })
    .first()
    .click();
  const gap = page.getByRole("region", { name: /No community found yet/ });
  await expect(gap).toBeVisible();
  await expect(gap.getByText("Help build the missing community")).toBeVisible();
});
