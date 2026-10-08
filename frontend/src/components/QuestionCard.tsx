import Link from "next/link";

export type QuestionTone = "cluster" | "evidence" | "action";

const toneClasses: Record<QuestionTone, { bar: string; label: string; ring: string }> = {
  cluster: { bar: "bg-cluster", label: "text-cluster", ring: "hover:border-cluster" },
  evidence: { bar: "bg-evidence", label: "text-evidence", ring: "hover:border-evidence" },
  action: { bar: "bg-action", label: "text-action", ring: "hover:border-action" },
};

export interface QuestionCardProps {
  tone: QuestionTone;
  label: string;
  question: string;
  description: string;
  /** Where the question is answered; the whole card links there. */
  href?: string;
  /** Call to action under the description, e.g. "Open the evidence map". */
  cta?: string;
  index?: number;
}

export function QuestionCard({
  tone,
  label,
  question,
  description,
  href,
  cta,
  index,
}: QuestionCardProps) {
  const classes = toneClasses[tone];
  const body = (
    <>
      <span aria-hidden="true" className={`absolute inset-x-0 top-0 h-1 ${classes.bar}`} />
      <p
        className={`flex items-baseline justify-between text-xs font-semibold tracking-wider uppercase ${classes.label}`}
      >
        {label}
        {index !== undefined && (
          <span aria-hidden="true" className="font-mono text-muted">
            {String(index).padStart(2, "0")}
          </span>
        )}
      </p>
      <h3 className="mt-3 text-lg leading-snug font-semibold">{question}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>
      {cta && (
        <p className={`mt-auto pt-5 text-sm font-medium ${classes.label}`}>
          {cta}{" "}
          <span
            aria-hidden="true"
            className="inline-block motion-safe:transition-transform motion-safe:group-hover:translate-x-0.5"
          >
            →
          </span>
        </p>
      )}
    </>
  );
  const frame =
    "relative flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface p-6";
  return (
    <li>
      {href ? (
        <Link href={href} className={`group ${frame} shadow-sm transition-colors ${classes.ring}`}>
          {body}
        </Link>
      ) : (
        <div className={frame}>{body}</div>
      )}
    </li>
  );
}
