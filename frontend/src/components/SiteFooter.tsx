import Link from "next/link";

export const REPO_URL = "https://github.com/alijendoubi/equilibrium";

const LINKS = [
  { href: "/about", label: "About" },
  { href: "/disclaimer", label: "Medical disclaimer" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
] as const;

/** Site-wide footer: what Equilibrium is, the legal pages and the source. */
export function SiteFooter() {
  return (
    <footer className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-3 border-t border-border px-6 py-6 text-xs text-muted">
      <p>
        Equilibrium · open-source rare disease atlas · research context only, not medical advice
      </p>
      <nav aria-label="Legal and project" className="flex flex-wrap gap-x-4 gap-y-2">
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="underline-offset-4 hover:text-foreground hover:underline"
          >
            {link.label}
          </Link>
        ))}
        <a href={REPO_URL} className="underline-offset-4 hover:text-foreground hover:underline">
          Source on GitHub
        </a>
      </nav>
    </footer>
  );
}
