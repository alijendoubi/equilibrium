import type { NodeType } from "@/lib/api/types";
import { DASH, nodeColor, shapePath } from "./map-style";

/** Illustration for the home page, drawn with the evidence map's own shapes and line styles. */

interface MotifNode {
  id: string;
  type: NodeType;
  label: string;
  x: number;
  y: number;
  r: number;
}

const NODES: MotifNode[] = [
  { id: "gd2", type: "disease", label: "Gaucher type II", x: 90, y: 70, r: 14 },
  { id: "gd3", type: "disease", label: "Gaucher type III", x: 70, y: 200, r: 13 },
  { id: "gba1", type: "gene", label: "GBA1", x: 220, y: 135, r: 15 },
  { id: "lyso", type: "mechanism", label: "lysosomal breakdown", x: 250, y: 255, r: 11 },
  { id: "pd", type: "disease", label: "late-onset Parkinson", x: 370, y: 85, r: 14 },
  { id: "cure", type: "funder", label: "Cure Parkinson's", x: 470, y: 185, r: 11 },
  { id: "aspro", type: "study", label: "ASPro-PD", x: 395, y: 275, r: 9 },
  { id: "igaa", type: "patient_group", label: "Gaucher Alliance", x: 205, y: 22, r: 10 },
];

type Kind = "data" | "hypothesis" | "contradiction";
const EDGES: { from: string; to: string; kind: Kind; w: number }[] = [
  { from: "gd2", to: "gba1", kind: "data", w: 3.6 },
  { from: "gd3", to: "gba1", kind: "data", w: 3.6 },
  { from: "gba1", to: "pd", kind: "data", w: 3.2 },
  { from: "gba1", to: "lyso", kind: "data", w: 2.8 },
  { from: "pd", to: "lyso", kind: "hypothesis", w: 2.2 },
  { from: "cure", to: "pd", kind: "data", w: 2 },
  { from: "cure", to: "aspro", kind: "data", w: 2 },
  { from: "aspro", to: "gd3", kind: "contradiction", w: 2.4 },
  { from: "igaa", to: "gd2", kind: "data", w: 2 },
];

const byId = new Map(NODES.map((n) => [n.id, n]));

export function MapMotif() {
  return (
    <svg
      viewBox="0 -10 560 320"
      role="img"
      aria-label="Illustration of the evidence map: Gaucher disease types II and III and late-onset Parkinson disease joined through the GBA1 gene, with a funder, a trial, a dashed hypothesis and a red contested link."
      className="evidence-map h-auto w-full"
    >
      {EDGES.map((e) => {
        const a = byId.get(e.from)!;
        const b = byId.get(e.to)!;
        const stroke = e.kind === "contradiction" ? "var(--contradiction)" : "var(--muted)";
        return (
          <g key={`${e.from}-${e.to}`}>
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              style={{ stroke }}
              strokeWidth={e.w}
              strokeLinecap="round"
              strokeDasharray={e.kind === "hypothesis" ? DASH : undefined}
              opacity={e.kind === "data" ? 0.55 : 1}
            />
            {e.kind === "contradiction" && (
              <g transform={`translate(${(a.x + b.x) / 2} ${(a.y + b.y) / 2})`}>
                <rect
                  x={-30}
                  y={-9}
                  width={60}
                  height={18}
                  rx={9}
                  style={{ fill: "var(--surface)", stroke: "var(--contradiction)" }}
                />
                <text
                  textAnchor="middle"
                  dy="0.35em"
                  fontSize={10}
                  fontWeight={600}
                  style={{ fill: "var(--contradiction)" }}
                >
                  contested
                </text>
              </g>
            )}
          </g>
        );
      })}
      {NODES.map((n) => (
        <g key={n.id} transform={`translate(${n.x} ${n.y})`}>
          <path
            d={shapePath(n.type, n.r)}
            style={{ fill: nodeColor(n.type), stroke: "var(--surface)" }}
            strokeWidth={1.5}
          />
          <text
            className="node-label"
            y={n.r + 13}
            textAnchor="middle"
            fontSize={11}
            fontWeight={500}
          >
            {n.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
