import type { EvidenceType, MatchReason, NodeType } from "@/lib/api/types";
import {
  EVIDENCE_DESCRIPTION,
  EVIDENCE_LABEL,
  MATCH_REASON_LABEL,
  NODE_TYPE_LABEL,
  NODE_TYPE_TONE,
  TONE_BORDER,
  TONE_TEXT,
} from "@/lib/format";

const PILL = "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium";

/** Node type, coloured by role and always spelled out. */
export function TypeBadge({ type }: { type: NodeType }) {
  const tone = NODE_TYPE_TONE[type];
  return (
    <span className={`${PILL} ${TONE_BORDER[tone]} ${TONE_TEXT[tone]}`}>
      {NODE_TYPE_LABEL[type]}
    </span>
  );
}

export function MatchReasonBadge({ reason }: { reason: MatchReason }) {
  return (
    <span className={`${PILL} border-border text-muted`} data-match-reason={reason}>
      {MATCH_REASON_LABEL[reason]}
    </span>
  );
}

/** Evidence type. Inferred reads "Hypothesis" with a dashed outline, so colour is never the only cue. */
export function EvidenceBadge({ type }: { type: EvidenceType }) {
  const style =
    type === "inferred"
      ? "border-dashed border-muted text-muted"
      : type === "observed"
        ? "border-evidence text-evidence"
        : "border-cluster text-cluster";
  return (
    <span className={`${PILL} ${style}`} title={EVIDENCE_DESCRIPTION[type]}>
      {EVIDENCE_LABEL[type]}
    </span>
  );
}

export function ContradictionBadge({ count }: { count: number }) {
  return (
    <span className={`${PILL} border-contradiction text-contradiction`}>
      Contradicted by {count} {count === 1 ? "source" : "sources"}
    </span>
  );
}
