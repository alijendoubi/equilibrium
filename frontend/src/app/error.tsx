"use client";

import { ErrorView } from "@/components/errors/ErrorView";

/** Route-level boundary: a failing page keeps the layout and footer, and can retry in place. */
export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorView digest={error.digest} onRetry={reset} />;
}
