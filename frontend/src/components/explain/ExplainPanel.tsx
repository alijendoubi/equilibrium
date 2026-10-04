"use client";

import { useMemo, useState } from "react";
import { AiGeneratedBadge } from "@/components/AiGeneratedBadge";
import { FallbackNotice } from "@/components/MockBanner";
import { EdgePanel } from "@/components/path/EdgePanel";
import { getAtlasClient, type AtlasClient } from "@/lib/api/client";
import { explanationToText } from "@/lib/api/explain-template";
import type { AtlasNode, Edge, ExplainAudience, ExplainResponse } from "@/lib/api/types";

export const TEMPLATE_LABEL = "Template (AI unavailable)";

const AUDIENCES: { value: ExplainAudience; label: string }[] = [
  { value: "family", label: "For families" },
  { value: "researcher", label: "For researchers" },
];

interface ExplainPanelProps {
  /** Edge ids to explain, in path order. */
  edgeIds: string[];
  /** Edges and nodes already on the page, so a cited edge chip can open its evidence. */
  edges: Edge[];
  nodes: AtlasNode[];
  triggerLabel: string;
  /** Heading of the result and first line of the copied text. */
  title: string;
  /** Injected in tests; defaults to the configured client (mock or live with fallback). */
  getClient?: () => AtlasClient;
}

type Status = "idle" | "loading" | "done" | "error";

/** Neutral label when the text came from the deterministic template, not a model. */
export function SourceLabel({ explanation }: { explanation: ExplainResponse }) {
  if (explanation.ai_generated) return <AiGeneratedBadge model={explanation.model} />;
  return (
    <span className="inline-flex items-center rounded-full border border-border px-2 py-0.5 text-xs font-medium text-muted">
      {TEMPLATE_LABEL}
    </span>
  );
}

/** Calls explain() on demand and renders cited steps; each edge chip opens its evidence. */
export function ExplainPanel({
  edgeIds,
  edges,
  nodes,
  triggerLabel,
  title,
  getClient = getAtlasClient,
}: ExplainPanelProps) {
  const [status, setStatus] = useState<Status>("idle");
  const [audience, setAudience] = useState<ExplainAudience>("family");
  const [explanation, setExplanation] = useState<ExplainResponse | null>(null);
  const [usedFallback, setUsedFallback] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const edgeById = useMemo(() => new Map(edges.map((e) => [e.id, e])), [edges]);
  const nodesById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  async function run(nextAudience: ExplainAudience) {
    setAudience(nextAudience);
    setStatus("loading");
    setError(null);
    setCopied(false);
    const client = getClient();
    try {
      const result = await client.explain(edgeIds, nextAudience);
      setExplanation(result);
      setUsedFallback(client.usedFallback);
      setStatus("done");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The explanation could not be loaded.");
      setStatus("error");
    }
  }

  async function copy() {
    if (!explanation) return;
    try {
      await navigator.clipboard.writeText(explanationToText(title, explanation));
      setCopied(true);
    } catch {
      setError("Copy failed. Select the text and copy it by hand.");
    }
  }

  if (status === "idle") {
    return (
      <button
        type="button"
        onClick={() => run(audience)}
        disabled={edgeIds.length === 0}
        className="rounded-xl border border-action px-3 py-1.5 text-sm font-medium text-action hover:bg-background disabled:opacity-50"
      >
        {triggerLabel}
      </button>
    );
  }

  const selectedEdge = selectedEdgeId ? (edgeById.get(selectedEdgeId) ?? null) : null;

  return (
    <section
      aria-label={title}
      aria-busy={status === "loading"}
      className="mt-2 rounded-2xl border border-border bg-surface p-4 text-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">{title}</h3>
        <div role="group" aria-label="Audience" className="flex gap-1">
          {AUDIENCES.map((a) => (
            <button
              key={a.value}
              type="button"
              aria-pressed={audience === a.value}
              onClick={() => run(a.value)}
              className={`rounded-lg border px-2 py-1 text-xs ${
                audience === a.value ? "border-focus font-medium" : "border-border text-muted"
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>

      {status === "loading" && <p className="mt-3 text-muted">Writing the explanation…</p>}
      {status === "error" && (
        <p role="alert" className="mt-3 text-contradiction">
          {error}
        </p>
      )}

      {status === "done" && explanation && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <SourceLabel explanation={explanation} />
            {explanation.source === "cache" && (
              <span className="text-xs text-muted">saved answer</span>
            )}
          </div>
          <FallbackNotice show={usedFallback} />
          <p>{explanation.summary}</p>
          <ol className="space-y-2">
            {explanation.steps.map((step, i) => (
              <li
                key={`${i}-${step.edge_ids.join("-")}`}
                data-hypothesis={step.is_hypothesis}
                className={`rounded-xl border-2 p-3 ${
                  step.is_hypothesis ? "border-dashed border-muted" : "border-solid border-border"
                }`}
              >
                {step.is_hypothesis && (
                  <span className="mb-1 block text-xs font-medium text-muted italic">
                    hypothesis
                  </span>
                )}
                <p>{step.text}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {step.edge_ids.map((id) => (
                    <button
                      key={id}
                      type="button"
                      aria-pressed={selectedEdgeId === id}
                      aria-label={`Show evidence for ${id}`}
                      onClick={() => setSelectedEdgeId(id)}
                      className="rounded-full border border-border px-2 py-0.5 font-mono text-xs text-muted hover:border-cluster"
                    >
                      {id}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ol>
          {selectedEdgeId &&
            (selectedEdge ? (
              <EdgePanel edge={selectedEdge} nodesById={nodesById} />
            ) : (
              <p className="text-xs text-muted">
                Evidence for {selectedEdgeId} is not loaded on this page.
              </p>
            ))}
          {explanation.caveats.length > 0 && (
            <div>
              <p className="text-xs font-semibold tracking-wider text-muted uppercase">Caveats</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-muted">
                {explanation.caveats.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={copy}
              className="rounded-lg border border-border px-2 py-1 text-xs hover:border-cluster"
            >
              Copy text
            </button>
            {copied && (
              <span role="status" className="text-xs text-muted">
                Copied
              </span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
