import Link from "next/link";
import { MapMotif } from "@/components/graph/MapMotif";
import { QuestionCard, type QuestionCardProps } from "@/components/QuestionCard";
import { AiThinkingOrbAndInput } from "@/components/ui/ai-thinking-orb-and-input";
import { actionsHref, nodeHref } from "@/lib/format";
import { mapHref } from "@/lib/graph-map";

const GAUCHER_2 = "MONDO:0009266";
const SAPOSIN_C = "MONDO:0012517";

const QUESTIONS: QuestionCardProps[] = [
  {
    tone: "cluster",
    label: "Cluster",
    question: "Who shares our disease characteristics?",
    description:
      "Find diseases and patient groups linked by shared genes, symptoms and mechanisms.",
    href: mapHref({ center: GAUCHER_2 }),
    cta: "See Gaucher type II on the map",
  },
  {
    tone: "evidence",
    label: "Evidence",
    question: "What useful work already exists?",
    description:
      "Trials, registries, publications and resources, with the source behind every link.",
    href: actionsHref(GAUCHER_2),
    cta: "Open the action view",
  },
  {
    tone: "action",
    label: "Action",
    question: "What should we do together next?",
    description: "Concrete next steps your group can take with the communities closest to yours.",
    href: nodeHref(SAPOSIN_C),
    cta: "See an honest gap: saposin C",
  },
];

const PROMISES = [
  { mark: "solid", text: "Every line is a sourced claim: record, link, retrieval date." },
  { mark: "dashed", text: "Dashed lines are hypotheses from our pipeline, never proof." },
  { mark: "red", text: "Contradictions are drawn in red, not hidden." },
] as const;

export default function HomePage() {
  return (
    <main className="flex min-h-dvh flex-col">
      <AiThinkingOrbAndInput />

      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 pb-14 sm:pb-20">
        <section aria-labelledby="questions-heading">
          <h2
            id="questions-heading"
            className="text-xs font-semibold tracking-[0.18em] text-muted uppercase"
          >
            Three questions the atlas answers
          </h2>
          <ul className="mt-5 grid gap-4 sm:grid-cols-3">
            {QUESTIONS.map((q, i) => (
              <QuestionCard key={q.tone} {...q} index={i + 1} />
            ))}
          </ul>
        </section>

        <section
          aria-labelledby="map-heading"
          className="mt-16 grid items-center gap-8 overflow-hidden rounded-3xl border border-border bg-surface p-6 sm:p-10 lg:grid-cols-[1.1fr_1fr]"
        >
          <div>
            <p className="text-xs font-semibold tracking-[0.18em] text-cluster uppercase">
              Evidence map
            </p>
            <h2 id="map-heading" className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
              See how Gaucher disease and Parkinson&apos;s connect, link by link
            </h2>
            <ul className="mt-6 space-y-3 text-sm">
              {PROMISES.map((p) => (
                <li key={p.mark} className="flex items-center gap-3">
                  <svg
                    width="36"
                    height="10"
                    viewBox="0 0 36 10"
                    aria-hidden="true"
                    className="shrink-0"
                  >
                    <line
                      x1="2"
                      y1="5"
                      x2="34"
                      y2="5"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeDasharray={p.mark === "dashed" ? "6 5" : undefined}
                      style={{ stroke: p.mark === "red" ? "var(--contradiction)" : "var(--muted)" }}
                    />
                  </svg>
                  <span>{p.text}</span>
                </li>
              ))}
            </ul>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/map"
                className="inline-flex items-center gap-2 rounded-xl bg-foreground px-4 py-2.5 text-sm font-medium text-background hover:opacity-90"
              >
                Open the evidence map <span aria-hidden="true">→</span>
              </Link>
              <Link
                href="/clusters"
                className="inline-flex items-center rounded-xl border border-border px-4 py-2.5 text-sm font-medium hover:bg-background"
              >
                Browse disease clusters
              </Link>
            </div>
          </div>
          <MapMotif />
        </section>
      </div>
    </main>
  );
}
