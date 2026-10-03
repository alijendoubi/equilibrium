export const SEARCH_PLACEHOLDER = 'Search a disease, gene, or symptom — e.g. "STXBP1"';

export function GlobalSearch() {
  return (
    <form role="search" className="w-full">
      <label htmlFor="global-search" className="mb-2 block text-sm font-medium text-muted">
        Search the atlas
      </label>
      <div className="relative">
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
          disabled
          aria-describedby="search-hint"
          placeholder={SEARCH_PLACEHOLDER}
          autoComplete="off"
          className="w-full cursor-not-allowed rounded-2xl border border-border bg-surface py-4 pr-4 pl-12 text-base text-foreground shadow-sm placeholder:text-muted disabled:opacity-80"
        />
      </div>
      <p id="search-hint" className="mt-2 text-xs text-muted">
        Search across diseases, genes, symptoms, patient groups and mechanisms. Coming soon.
      </p>
    </form>
  );
}
