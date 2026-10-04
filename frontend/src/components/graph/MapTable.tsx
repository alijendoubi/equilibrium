import type { Edge, MapNode } from "@/lib/api/types";
import { EVIDENCE_LABEL, NODE_TYPE_LABEL, formatConfidence, relationLabel } from "@/lib/format";
import { contradictionBadge } from "./map-style";

interface MapTableProps {
  nodes: MapNode[];
  edges: Edge[];
  labelOf: (id: string) => string;
  contradictionIds: ReadonlySet<string>;
  onSelectNode: (id: string) => void;
  onSelectEdge: (id: string) => void;
}

const TH = "px-3 py-2 text-left text-[0.7rem] font-semibold tracking-wider text-muted uppercase";
const TD = "px-3 py-2 align-top";

/** The same nodes and links as the drawing, as two tables (screen readers, keyboards, printing). */
export function MapTable({
  nodes,
  edges,
  labelOf,
  contradictionIds,
  onSelectNode,
  onSelectEdge,
}: MapTableProps) {
  return (
    <div className="space-y-6">
      <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
        <table className="w-full text-sm">
          <caption className="px-3 pt-3 text-left text-sm font-semibold">
            Nodes on the map ({nodes.length})
          </caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className={TH}>
                Name
              </th>
              <th scope="col" className={TH}>
                Type
              </th>
              <th scope="col" className={TH}>
                Links shown
              </th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((n) => (
              <tr key={n.node.id} className="border-b border-border last:border-0">
                <th scope="row" className={`${TD} font-medium`}>
                  <button
                    type="button"
                    onClick={() => onSelectNode(n.node.id)}
                    className="text-left underline-offset-4 hover:underline"
                  >
                    {n.node.label}
                  </button>
                </th>
                <td className={TD}>{NODE_TYPE_LABEL[n.node.type]}</td>
                <td className={TD}>
                  {n.degree} <span className="text-muted">of {n.total_degree}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
        <table className="w-full text-sm">
          <caption className="px-3 pt-3 text-left text-sm font-semibold">
            Links on the map ({edges.length})
          </caption>
          <thead>
            <tr className="border-b border-border">
              <th scope="col" className={TH}>
                From
              </th>
              <th scope="col" className={TH}>
                Relation
              </th>
              <th scope="col" className={TH}>
                To
              </th>
              <th scope="col" className={TH}>
                Evidence
              </th>
              <th scope="col" className={TH}>
                Confidence
              </th>
              <th scope="col" className={TH}>
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {edges.map((e) => (
              <tr key={e.id} className="border-b border-border last:border-0">
                <td className={TD}>{labelOf(e.source_id)}</td>
                <td className={`${TD} text-muted`}>
                  {relationLabel(e.relation)}
                  {contradictionIds.has(e.id) && (
                    <span className="ml-2 rounded-full border border-contradiction px-2 py-0.5 text-xs font-medium text-contradiction">
                      {contradictionBadge(e)}
                    </span>
                  )}
                </td>
                <td className={TD}>{labelOf(e.target_id)}</td>
                <td className={TD}>{EVIDENCE_LABEL[e.evidence_type]}</td>
                <td className={TD}>{formatConfidence(e.confidence)}</td>
                <td className={TD}>
                  <button
                    type="button"
                    onClick={() => onSelectEdge(e.id)}
                    className="text-cluster underline-offset-4 hover:underline"
                  >
                    Evidence
                    <span className="sr-only">
                      {" "}
                      for {labelOf(e.source_id)} {relationLabel(e.relation)} {labelOf(e.target_id)}
                    </span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
