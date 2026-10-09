import { describe, expect, it } from "vitest";
import { generateMetadata } from "@/app/disease/[id]/page";
import robots from "@/app/robots";
import sitemap from "@/app/sitemap";
import { DEFAULT_SITE_URL, absoluteUrl, getSiteUrl, metaDescription } from "@/lib/site";

describe("site url", () => {
  it("defaults to the live URL and strips trailing slashes", () => {
    expect(getSiteUrl(undefined)).toBe(DEFAULT_SITE_URL);
    expect(getSiteUrl("https://atlas.example.org/")).toBe("https://atlas.example.org");
  });

  it("rejects non-http URLs instead of emitting broken canonicals", () => {
    expect(() => getSiteUrl("javascript:alert(1)")).toThrow(/NEXT_PUBLIC_SITE_URL/);
    expect(() => getSiteUrl("atlas.example.org")).toThrow();
  });

  it("builds absolute URLs and short descriptions", () => {
    expect(absoluteUrl("/map", "https://a.org")).toBe("https://a.org/map");
    expect(metaDescription("a  b\n c")).toBe("a b c");
    const long = metaDescription("x".repeat(400));
    expect(long).toHaveLength(155);
    expect(long.endsWith("…")).toBe(true);
  });
});

describe("robots and sitemap", () => {
  it("allows crawling, hides the API, and points at the sitemap", () => {
    const result = robots();
    expect(result.rules).toEqual([{ userAgent: "*", allow: "/", disallow: ["/api/"] }]);
    expect(result.sitemap).toBe(`${DEFAULT_SITE_URL}/sitemap.xml`);
  });

  it("lists entry points, clusters and cluster member diseases as absolute URLs", async () => {
    const urls = (await sitemap()).map((entry) => entry.url);
    expect(urls).toContain(`${DEFAULT_SITE_URL}/`);
    expect(urls).toContain(`${DEFAULT_SITE_URL}/map`);
    expect(urls).toContain(`${DEFAULT_SITE_URL}/disease/MONDO%3A0009266`);
    expect(urls.some((u) => u.includes("/clusters/"))).toBe(true);
    expect(new Set(urls).size).toBe(urls.length);
    expect(urls.every((u) => u.startsWith("https://"))).toBe(true);
  });
});

describe("disease metadata", () => {
  it("has a title, a short description and an encoded canonical", async () => {
    const meta = await generateMetadata({ params: Promise.resolve({ id: "MONDO%3A0009266" }) });
    expect(meta.title).toBe("Gaucher disease type II · Equilibrium");
    expect(String(meta.description).length).toBeLessThanOrEqual(155);
    expect(meta.alternates?.canonical).toBe("/disease/MONDO%3A0009266");
  });

  it("keeps unknown ids out of the index", async () => {
    const meta = await generateMetadata({ params: Promise.resolve({ id: "MONDO%3A0000000" }) });
    expect(meta.robots).toEqual({ index: false });
  });
});
