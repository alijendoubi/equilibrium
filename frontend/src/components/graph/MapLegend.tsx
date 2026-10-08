import type { NodeType } from "@/lib/api/types";
import { NODE_TYPE_LABEL } from "@/lib/format";
import { DASH, NODE_SHAPE_NAME, nodeColor, shapePath } from "./map-style";

function Swatch({ type }: { type: NodeType }) {
  return (
    <svg width="22" height="22" viewBox="-11 -11 22 22" aria-hidden="true" className="shrink-0">
      <path d={shapePath(type, 7)} style={{ fill: nodeColor(type) }} />
    </svg>
  );
}

function Line({ kind }: { kind: "data" | "hypothesis" | "contradiction" | "highlight" }) {
  const stroke =
    kind === "contradiction"
      ? "var(--contradiction)"
      : kind === "highlight"
        ? "var(--focus)"
        : "var(--muted)";
  return (
    <svg width="40" height="14" viewBox="0 0 40 14" aria-hidden="true" className="shrink-0">
      <line
        x1="2"
        y1="7"
        x2="32"
        y2="7"
        style={{ stroke }}
        strokeWidth={kind === "highlight" ? 4 : 2.5}
        strokeDasharray={kind === "hypothesis" ? DASH : undefined}
      />
      <path d="M31,3 L38,7 L31,11 Z" style={{ fill: stroke }} />
    </svg>
  );
}

interface MapLegendProps {
  types: NodeType[];
  showHighlight?: boolean;
  compact?: boolean;
}

/** Explains shapes, colours and line styles in words, so nothing depends on colour alone. */
export function MapLegend({ types, showHighlight = false, compact = false }: MapLegendProps) {
  return (
    <section
      aria-label="Map legend"
      className="rounded-2xl border border-border bg-surface p-4 text-xs leading-relaxed"
    >
      <h3 className="text-[0.7rem] font-semibold tracking-wider text-muted uppercase">Legend</h3>
      <ul className={`mt-3 grid gap-x-4 gap-y-1.5 ${compact ? "grid-cols-2" : "sm:grid-cols-2"}`}>
        {types.map((type) => (
          <li key={type} className="flex items-center gap-2">
            <Swatch type={type} />
            <span>
              <span className="font-medium">{NODE_TYPE_LABEL[type]}</span>
              <span className="text-muted"> · {NODE_SHAPE_NAME[type]}</span>
            </span>
          </li>
        ))}
      </ul>
      <ul className="mt-3 space-y-1.5 border-t border-border pt-3">
        <li className="flex items-center gap-2">
          <Line kind="data" />
          <span>Solid line: data (observed or curated, with a source)</span>
        </li>
        <li className="flex items-center gap-2">
          <Line kind="hypothesis" />
          <span>Dashed line: hypothesis (inferred by our pipeline)</span>
        </li>
        <li className="flex items-center gap-2">
          <Line kind="contradiction" />
          <span>
            Red line with a <span className="font-medium text-contradiction">contradicts</span> or{" "}
            <span className="font-medium text-contradiction">contested</span> badge: sources
            disagree
          </span>
        </li>
        {showHighlight && (
          <li className="flex items-center gap-2">
            <Line kind="highlight" />
            <span>Thick blue line: the route you came from</span>
          </li>
        )}
      </ul>
      {!compact && (
        <p className="mt-3 border-t border-border pt-3 text-muted">
          Arrows point from subject to object (a disease is <em>caused by</em> a gene). Thicker
          lines mean higher confidence; bigger shapes have more links on this map. Teal: biology
          (who shares this). Amber: existing work. Violet: people and organisations.
        </p>
      )}
    </section>
  );
}
