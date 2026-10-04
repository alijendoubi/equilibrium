import Link from "next/link";

/** Slim header for inner pages: home link plus an optional compact search form (works without JS). */
export function PageHeader({ query = "" }: { query?: string }) {
  return (
    <header className="flex flex-wrap items-center gap-4 border-b border-border pb-4">
      <Link href="/" className="text-sm font-semibold tracking-tight">
        Equilibrium
      </Link>
      <form role="search" action="/search" method="get" className="ml-auto flex-1 sm:max-w-sm">
        <label htmlFor="header-search" className="sr-only">
          Search the atlas
        </label>
        <input
          id="header-search"
          name="q"
          type="search"
          defaultValue={query}
          placeholder="Search a disease, gene or symptom"
          className="w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm placeholder:text-muted"
        />
      </form>
    </header>
  );
}
