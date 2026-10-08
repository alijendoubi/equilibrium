"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { MatchReasonBadge, TypeBadge } from "@/components/Badges";
import { EvidenceMap } from "@/components/graph/EvidenceMap";
import { NODE_TYPE_PLURAL } from "@/components/graph/map-style";
import { DataNotice } from "@/components/MockBanner";
import type { SearchResult } from "@/lib/api/types";
import { NODE_TYPE_LABEL, actionsHref, nodeHref, searchHref } from "@/lib/format";
import { mapHref } from "@/lib/graph-map";
import { summarizeTrace, type TraceResult, type TraceSummary } from "@/lib/trace-result";

const BUTTON =
  "inline-flex items-center gap-2 rounded-full border border-border px-4 py-2 text-sm font-semibold hover:border-cluster focus-visible:outline-2 focus-visible:outline-focus";
const PRIMARY =
  "inline-flex items-center gap-2 rounded-full bg-cluster px-4 py-2 text-sm font-semibold text-background hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

export interface TraceResultViewProps {
  result: Exclude<TraceResult, { status: "invalid" }>;
  /** Id of the alternative being loaded, so its chip can say so. */
  pendingId: string | null;
  onPick: (alternative: SearchResult) => void;
  onRetry: () => void;
  onReset: () => void;
}

function describeMap(summary: TraceSummary): string {
  if (summary.links === 0) return "No direct links in the atlas yet.";
  const parts = summary.neighbours
    .slice(0, 4)
    .map(({ type, count }) =>
      `${count} ${count === 1 ? NODE_TYPE_LABEL[type] : NODE_TYPE_PLURAL[type]}`.toLowerCase(),
    );
  const links = `${summary.links} sourced ${summary.links === 1 ? "link" : "links"}`;
  const red =
    summary.contradictions > 0 ? ` · ${summary.contradictions} contradicted, drawn in red` : "";
  return `${links} to ${parts.join(", ")}${red}.`;
}

/** What the "Trace it" flow found: the real depth-1 evidence map, or an honest dead end. */
export function TraceResultView({
  result,
  pendingId,
  onPick,
  onRetry,
  onReset,
}: TraceResultViewProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const key = result.status === "found" ? result.match.node.id : result.status;
  useEffect(() => headingRef.current?.focus(), [key]);

  const newSearch = (
    <button type="button" onClick={onReset} className={BUTTON}>
      New search
    </button>
  );

  if (result.status === "error") {
    return (
      <div className="mt-6 text-center" role="alert">
        <h2 ref={headingRef} tabIndex={-1} className="text-2xl font-semibold outline-none">
          Could not trace &ldquo;{result.query}&rdquo;
        </h2>
        <p className="mt-2 text-muted">{result.message}</p>
        <div className="mt-6 flex justify-center gap-3">
          <button type="button" onClick={onRetry} className={PRIMARY}>
            Try again
          </button>
          {newSearch}
        </div>
      </div>
    );
  }

  if (result.status === "not_found") {
    return (
      <div className="mt-6 text-center">
        <DataNotice isMock={result.isMock} usedFallback={result.usedFallback} />
        <h2 ref={headingRef} tabIndex={-1} className="mt-6 text-2xl font-semibold outline-none">
          Nothing in the atlas matches &ldquo;{result.query}&rdquo;
        </h2>
        <p className="mx-auto mt-2 max-w-lg text-sm text-muted">
          We searched {result.searched.join(", ") || "the atlas snapshot"}. A missing match is a
          coverage gap, not proof that no work exists.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {newSearch}
          <Link href="/map" className={BUTTON}>
            Browse the evidence map
          </Link>
        </div>
      </div>
    );
  }

  const { match, alternatives, graph, query } = result;
  const node = match.node;
  const summary = graph ? summarizeTrace(graph) : null;
  const showMatched = match.match_reason !== "exact" && match.matched_text !== node.label;

  return (
    <div className="mt-6 w-full text-left">
      <DataNotice isMock={result.isMock} usedFallback={result.usedFallback} />
      <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <p className="text-sm font-medium text-cluster">Evidence map · direct links</p>
          <h2
            ref={headingRef}
            tabIndex={-1}
            className="mt-1 text-3xl font-semibold tracking-tight outline-none"
          >
            {node.label}
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
            <TypeBadge type={node.type} />
            <MatchReasonBadge reason={match.match_reason} />
            {showMatched && <span>Matched on: {match.matched_text}</span>}
          </div>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            {summary
              ? describeMap(summary)
              : "This entry is in the atlas, but it is not on the evidence map yet."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {newSearch}
          <Link href={nodeHref(node.id)} className={BUTTON}>
            Open {node.type === "disease" ? "disease" : "node"} page
          </Link>
          {node.type === "disease" && (
            <Link href={actionsHref(node.id)} className={BUTTON}>
              What to do next
            </Link>
          )}
          <Link href={mapHref({ center: node.id })} className={PRIMARY}>
            Open full map <span aria-hidden="true">→</span>
          </Link>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
        {alternatives.length > 0 && <span className="text-muted">Not what you meant?</span>}
        {alternatives.map((alt) => (
          <button
            key={alt.node.id}
            type="button"
            disabled={pendingId !== null}
            onClick={() => onPick(alt)}
            title={alt.node.label}
            className="max-w-[18rem] truncate rounded-full border border-border px-3 py-1 hover:border-cluster disabled:opacity-60"
          >
            {pendingId === alt.node.id ? `Loading ${alt.node.label}…` : alt.node.label}
          </button>
        ))}
        <Link href={searchHref(query)} className="text-cluster underline-offset-4 hover:underline">
          See all matches
        </Link>
      </div>

      {graph && (
        <div className="mt-6">
          <EvidenceMap key={node.id} graph={graph} state={{ center: node.id }} compact />
        </div>
      )}
    </div>
  );
}
