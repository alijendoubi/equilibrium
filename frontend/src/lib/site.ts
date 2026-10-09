import { z } from "zod";

/** Public production URL until the owner settles the domain (#81); override with NEXT_PUBLIC_SITE_URL. */
export const DEFAULT_SITE_URL = "https://frontend-iota-eight-14.vercel.app";

export const SITE_NAME = "Equilibrium";
export const SITE_DESCRIPTION =
  "An explainable, evidence-first atlas of rare diseases: every connection cites its source, and missing evidence is shown as an honest gap.";

const siteUrlSchema = z
  .string()
  .trim()
  .optional()
  .transform((value) => value || DEFAULT_SITE_URL)
  .pipe(z.url({ protocol: /^https?$/ }))
  .transform((value) => value.replace(/\/+$/, ""));

/** Canonical origin for metadata, the sitemap and robots.txt (no trailing slash). */
export function getSiteUrl(raw: string | undefined = process.env.NEXT_PUBLIC_SITE_URL): string {
  const parsed = siteUrlSchema.safeParse(raw);
  if (!parsed.success) throw new Error(`Invalid NEXT_PUBLIC_SITE_URL: ${raw}`);
  return parsed.data;
}

export function absoluteUrl(path: string, base: string = getSiteUrl()): string {
  return new URL(path, `${base}/`).toString();
}

/** Short plain-text description for meta tags (search engines show about 155 characters). */
export function metaDescription(text: string, max = 155): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max - 1).trimEnd()}…` : flat;
}
