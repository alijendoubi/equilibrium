import { ContradictionBadge, EvidenceBadge } from "@/components/Badges";
import type { AtlasNode, Edge } from "@/lib/api/types";
import { EVIDENCE_DESCRIPTION, formatConfidence, formatDate, relationLabel } from "@/lib/format";

interface EdgePanelProps {
  edge: Edge | null;
  nodesById: Map<string, AtlasNode>;
}

/** Side panel: who says so, how sure we are, and whether it is observed, curated or inferred. */
export function EdgePanel({ edge, nodesById }: EdgePanelProps) {
  if (!edge) {
    return (
      <aside aria-label="Edge evidence" className="rounded-2xl border border-border p-5 text-sm">
        <p className="text-muted">Select a link in the chain to see its evidence.</p>
      </aside>
    );
  }
  const source = nodesById.get(edge.source_id)?.label ?? edge.source_id;
  const target = nodesById.get(edge.target_id)?.label ?? edge.target_id;
  const p = edge.provenance;

  return (
    <aside
      aria-label="Edge evidence"
      aria-live="polite"
      className="rounded-2xl border border-border bg-surface p-5 text-sm"
    >
      <h2 className="font-semibold">
        {source} <span className="font-normal text-muted">{relationLabel(edge.relation)}</span>{" "}
        {target}
      </h2>
      <div className="mt-2 flex flex-wrap gap-2">
        <EvidenceBadge type={edge.evidence_type} />
        {edge.contradicted_by.length > 0 && (
          <ContradictionBadge count={edge.contradicted_by.length} />
        )}
        {edge.relation === "contradicts" && (
          <span className="inline-flex items-center rounded-full border border-contradiction px-2 py-0.5 text-xs font-medium text-contradiction">
            Contradicting evidence
          </span>
        )}
      </div>
      <p className="mt-2 text-xs text-muted">{EVIDENCE_DESCRIPTION[edge.evidence_type]}</p>

      <dl className="mt-4 grid grid-cols-[7rem_1fr] gap-x-3 gap-y-2">
        <dt className="text-muted">Source</dt>
        <dd>
          {p.url ? (
            <a
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-cluster underline underline-offset-4"
            >
              {p.source} · {p.source_record_id}
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          ) : (
            <span>
              {p.source} · {p.source_record_id}
            </span>
          )}
        </dd>
        <dt className="text-muted">Retrieved</dt>
        <dd>
          <time dateTime={p.retrieved_at}>{formatDate(p.retrieved_at)}</time>
        </dd>
        <dt className="text-muted">Confidence</dt>
        <dd>
          <span className="font-medium">{formatConfidence(edge.confidence)}</span>
          {edge.confidence_reasons.length > 0 && (
            <ul className="mt-1 list-disc pl-4 text-xs text-muted">
              {edge.confidence_reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          )}
        </dd>
        {p.source_version && (
          <>
            <dt className="text-muted">Source version</dt>
            <dd>{p.source_version}</dd>
          </>
        )}
        {p.extractor && (
          <>
            <dt className="text-muted">Extracted by</dt>
            <dd>{p.extractor}</dd>
          </>
        )}
        {p.supporting_edge_ids.length > 0 && (
          <>
            <dt className="text-muted">Derived from</dt>
            <dd className="text-xs">{p.supporting_edge_ids.join(", ")}</dd>
          </>
        )}
        {Object.entries(edge.qualifiers).map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k.replaceAll("_", " ")}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>

      {p.evidence_quote && (
        <figure className="mt-4">
          <blockquote className="border-l-2 border-evidence pl-3 italic">
            &ldquo;{p.evidence_quote}&rdquo;
          </blockquote>
          <figcaption className="mt-1 text-xs text-muted">
            Quote from {p.source_record_id}
          </figcaption>
        </figure>
      )}
      <p className="mt-4 text-xs text-muted">Edge id: {edge.id}</p>
    </aside>
  );
}
