import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Equilibrium | Evidence that helps rare-disease communities act together",
  description:
    "Equilibrium turns disconnected rare-disease evidence into a transparent map of connections, opportunities, and unanswered questions.",
};

const APP_URL = process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") ?? "/";

const principles = [
  {
    number: "01",
    title: "Traceable by design",
    copy: "Every connection leads back to a record, a link, and the date we retrieved it.",
  },
  {
    number: "02",
    title: "Useful across boundaries",
    copy: "Find shared genes, mechanisms, studies, organisations and assets that are easy to miss in a single disease view.",
  },
  {
    number: "03",
    title: "Honest about uncertainty",
    copy: "Hypotheses are dashed. Conflicting sources are visible. Missing evidence becomes the next question, not a polished fiction.",
  },
] as const;

function AppLink({
  href,
  children,
  className,
}: Readonly<{ href: string; children: React.ReactNode; className?: string }>) {
  const target = href === "/" ? APP_URL : `${APP_URL}${href}`;
  return (
    <Link href={target} className={className}>
      {children}
    </Link>
  );
}

export default function MarketingHomePage() {
  return (
    <main className="overflow-hidden bg-background text-foreground">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-8">
        <Link
          href="/"
          className="text-lg font-semibold tracking-tight"
          aria-label="Equilibrium home"
        >
          equilibrium<span className="text-cluster">.</span>
        </Link>
        <nav aria-label="Primary" className="hidden items-center gap-7 text-sm text-muted md:flex">
          <a href="#how-it-works" className="hover:text-foreground">
            How it works
          </a>
          <a href="#principles" className="hover:text-foreground">
            Our standard
          </a>
          <AppLink href="/map" className="font-medium text-foreground hover:text-cluster">
            Explore the atlas
          </AppLink>
        </nav>
        <AppLink
          href="/"
          className="rounded-full bg-foreground px-4 py-2 text-sm font-semibold text-background transition-transform hover:opacity-90 active:scale-[0.98]"
        >
          Open Equilibrium
        </AppLink>
      </header>

      <section className="relative mx-auto grid min-h-[calc(100dvh-5.5rem)] max-w-7xl items-center gap-12 px-6 py-16 lg:grid-cols-[1.05fr_.95fr] lg:px-8 lg:py-24">
        <div
          aria-hidden="true"
          className="absolute -top-20 right-[-18rem] -z-0 size-[42rem] rounded-full bg-cluster/10 blur-3xl"
        />
        <div className="relative z-10">
          <p className="text-xs font-semibold tracking-[0.2em] text-cluster uppercase">
            A rare-disease evidence atlas
          </p>
          <h1 className="mt-6 max-w-3xl text-5xl leading-[.98] font-semibold tracking-[-0.055em] text-balance sm:text-6xl lg:text-7xl">
            Make the connections that isolated evidence keeps hidden.
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-relaxed text-muted">
            Equilibrium helps patient communities, researchers and funders see where diseases
            connect - and what those connections make possible.
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <AppLink
              href="/"
              className="rounded-full bg-cluster px-5 py-3 text-sm font-semibold text-background transition-transform hover:opacity-90 active:scale-[0.98]"
            >
              Explore the evidence map
            </AppLink>
            <a
              href="#how-it-works"
              className="rounded-full border border-border px-5 py-3 text-sm font-semibold transition-colors hover:border-cluster hover:text-cluster"
            >
              See how it works
            </a>
          </div>
          <p className="mt-6 text-sm text-muted">
            Built for decisions that deserve more than a search result.
          </p>
        </div>

        <div
          className="relative z-10 mx-auto w-full max-w-xl"
          aria-label="A preview of a sourced evidence map"
        >
          <div className="relative aspect-square rounded-[2rem] border border-border bg-surface p-6 shadow-[0_28px_80px_color-mix(in_oklab,var(--cluster)_14%,transparent)] sm:p-9">
            <div
              aria-hidden="true"
              className="absolute inset-0 rounded-[2rem] opacity-60 [background-image:linear-gradient(color-mix(in_oklab,var(--cluster)_10%,transparent)_1px,transparent_1px),linear-gradient(90deg,color-mix(in_oklab,var(--cluster)_10%,transparent)_1px,transparent_1px)] [background-size:42px_42px]"
            />
            <p className="relative text-xs font-semibold tracking-[0.17em] text-cluster uppercase">
              One map, many starting points
            </p>
            <div className="absolute top-[29%] left-[25%] h-px w-[26%] -rotate-[28deg] bg-cluster/50" />
            <div className="absolute top-[46%] left-[39%] h-px w-[26%] rotate-[7deg] bg-evidence/60" />
            <div className="absolute top-[62%] left-[29%] h-px w-[25%] rotate-[42deg] border-t border-dashed border-action" />
            <div className="absolute top-[30%] right-[13%] rounded-2xl border border-cluster bg-cluster px-4 py-3 text-sm font-semibold text-background shadow-sm">
              GBA1
            </div>
            <div className="absolute top-[43%] left-[10%] rounded-2xl border border-border bg-background px-4 py-3 text-sm font-semibold shadow-sm">
              Gaucher disease
            </div>
            <div className="absolute top-[54%] right-[8%] rounded-2xl border border-border bg-background px-4 py-3 text-sm font-semibold shadow-sm">
              Study
            </div>
            <div className="absolute bottom-[11%] left-[20%] rounded-2xl border border-dashed border-action bg-background px-4 py-3 text-sm font-semibold text-action shadow-sm">
              Open question
            </div>
            <p className="absolute right-6 bottom-6 left-6 text-xs leading-relaxed text-muted">
              Solid lines are supported claims. Dashed lines make uncertainty visible.
            </p>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="border-y border-border bg-surface">
        <div className="mx-auto max-w-7xl px-6 py-20 lg:px-8">
          <div className="grid gap-8 lg:grid-cols-[.8fr_1.2fr]">
            <div>
              <p className="text-xs font-semibold tracking-[0.2em] text-evidence uppercase">
                From question to action
              </p>
              <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
                The atlas does not just return results. It shows its work.
              </h2>
            </div>
            <ol className="divide-y divide-border border-y border-border">
              {[
                ["Start anywhere", "Search a disease, gene, symptom or organisation."],
                [
                  "Follow the evidence",
                  "Open the map to inspect the biology, people, studies and sources around it.",
                ],
                [
                  "Find a next move",
                  "Turn shared evidence into a clearer collaboration, research or funding question.",
                ],
              ].map(([title, copy], index) => (
                <li key={title} className="grid grid-cols-[3rem_1fr] gap-4 py-5">
                  <span className="font-mono text-sm text-evidence">0{index + 1}</span>
                  <div>
                    <h3 className="font-semibold">{title}</h3>
                    <p className="mt-1 leading-relaxed text-muted">{copy}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section id="principles" className="mx-auto max-w-7xl px-6 py-24 lg:px-8">
        <p className="text-xs font-semibold tracking-[0.2em] text-action uppercase">
          A different standard for health intelligence
        </p>
        <div className="mt-5 grid gap-6 lg:grid-cols-3">
          {principles.map((principle) => (
            <article key={principle.number} className="border-t border-border pt-5">
              <p className="font-mono text-sm text-action">{principle.number}</p>
              <h2 className="mt-8 text-2xl font-semibold tracking-tight">{principle.title}</h2>
              <p className="mt-3 max-w-sm leading-relaxed text-muted">{principle.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-4 mb-4 rounded-[2rem] bg-foreground px-6 py-16 text-background sm:mx-6 lg:mx-8 lg:px-12">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-8 lg:flex-row lg:items-end">
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] text-cluster uppercase">
              See the evidence differently
            </p>
            <h2 className="mt-4 max-w-2xl text-3xl font-semibold tracking-tight sm:text-5xl">
              Better connections start with evidence everyone can inspect.
            </h2>
          </div>
          <AppLink
            href="/"
            className="shrink-0 rounded-full bg-cluster px-5 py-3 text-sm font-semibold text-background transition-transform hover:opacity-90 active:scale-[0.98]"
          >
            Open the Atlas
          </AppLink>
        </div>
      </section>

      <footer className="mx-auto flex max-w-7xl flex-wrap justify-between gap-4 px-6 py-8 text-sm text-muted lg:px-8">
        <p>Equilibrium - Rare Disease Atlas</p>
        <p>Every line is a claim. Every claim has a source.</p>
      </footer>
    </main>
  );
}
