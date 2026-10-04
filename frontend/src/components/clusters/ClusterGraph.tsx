import type { ClusterDetail } from "@/lib/api/types";
import { GRAPH_SIZE, layoutCluster } from "@/lib/cluster-layout";
import { nodeHref } from "@/lib/format";

const LABEL_GAP = 12;
const PAD_X = 110;
const PAD_Y = 24;

/**
 * Small SVG graph of one cluster: members on the inner circle (filled), diseases from other
 * clusters on the outer ring (hollow, labelled with their cluster), solid links within the
 * cluster and dashed bridges. Every node is a keyboard-focusable link to its disease page.
 */
export function ClusterGraph({ detail }: { detail: ClusterDetail }) {
  const layout = layoutCluster(detail);
  const titleId = `cluster-graph-title-${detail.id}`;
  const descId = `cluster-graph-desc-${detail.id}`;
  const bridges = layout.edges.filter((e) => e.edge.kind === "bridge").length;

  return (
    <figure className="rounded-2xl border border-border bg-surface p-4">
      <svg
        role="group"
        aria-labelledby={titleId}
        aria-describedby={descId}
        viewBox={`${-PAD_X} ${-PAD_Y} ${GRAPH_SIZE + 2 * PAD_X} ${GRAPH_SIZE + 2 * PAD_Y}`}
        className="h-auto w-full"
      >
        <title id={titleId}>{`Cluster ${detail.id} graph: ${detail.label}`}</title>
        <desc id={descId}>
          {`${detail.size} member diseases (filled circles) and ${layout.nodes.length - detail.size} diseases from other clusters (hollow circles). Solid lines join similar members; ${bridges} dashed lines are bridges to other clusters.`}
        </desc>
        <g>
          {layout.edges.map(({ edge, source, target }) => (
            <line
              key={`${edge.kind}:${edge.source_id}:${edge.target_id}`}
              data-kind={edge.kind}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke={edge.kind === "bridge" ? "var(--muted)" : source.color}
              strokeWidth={1 + 3 * edge.score}
              strokeDasharray={edge.kind === "bridge" ? "6 5" : undefined}
              strokeOpacity={0.75}
            >
              <title>
                {`${edge.kind === "bridge" ? "Bridge" : "Similar"} (score ${edge.score.toFixed(2)}): ${edge.reasons.join("; ")}`}
              </title>
            </line>
          ))}
        </g>
        <g>
          {layout.nodes.map(({ item, x, y, r, color, shortLabel }) => {
            const where = item.is_member ? "member" : `in cluster ${item.cluster_id}`;
            const name = `${item.node.label} (${where}, ${item.degree} similarity links)`;
            return (
              <a key={item.node.id} href={nodeHref(item.node.id)} aria-label={name}>
                <title>{name}</title>
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={item.is_member ? color : "var(--surface)"}
                  stroke={color}
                  strokeWidth={item.is_member ? 1 : 2.5}
                />
                <text
                  x={x}
                  y={y + r + LABEL_GAP}
                  textAnchor="middle"
                  fontSize={11}
                  fill="var(--foreground)"
                >
                  {item.is_member ? shortLabel : `${shortLabel} (${item.cluster_id})`}
                </text>
              </a>
            );
          })}
        </g>
      </svg>
      <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <span>Filled circle: member of {detail.id}</span>
        <span>Hollow circle: disease in another cluster (cluster shown in brackets)</span>
        <span>Solid line: similar within the cluster</span>
        <span>Dashed line: bridge to another cluster</span>
        <span>Bigger circle: more similarity links</span>
        {layout.hidden > 0 && <span>{layout.hidden} more diseases listed below</span>}
      </figcaption>
    </figure>
  );
}
