import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EvidenceBadge, TypeBadge } from "@/components/Badges";
import { ActionSections } from "@/components/disease/ActionSections";
import { DiseaseCluster } from "@/components/disease/DiseaseCluster";
import { SummaryCard } from "@/components/disease/SummaryCard";
import { GapCard } from "@/components/GapCard";
import { DataNotice } from "@/components/MockBanner";
import { NodeChip } from "@/components/NodeChip";
import { PageHeader } from "@/components/PageHeader";
import { EvidenceMap } from "@/components/graph/EvidenceMap";
import { getServerAtlasClient } from "@/lib/api/server-client";
import type { GraphMapResponse, NodeSummary } from "@/lib/api/types";
import { mapHref } from "@/lib/graph-map";
import { buildDiseaseSummary } from "@/lib/disease-summary";
import { actionsHref, displayId, pathHref, relationLabel } from "@/lib/format";
import { closestCommunities } from "@/lib/gap";
import { decodeSegment } from "@/lib/params";

interface NodePageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: NodePageProps): Promise<Metadata> {
  const id = decodeSegment((await params).id);
  const summary = id ? await (await getServerAtlasClient()).getNode(id) : null;
  return { title: `${summary?.node.label ?? "Not found"} · Equilibrium` };
}

/** Non-disease nodes (genes, studies, ...) get a plain list of their connections for now. */
function Connections({ summary }: { summary: NodeSummary }) {
  const byId = new Map(summary.neighbors.map((n) => [n.id, n]));
  return (
    <section aria-labelledby="connections" className="mt-8">
      <h2 id="connections" className="text-sm font-medium text-muted">
        Connections ({summary.counts.edges})
      </h2>
      <ul className="mt-3 space-y-3">
        {summary.edges.map((edge) => {
          const otherId = edge.source_id === summary.node.id ? edge.target_id : edge.source_id;
          const other = byId.get(otherId);
          if (!other) return null;
          const outgoing = edge.source_id === summary.node.id;
          return (
            <li key={edge.id} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted">
                {outgoing ? relationLabel(edge.relation) : `${relationLabel(edge.relation)} (from)`}
              </span>
              <NodeChip node={other} />
              <EvidenceBadge type={edge.evidence_type} />
              <Link
                href={pathHref(summary.node.id, otherId)}
                className="text-cluster underline-offset-4 hover:underline"
              >
                Evidence
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Compact depth-1 evidence map of the node, with a way into the full map. */
function MapPreview({ graph, id }: { graph: GraphMapResponse; id: string }) {
  return (
    <section aria-labelledby="map-preview" className="mt-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="map-preview" className="text-sm font-medium text-muted">
          Evidence map · direct links
        </h2>
        <Link
          href={mapHref({ center: id })}
          className="text-sm font-medium text-cluster underline-offset-4 hover:underline"
        >
          Open the full map <span aria-hidden="true">→</span>
        </Link>
      </div>
      <div className="mt-3">
        <EvidenceMap graph={graph} state={{ center: id }} compact />
      </div>
    </section>
  );
}

export default async function NodePage({ params }: NodePageProps) {
  const id = decodeSegment((await params).id);
  if (!id) notFound();
  const client = await getServerAtlasClient();
  const summary = await client.getNode(id);
  if (!summary) notFound();

  const { node } = summary;
  const isDisease = node.type === "disease";
  const description = node.attributes.description;
  const [actions, cluster, graph] = await Promise.all([
    isDisease ? client.getActions(id) : null,
    isDisease && summary.cluster_id ? client.getCluster(summary.cluster_id) : null,
    client.getGraph({ center: id, depth: 1 }),
  ]);
  const coverage = actions?.coverage ?? null;
  const gap = coverage && coverage.result !== "supported" ? coverage : null;

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <PageHeader />
      <DataNotice isMock={client.isMock} usedFallback={client.usedFallback} />

      <header className="mt-8">
        <div className="flex flex-wrap items-center gap-2">
          <TypeBadge type={node.type} />
          <span className="text-xs text-muted">{displayId(node.id)}</span>
          {summary.coverage_status === "gap" && (
            <span className="rounded-full border border-dashed border-muted px-2 py-0.5 text-xs text-muted">
              Coverage gap
            </span>
          )}
        </div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{node.label}</h1>
        {node.synonyms.length > 0 && (
          <p className="mt-2 text-sm text-muted">Also known as: {node.synonyms.join(", ")}</p>
        )}
        {description && <p className="mt-4 leading-relaxed">{description}</p>}
        <p className="mt-5">
          <Link
            href={mapHref({ center: id })}
            className="inline-flex items-center gap-2 rounded-xl bg-cluster px-4 py-2 text-sm font-medium text-background shadow-sm hover:opacity-90"
          >
            View on evidence map <span aria-hidden="true">→</span>
          </Link>
        </p>
      </header>

      {isDisease ? (
        <>
          {gap && (
            <div className="mt-8">
              <GapCard
                diseaseLabel={node.label}
                report={gap}
                communities={closestCommunities(id)}
              />
            </div>
          )}
          {actions && !gap && (
            <p className="mt-6">
              <Link
                href={actionsHref(id)}
                className="inline-block rounded-xl border border-action px-4 py-2 text-sm font-medium text-action hover:bg-surface"
              >
                What to do next: partners, reusable work and a brief{" "}
                <span aria-hidden="true">→</span>
              </Link>
            </p>
          )}
          <div className="mt-8">
            <SummaryCard summary={buildDiseaseSummary(summary)} />
          </div>
          {graph && <MapPreview graph={graph} id={id} />}
          {cluster && (
            <div className="mt-8">
              <DiseaseCluster diseaseId={id} cluster={cluster} />
            </div>
          )}
          {actions && (
            <div className="mt-8">
              <ActionSections
                actions={actions}
                gapShownAbove={Boolean(gap)}
                clusterId={cluster?.id ?? null}
              />
            </div>
          )}
        </>
      ) : (
        <>
          {graph && <MapPreview graph={graph} id={id} />}
          <Connections summary={summary} />
        </>
      )}
    </main>
  );
}
