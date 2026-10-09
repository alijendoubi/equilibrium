import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ClusterDetails } from "@/components/clusters/ClusterDetails";
import { ClusterGraph } from "@/components/clusters/ClusterGraph";
import { DataNotice } from "@/components/MockBanner";
import { PageHeader } from "@/components/PageHeader";
import { getServerAtlasClient } from "@/lib/api/server-client";
import { decodeSegment } from "@/lib/params";

interface ClusterPageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: ClusterPageProps): Promise<Metadata> {
  const id = decodeSegment((await params).id);
  return { title: `${id ? `Cluster ${id}` : "Cluster"} · Equilibrium` };
}

export default async function ClusterPage({ params }: ClusterPageProps) {
  const id = decodeSegment((await params).id);
  if (!id) notFound();
  const client = await getServerAtlasClient();
  const detail = await client.getCluster(id);
  if (!detail) notFound();

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <PageHeader />
      <DataNotice isMock={client.isMock} usedFallback={client.usedFallback} />
      <p className="mt-8 text-sm">
        <Link href="/clusters" className="text-cluster underline-offset-4 hover:underline">
          <span aria-hidden="true">←</span> All clusters
        </Link>
      </p>
      <header className="mt-2">
        <p className="text-xs font-semibold tracking-wider text-cluster uppercase">
          Cluster {detail.id} · {detail.size} {detail.size === 1 ? "disease" : "diseases"}
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{detail.label}</h1>
        <p className="mt-2 text-sm text-muted">
          Grouped by shared genes, GO mechanisms and specific symptoms. A computed grouping to
          explore, not a diagnosis: each link lists its reasons.
        </p>
      </header>
      <div className="mt-6">
        <ClusterGraph detail={detail} />
      </div>
      <div className="mt-6">
        <ClusterDetails detail={detail} />
      </div>
    </main>
  );
}
