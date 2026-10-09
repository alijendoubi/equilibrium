import type { Metadata } from "next";
import Link from "next/link";
import { EvidenceMap } from "@/components/graph/EvidenceMap";
import { DataNotice } from "@/components/MockBanner";
import { PageHeader } from "@/components/PageHeader";
import { getServerAtlasClient } from "@/lib/api/server-client";
import type { GraphMapResponse } from "@/lib/api/types";
import { NODE_TYPE_LABEL, nodeHref } from "@/lib/format";
import { ALL_NODE_TYPES, mapHref, mergeMaps, parseMapParams } from "@/lib/graph-map";

export const metadata: Metadata = { title: "Evidence map · Equilibrium" };

/** Lists of ids (expand, highlight) are longer than a single id, so they get a larger cap. */
const MAX_LIST_PARAM = 2000;

interface MapPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function flatten(params: Record<string, string | string[] | undefined>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(params).map(([key, value]) => [
      key,
      ((Array.isArray(value) ? value[0] : value) ?? "").slice(0, MAX_LIST_PARAM),
    ]),
  );
}

export default async function MapPage({ searchParams }: MapPageProps) {
  const state = parseMapParams(flatten(await searchParams));
  const client = await getServerAtlasClient();
  const base = await client.getGraph({
    center: state.center,
    depth: state.depth,
    types: state.phenotypes ? ALL_NODE_TYPES : undefined,
  });

  if (!base) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-8">
        <PageHeader />
        <h1 className="mt-8 text-2xl font-semibold">Not on the map</h1>
        <p className="mt-2 text-muted">
          {state.center} is not in the atlas snapshot.{" "}
          <Link href="/map" className="text-cluster underline underline-offset-4">
            Open the overview
          </Link>
        </p>
      </main>
    );
  }

  const extras = (
    await Promise.all(state.expand.map((id) => client.getGraph({ center: id })))
  ).filter((m): m is GraphMapResponse => m !== null);
  const graph = mergeMaps(base, extras, new Set(state.highlight));
  const centerNode = base.nodes.find((n) => n.node.id === base.center)?.node ?? null;

  return (
    <main className="mx-auto max-w-7xl px-6 py-8">
      <PageHeader />
      <DataNotice isMock={client.isMock} usedFallback={client.usedFallback} />

      <header className="mt-8 flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold tracking-wider text-cluster uppercase">
            Evidence map
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">
            {centerNode ? centerNode.label : "The Gaucher–Parkinson slice at a glance"}
          </h1>
          <p className="mt-2 leading-relaxed text-muted">
            {centerNode
              ? `Everything within ${state.depth === 2 ? "two hops" : "one hop"} of this ${NODE_TYPE_LABEL[centerNode.type].toLowerCase()}. Every line is a sourced claim: click it to see who says so, when, and how sure we are.`
              : "Diseases, genes, mechanisms, patient groups, funders and the curated trials and papers that connect them. Symptoms, investigators and bulk trials are counted, not drawn; centre the map on a node to see its neighbourhood."}
          </p>
        </div>
        <nav aria-label="Map scope" className="flex flex-wrap gap-2 text-sm">
          {centerNode && (
            <>
              <Link
                href={nodeHref(centerNode.id)}
                className="rounded-xl border border-cluster px-3 py-1.5 font-medium text-cluster hover:bg-surface"
              >
                Open {centerNode.type === "disease" ? "disease" : "node"} page
              </Link>
              <Link
                href={mapHref({ ...state, depth: state.depth === 2 ? 1 : 2, expand: [] })}
                className="rounded-xl border border-border px-3 py-1.5 hover:bg-surface"
              >
                {state.depth === 2 ? "One hop" : "Two hops"}
              </Link>
              <Link
                href="/map"
                className="rounded-xl border border-border px-3 py-1.5 hover:bg-surface"
              >
                Overview
              </Link>
            </>
          )}
          {state.expand.length > 0 && (
            <Link
              href={mapHref({ ...state, expand: [], highlight: [] })}
              className="rounded-xl border border-border px-3 py-1.5 hover:bg-surface"
            >
              Collapse {state.expand.length} expanded
            </Link>
          )}
        </nav>
      </header>

      <div className="mt-6">
        <EvidenceMap graph={graph} state={state} />
      </div>
    </main>
  );
}
