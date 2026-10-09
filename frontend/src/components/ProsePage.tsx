import type { ReactNode } from "react";
import { PageHeader } from "@/components/PageHeader";

/** Layout for text pages (about, disclaimer, privacy, terms): readable width, dated. */
export function ProsePage({
  title,
  updated,
  children,
}: Readonly<{ title: string; updated: string; children: ReactNode }>) {
  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <PageHeader />
      <article className="mt-10 space-y-5 leading-relaxed [&_a]:text-cluster [&_a]:underline [&_a]:underline-offset-4 [&_h2]:mt-10 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:tracking-tight [&_li]:mt-2 [&_ul]:list-disc [&_ul]:pl-6">
        <header>
          <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-2 text-sm text-muted">
            Last updated <time dateTime={updated}>{updated}</time>
          </p>
        </header>
        {children}
      </article>
    </main>
  );
}
