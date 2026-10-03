import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EvidenceBadge, TypeBadge } from "@/components/Badges";
import { ActionSections } from "@/components/disease/ActionSections";
import { SummaryCard } from "@/components/disease/SummaryCard";
import { MockBanner } from "@/components/MockBanner";
import { NodeChip } from "@/components/NodeChip";
import { PageHeader } from "@/components/PageHeader";
import { getAtlasClient } from "@/lib/api/client";
import type { NodeSummary } from "@/lib/api/types";
import { buildDiseaseSummary } from "@/lib/disease-summary";
import { pathHref, relationLabel } from "@/lib/format";
import { decodeSegment } from "@/lib/params";

interface NodePageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: NodePageProps): Promise<Metadata> {
  const id = decodeSegment((await params).id);
  const summary = id ? await getAtlasClient().getNode(id) : null;
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

export default async function NodePage({ params }: NodePageProps) {
  const id = decodeSegment((await params).id);
  if (!id) notFound();
  const client = getAtlasClient();
  const summary = await client.getNode(id);
  if (!summary) notFound();

  const { node } = summary;
  const isDisease = node.type === "disease";
  const actions = isDisease ? await client.getActions(id) : null;

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <PageHeader />
      <div className="mt-6">
        <MockBanner isMock={client.isMock} />
      </div>

      <header className="mt-8">
        <div className="flex flex-wrap items-center gap-2">
          <TypeBadge type={node.type} />
          <span className="text-xs text-muted">{node.id}</span>
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
        {node.description && <p className="mt-4 leading-relaxed">{node.description}</p>}
      </header>

      {isDisease ? (
        <>
          <div className="mt-8">
            <SummaryCard summary={buildDiseaseSummary(summary)} />
          </div>
          {actions && (
            <div className="mt-8">
              <ActionSections actions={actions} />
            </div>
          )}
        </>
      ) : (
        <Connections summary={summary} />
      )}
    </main>
  );
}
