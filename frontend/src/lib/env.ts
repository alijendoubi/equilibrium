import { z } from "zod";

export const DEFAULT_BACKEND_URL = "http://localhost:8000";

const urlWithDefault = z
  .string()
  .trim()
  .optional()
  .transform((value) => (value ? value : DEFAULT_BACKEND_URL))
  .pipe(z.url({ protocol: /^https?$/ }))
  .transform((value) => value.replace(/\/+$/, ""));

const publicEnvSchema = z.object({
  NEXT_PUBLIC_API_URL: urlWithDefault,
});

const serverEnvSchema = z.object({
  BACKEND_URL: urlWithDefault,
});

export type PublicEnv = z.infer<typeof publicEnvSchema>;
export type ServerEnv = z.infer<typeof serverEnvSchema>;

type RawEnv = Record<string, string | undefined>;

function formatIssues(error: z.ZodError): string {
  return error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`).join("; ");
}

/**
 * Browser-safe env. NEXT_PUBLIC_* vars must be referenced literally so Next.js
 * can inline them at build time.
 */
export function getPublicEnv(
  raw: RawEnv = { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL },
): PublicEnv {
  const parsed = publicEnvSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(`Invalid public environment: ${formatIssues(parsed.error)}`);
  }
  return parsed.data;
}

/** Server-only env. Never import the result into client components. */
export function getServerEnv(raw: RawEnv = { BACKEND_URL: process.env.BACKEND_URL }): ServerEnv {
  const parsed = serverEnvSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(`Invalid server environment: ${formatIssues(parsed.error)}`);
  }
  return parsed.data;
}
