"use client";

import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import { TypeBadge } from "@/components/Badges";
import { ExplainPanel } from "@/components/explain/ExplainPanel";
import { EdgePanel } from "@/components/path/EdgePanel";
import type { ActionsResponse, AtlasNode, Edge } from "@/lib/api/types";
import { nodeHref, pathHref } from "@/lib/format";

export interface ActionPlanProps {
  diseaseLabel: string;
  actions: ActionsResponse;
  /** Every edge loaded for this page (disease edges plus the routes to each partner/asset). */
  edges: Edge[];
  nodes: AtlasNode[];
  /** Target node id -> edge ids of the strongest route from the disease (what the brief explains). */
  briefEdgeIds: Record<string, string[]>;
}

/** "Ambroxol dosing; safety. Adults only." -> ["Ambroxol dosing", "safety.", "Adults only."] */
export function splitPoints(text: string): string[] {
  return text
    .split(/(?<=[.;])\s+/)
    .map((s) => s.replace(/;$/, "").trim())
    .filter((s) => s.length > 0);
}

interface CitedEdgesProps {
  ids: string[];
  known: Map<string, Edge>;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

/** "Why we say so": one chip per cited edge; known edges open the evidence panel. */
function CitedEdges({ ids, known, selectedId, onSelect }: CitedEdgesProps) {
  if (ids.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1 text-xs">
      <span className="text-muted">Cited:</span>
      {ids.map((id) => {
        const edge = known.get(id);
        const dashed = edge?.evidence_type === "inferred";
        return (
          <button
            key={id}
            type="button"
            disabled={!edge}
            aria-pressed={selectedId === id}
            aria-label={`Show evidence for ${id}${dashed ? " (hypothesis)" : ""}`}
            onClick={() => onSelect(id)}
            className={`rounded-full border px-2 py-0.5 font-mono text-muted hover:border-cluster disabled:opacity-50 ${
              dashed ? "border-dashed border-muted" : "border-border"
            }`}
          >
            {id}
          </button>
        );
      })}
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="rounded-2xl border border-border bg-surface p-5">
      <h2 id={id} className="font-semibold">
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

/** Maria's action view: partners, reusable work, what to check, and a brief she can send. */
export function ActionPlan({ diseaseLabel, actions, edges, nodes, briefEdgeIds }: ActionPlanProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const known = useMemo(() => new Map(edges.map((e) => [e.id, e])), [edges]);
  const nodesById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const selected = selectedId ? (known.get(selectedId) ?? null) : null;
  const diseaseId = actions.disease_id;
  const cite = (ids: string[]) => (
    <CitedEdges ids={ids} known={known} selectedId={selectedId} onSelect={setSelectedId} />
  );
  const brief = (target: AtlasNode, fallbackIds: string[]) => (
    <div className="mt-3">
      <ExplainPanel
        edgeIds={briefEdgeIds[target.id] ?? fallbackIds}
        edges={edges}
        nodes={nodes}
        triggerLabel="Draft collaboration brief"
        title={`Collaboration brief: ${diseaseLabel} and ${target.label}`}
      />
    </div>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-6">
        <Section id="partners" title="Who to talk to">
          {actions.partners.length === 0 ? (
            <p className="text-sm text-muted">No partner with a supported link yet.</p>
          ) : (
            <ul className="space-y-5">
              {actions.partners.map((p) => (
                <li key={p.node.id}>
                  <div className="flex flex-wrap items-center gap-2">
                    <TypeBadge type={p.node.type} />
                    <Link href={nodeHref(p.node.id)} className="font-medium hover:underline">
                      {p.node.label}
                    </Link>
                  </div>
                  <p className="mt-1 text-sm">
                    <span className="text-muted">Why: </span>
                    {p.why}
                  </p>
                  {cite(p.edge_ids)}
                  {brief(p.node, p.edge_ids)}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section id="assets" title="What you can reuse">
          {actions.assets.length === 0 ? (
            <p className="text-sm text-muted">No trial, registry or publication is linked yet.</p>
          ) : (
            <ul className="space-y-6">
              {actions.assets.map((a) => (
                <li key={a.node.id}>
                  <div className="flex flex-wrap items-center gap-2">
                    <TypeBadge type={a.node.type} />
                    <Link href={nodeHref(a.node.id)} className="font-medium hover:underline">
                      {a.node.label}
                    </Link>
                  </div>
                  <div className="mt-2 grid gap-3 text-sm sm:grid-cols-2">
                    <div aria-label="Reusable" role="group">
                      <p className="text-xs font-semibold tracking-wider text-evidence uppercase">
                        Reusable
                      </p>
                      <ul className="mt-1 list-disc space-y-1 pl-5">
                        {splitPoints(a.reusable).map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    </div>
                    <div aria-label="What differs" role="group">
                      <p className="text-xs font-semibold tracking-wider text-contradiction uppercase">
                        What differs
                      </p>
                      <ul className="mt-1 list-disc space-y-1 pl-5">
                        {splitPoints(a.differs).map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  {cite(a.edge_ids)}
                  <Link
                    href={pathHref(diseaseId, a.node.id)}
                    className="mt-2 inline-block text-sm font-medium text-cluster underline-offset-4 hover:underline"
                  >
                    See the full connection <span aria-hidden="true">→</span>
                  </Link>
                  {brief(a.node, a.edge_ids)}
                </li>
              ))}
            </ul>
          )}
        </Section>

        {actions.next_experiment && (
          <section
            aria-labelledby="next-experiment"
            data-hypothesis={actions.next_experiment.is_hypothesis}
            className={`rounded-2xl border-2 p-5 ${
              actions.next_experiment.is_hypothesis
                ? "border-dashed border-muted"
                : "border-solid border-border"
            }`}
          >
            <h2 id="next-experiment" className="font-semibold">
              Next experiment
              {actions.next_experiment.is_hypothesis && (
                <span className="ml-2 rounded-full border border-dashed border-muted px-2 py-0.5 text-xs font-medium text-muted italic">
                  hypothesis
                </span>
              )}
            </h2>
            <p className="mt-2 text-sm">{actions.next_experiment.text}</p>
            {cite(actions.next_experiment.edge_ids)}
          </section>
        )}

        {actions.review_checklist.length > 0 && (
          <Section id="checklist" title="Check with an expert before acting">
            <ul className="space-y-2 text-sm">
              {actions.review_checklist.map((q) => (
                <li key={q}>
                  <label className="flex items-start gap-2">
                    <input type="checkbox" className="mt-1" />
                    <span>{q}</span>
                  </label>
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
      <div className="lg:sticky lg:top-6 lg:self-start">
        <EdgePanel edge={selected} nodesById={nodesById} />
      </div>
    </div>
  );
}
