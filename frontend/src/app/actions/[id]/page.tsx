import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ActionPlan } from "@/components/actions/ActionPlan";
import { GapCard } from "@/components/GapCard";
import { DataNotice } from "@/components/MockBanner";
import { PageHeader } from "@/components/PageHeader";
import { loadActionView } from "@/lib/action-view";
import { getAtlasClient } from "@/lib/api/client";
import { nodeHref } from "@/lib/format";
import { closestCommunities } from "@/lib/gap";
import { decodeSegment } from "@/lib/params";

interface ActionsPageProps {
  params: Promise<{ id: string }>;
}

export const metadata: Metadata = { title: "What to do next · Equilibrium" };

export default async function ActionsPage({ params }: ActionsPageProps) {
  const id = decodeSegment((await params).id);
  if (!id) notFound();
  const client = getAtlasClient();
  const view = await loadActionView(client, id);
  if (!view) notFound();

  const { summary, actions, coverage } = view;
  const label = summary.node.label;
  const isGap = coverage !== null && coverage.result !== "supported";
  const hasPlan = actions.partners.length > 0 || actions.assets.length > 0;

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <PageHeader />
      <DataNotice isMock={client.isMock} usedFallback={client.usedFallback} />
      <p className="mt-8 text-sm">
        <Link href={nodeHref(id)} className="text-muted underline-offset-4 hover:underline">
          <span aria-hidden="true">←</span> Back to {label}
        </Link>
      </p>
      <p className="mt-2 text-xs font-semibold tracking-wider text-action uppercase">Action</p>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight">What to do next for {label}</h1>
      <p className="mt-2 text-sm text-muted">
        Every recommendation cites the links it rests on. Dashed means hypothesis: check it with an
        expert first.
      </p>

      {isGap && coverage && (
        <div className="mt-6">
          <GapCard diseaseLabel={label} report={coverage} communities={closestCommunities(id)} />
        </div>
      )}

      {(hasPlan || !isGap) && (
        <div className="mt-6">
          <ActionPlan
            diseaseLabel={label}
            actions={actions}
            edges={view.edges}
            nodes={view.nodes}
            briefEdgeIds={view.briefEdgeIds}
          />
        </div>
      )}
    </main>
  );
}
