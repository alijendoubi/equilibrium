import { expect, test } from "@playwright/test";

test("crawlers get a sitemap, robots rules and share images", async ({ request }) => {
  const sitemap = await request.get("/sitemap.xml");
  expect(sitemap.ok()).toBe(true);
  const xml = await sitemap.text();
  expect(xml).toContain("<urlset");
  expect(xml).toContain("/disease/MONDO%3A0009266");

  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toMatch(/Sitemap: https?:\/\/\S+\/sitemap\.xml/);
  expect(robots).toContain("Disallow: /api/");

  for (const path of ["/opengraph-image", "/disease/MONDO%3A0009266/opengraph-image"]) {
    const image = await request.get(path);
    expect(image.ok(), path).toBe(true);
    expect(image.headers()["content-type"]).toBe("image/png");
    expect((await image.body()).length).toBeGreaterThan(5_000);
  }
});

test("pages carry canonical, Open Graph and robots tags", async ({ page }) => {
  await page.goto("/disease/MONDO%3A0009266");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    /\/disease\/MONDO%3A0009266$/,
  );
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute(
    "content",
    "Gaucher disease type II · Equilibrium",
  );
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
    "content",
    /opengraph-image/,
  );

  await page.goto("/search?q=Gaucher");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
});
