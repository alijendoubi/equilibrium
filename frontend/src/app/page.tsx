import { GlobalSearch } from "@/components/GlobalSearch";
import { QuestionCard, type QuestionCardProps } from "@/components/QuestionCard";

const QUESTIONS: QuestionCardProps[] = [
  {
    tone: "cluster",
    label: "Cluster",
    question: "Who shares our disease characteristics?",
    description:
      "Find diseases and patient groups linked by shared genes, symptoms and mechanisms.",
  },
  {
    tone: "evidence",
    label: "Evidence",
    question: "What useful work already exists?",
    description:
      "Trials, registries, publications and resources, with the source behind every link.",
  },
  {
    tone: "action",
    label: "Action",
    question: "What should we do together next?",
    description: "Concrete next steps your group can take with the communities closest to yours.",
  },
];

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-5xl flex-col px-6 py-16 sm:py-24">
      <header className="max-w-2xl">
        <p className="text-sm font-medium text-muted">Equilibrium</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
          Equilibrium · Rare Disease Atlas
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-muted">
          An explainable map of the world&apos;s rare diseases, so patient groups can find each
          other, see the evidence, and act together.
        </p>
      </header>

      <section aria-label="Global search" className="mt-12 max-w-2xl">
        <GlobalSearch />
      </section>

      <section aria-labelledby="questions-heading" className="mt-16">
        <h2 id="questions-heading" className="text-sm font-medium text-muted">
          Three questions the atlas answers
        </h2>
        <ul className="mt-4 grid gap-4 sm:grid-cols-3">
          {QUESTIONS.map((q) => (
            <QuestionCard key={q.tone} {...q} />
          ))}
        </ul>
      </section>

      <footer className="mt-auto pt-16 text-xs text-muted">
        Hack-Nation Challenge 05 · Team Equilibrium
      </footer>
    </main>
  );
}
