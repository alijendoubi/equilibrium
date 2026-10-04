"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { searchHref } from "@/lib/format";

export const SEARCH_PLACEHOLDER = 'Search a disease, gene, or symptom — e.g. "GBA1"';
export const EXAMPLE_QUERIES = ["Gaucher disease", "GBA1", "Saposin C deficiency"] as const;
export const MAX_QUERY_LENGTH = 200;

export function GlobalSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = query.trim();
    if (!q) {
      setError("Type a disease, gene or symptom first.");
      return;
    }
    setError(null);
    router.push(searchHref(q));
  }

  return (
    <form role="search" action="/search" method="get" onSubmit={onSubmit} className="w-full">
      <label htmlFor="global-search" className="mb-2 block text-sm font-medium text-muted">
        Search the atlas
      </label>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted"
          >
            <circle cx="9" cy="9" r="6" />
            <path d="m14 14 4 4" strokeLinecap="round" />
          </svg>
          <input
            id="global-search"
            name="q"
            type="search"
            value={query}
            maxLength={MAX_QUERY_LENGTH}
            onChange={(e) => setQuery(e.target.value)}
            aria-describedby="search-hint"
            aria-invalid={error ? true : undefined}
            placeholder={SEARCH_PLACEHOLDER}
            autoComplete="off"
            className="w-full rounded-2xl border border-border bg-surface py-4 pr-4 pl-12 text-base text-foreground shadow-sm placeholder:text-muted"
          />
        </div>
        <button
          type="submit"
          className="rounded-2xl border border-border bg-foreground px-5 text-sm font-medium text-background"
        >
          Search
        </button>
      </div>
      <p id="search-hint" className="mt-2 text-xs text-muted" aria-live="polite">
        {error ?? "Search across diseases, genes, symptoms, patient groups and mechanisms."}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted">Try:</span>
        {EXAMPLE_QUERIES.map((example) => (
          <Link
            key={example}
            href={searchHref(example)}
            className="rounded-full border border-border px-3 py-1 text-sm hover:border-cluster"
          >
            {example}
          </Link>
        ))}
      </div>
    </form>
  );
}
