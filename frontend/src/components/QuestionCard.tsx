export type QuestionTone = "cluster" | "evidence" | "action";

const toneClasses: Record<QuestionTone, { bar: string; label: string }> = {
  cluster: { bar: "bg-cluster", label: "text-cluster" },
  evidence: { bar: "bg-evidence", label: "text-evidence" },
  action: { bar: "bg-action", label: "text-action" },
};

export interface QuestionCardProps {
  tone: QuestionTone;
  label: string;
  question: string;
  description: string;
}

export function QuestionCard({ tone, label, question, description }: QuestionCardProps) {
  const classes = toneClasses[tone];
  return (
    <li className="relative overflow-hidden rounded-2xl border border-border bg-surface p-6">
      <span aria-hidden="true" className={`absolute inset-x-0 top-0 h-1 ${classes.bar}`} />
      <p className={`text-xs font-semibold tracking-wider uppercase ${classes.label}`}>{label}</p>
      <h3 className="mt-3 text-lg leading-snug font-semibold">{question}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>
    </li>
  );
}
