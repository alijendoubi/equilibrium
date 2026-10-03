import { EvidenceBadge } from "@/components/Badges";
import { NodeChip } from "@/components/NodeChip";
import type { DiseaseSummary, LinkedNode } from "@/lib/disease-summary";

function Row({ label, items, empty }: { label: string; items: LinkedNode[]; empty: string }) {
  return (
    <div className="grid gap-2 sm:grid-cols-[8rem_1fr]">
      <dt className="pt-1 text-sm text-muted">{label}</dt>
      <dd>
        {items.length === 0 ? (
          <span className="text-sm text-muted">{empty}</span>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {items.map(({ node, edge }) => (
              <li key={node.id} className="flex items-center gap-1">
                <NodeChip node={node} />
                {edge.evidence_type === "inferred" && <EvidenceBadge type="inferred" />}
              </li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  );
}

/** Summary first: cause, top symptoms (most informative first), mechanism. */
export function SummaryCard({ summary }: { summary: DiseaseSummary }) {
  return (
    <section aria-label="Summary" className="rounded-2xl border border-border bg-surface p-6">
      <dl className="space-y-4">
        <Row label="Cause" items={summary.causes} empty="No causal gene recorded" />
        <Row label="Top symptoms" items={summary.phenotypes} empty="No symptoms recorded" />
        <Row label="Mechanism" items={summary.mechanisms} empty="No mechanism recorded" />
      </dl>
    </section>
  );
}
