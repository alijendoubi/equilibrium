"use client";

import { ErrorView } from "@/components/errors/ErrorView";
import "./globals.css";

/** Last-resort boundary for failures in the root layout itself, so it renders its own document. */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-dvh bg-background text-foreground">
        <ErrorView digest={error.digest} onRetry={reset} />
      </body>
    </html>
  );
}
