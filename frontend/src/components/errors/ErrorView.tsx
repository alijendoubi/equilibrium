"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

export interface ErrorViewProps {
  /** Next.js error digest: matches the server log line for this failure. */
  digest?: string;
  onRetry: () => void;
}

/** What a visitor sees when a page fails: what happened, a retry, a way out, and a reference. */
export function ErrorView({ digest, onRetry }: ErrorViewProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => headingRef.current?.focus(), []);

  return (
    <main className="mx-auto max-w-3xl px-6 py-16" role="alert">
      <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-semibold outline-none">
        Something went wrong on this page
      </h1>
      <p className="mt-2 leading-relaxed text-muted">
        The atlas could not finish loading it. This is our fault, not yours, and trying again
        usually works.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onRetry}
          className="rounded-full bg-cluster px-5 py-2.5 text-sm font-semibold text-background hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-full border border-border px-5 py-2.5 text-sm font-semibold hover:border-cluster"
        >
          Back to search
        </Link>
      </div>
      {digest && (
        <p className="mt-8 text-xs text-muted">
          If it keeps happening, report it on GitHub with this reference:{" "}
          <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-foreground">
            {digest}
          </code>
        </p>
      )}
    </main>
  );
}
