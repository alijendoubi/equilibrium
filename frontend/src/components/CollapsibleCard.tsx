import type { ReactNode } from "react";
import { TONE_BG, TONE_TEXT, type Tone } from "@/lib/format";

interface CollapsibleCardProps {
  tone: Tone;
  /** Short label shown above the title, e.g. "Cluster". Colour never carries meaning alone. */
  label: string;
  title: string;
  summary?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

/** Progressive reveal: native <details>, so it is keyboard and screen-reader friendly with no JS. */
export function CollapsibleCard({
  tone,
  label,
  title,
  summary,
  defaultOpen = false,
  children,
}: CollapsibleCardProps) {
  return (
    <details
      open={defaultOpen}
      className="group relative overflow-hidden rounded-2xl border border-border bg-surface"
    >
      <span aria-hidden="true" className={`absolute inset-y-0 left-0 w-1 ${TONE_BG[tone]}`} />
      <summary className="flex cursor-pointer list-none items-start justify-between gap-4 p-5 pl-6 [&::-webkit-details-marker]:hidden">
        <span>
          <span
            className={`block text-xs font-semibold tracking-wider uppercase ${TONE_TEXT[tone]}`}
          >
            {label}
          </span>
          <span className="mt-1 block text-lg font-semibold">{title}</span>
          {summary && <span className="mt-1 block text-sm text-muted">{summary}</span>}
        </span>
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          className="mt-1 size-5 shrink-0 text-muted transition-transform group-open:rotate-180"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.75"
        >
          <path d="m5 8 5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="border-t border-border p-5 pl-6">{children}</div>
    </details>
  );
}
