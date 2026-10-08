import { sourceCitation } from "@/lib/api/explain-template";
import Link from "next/link";
import { EvidenceBadge, TypeBadge } from "@/components/Badges";
import type { Edge, MapNode } from "@/lib/api/types";
import { clusterHref, displayId, formatConfidence, nodeHref, relationLabel } from "@/lib/format";
import { mapHref, type MapParams } from "@/lib/graph-map";
import { contradictionBadge } from "./map-style";

const DESCRIPTION_LIMIT = 260;
const ACTION =
  "inline-flex items-center justify-center rounded-xl border px-3 py-1.5 text-xs font-medium hover:bg-background";

interface MapNodePanelProps {
  item: MapNode;
  edges: Edge[];
  labelOf: (id: string) => string;
  contradictionIds: ReadonlySet<string>;
  state: MapParams;
  onSelectEdge: (id: string) => void;
  onClose: () => void;
}

/** What a clicked node is, how it is connected here, and where to go next. */
export function MapNodePanel({
  item,
  edges,
  labelOf,
  contradictionIds,
  state,
  onSelectEdge,
  onClose,
}: MapNodePanelProps) {
  const { node } = item;
  const description = node.attributes.description;
  const mine = edges.filter((e) => e.source_id === node.id || e.target_id === node.id);
  const expand = [...new Set([...(state.expand ?? []), node.id])];
  const isCenter = state.center === node.id;

  return (
    <aside
      aria-label="Node details"
      aria-live="polite"
      className="rounded-2xl border border-border bg-surface p-5 text-sm"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <TypeBadge type={node.type} />
          <span className="text-xs text-muted">{displayId(node.id)}</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg px-2 text-muted hover:bg-background"
          aria-label="Close details"
        >
          ×
        </button>
      </div>
      <h2 className="mt-2 text-base leading-snug font-semibold">{node.label}</h2>
      {description && (
        <p className="mt-2 text-xs leading-relaxed text-muted">
          {description.length > DESCRIPTION_LIMIT
            ? `${description.slice(0, DESCRIPTION_LIMIT).trimEnd()}…`
            : description}
        </p>
      )}
      <p className="mt-3 text-xs text-muted">
        {item.degree} {item.degree === 1 ? "link" : "links"} on this map · {item.total_degree} in
        the atlas
        {item.cluster_id && (
          <>
            {" · "}
            <Link href={clusterHref(item.cluster_id)} className="text-cluster hover:underline">
              its cluster
            </Link>
          </>
        )}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <Link href={nodeHref(node.id)} className={`${ACTION} border-cluster text-cluster`}>
          {node.type === "disease" ? "Open disease page" : "Open page"}
        </Link>
        {!isCenter && (
          <Link href={mapHref({ center: node.id })} className={`${ACTION} border-border`}>
            Center map here
          </Link>
        )}
        <Link
          href={mapHref({ ...state, center: state.center ?? null, expand })}
          className={`${ACTION} border-border`}
        >
          Expand neighbours
        </Link>
      </div>

      {mine.length > 0 && (
        <section aria-label="Links on this map" className="mt-5">
          <h3 className="text-[0.7rem] font-semibold tracking-wider text-muted uppercase">
            Links on this map ({mine.length})
          </h3>
          <ul className="mt-2 max-h-72 space-y-1 overflow-y-auto pr-1">
            {mine.map((edge) => {
              const outgoing = edge.source_id === node.id;
              const other = labelOf(outgoing ? edge.target_id : edge.source_id);
              return (
                <li key={edge.id}>
                  <button
                    type="button"
                    onClick={() => onSelectEdge(edge.id)}
                    className="flex w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-background"
                  >
                    <span className="text-muted">
                      {outgoing
                        ? relationLabel(edge.relation)
                        : `${relationLabel(edge.relation)} ←`}
                    </span>
                    <span className="font-medium">{other}</span>
                    <EvidenceBadge type={edge.evidence_type} />
                    <span className="text-muted">{sourceCitation(edge.provenance)}</span>
                    {contradictionIds.has(edge.id) && (
                      <span className="rounded-full border border-contradiction px-2 py-0.5 font-medium text-contradiction">
                        {contradictionBadge(edge)}
                      </span>
                    )}
                    <span className="ml-auto text-muted">
                      {formatConfidence(edge.confidence)}
                      <span className="sr-only">. Show evidence.</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </aside>
  );
}
