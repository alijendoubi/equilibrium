import type { Metadata } from "next";
import Link from "next/link";
import { DataNotice } from "@/components/MockBanner";
import { PageHeader } from "@/components/PageHeader";
import { getAtlasClient } from "@/lib/api/client";
import { clusterColor } from "@/lib/cluster-layout";
import { clusterHref } from "@/lib/format";

export const metadata: Metadata = { title: "Disease clusters · Equilibrium" };

export default async function ClustersPage() {
  const client = getAtlasClient();
  const { clusters, method } = await client.getClusters();

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <PageHeader />
      <DataNotice isMock={client.isMock} usedFallback={client.usedFallback} />
      <h1 className="mt-8 text-3xl font-semibold tracking-tight">Disease clusters</h1>
      <p className="mt-2 leading-relaxed text-muted">
        Who shares our disease characteristics: diseases grouped by shared genes, mechanisms and
        specific symptoms. Open a cluster to see why its members belong together, the bridges to
        other clusters and the counterexamples.
      </p>
      <p className="mt-2 text-xs text-muted">{method.description}</p>

      {clusters.length === 0 ? (
        <p className="mt-8 rounded-2xl border border-dashed border-muted p-5 text-sm text-muted">
          No clusters yet: the loaded snapshot has no disease similarity to group.
        </p>
      ) : (
        <ul className="mt-8 space-y-3">
          {clusters.map((c) => (
            <li key={c.id}>
              <Link
                href={clusterHref(c.id)}
                className="relative block overflow-hidden rounded-2xl border border-border bg-surface p-4 pl-6 hover:border-cluster"
              >
                <span
                  aria-hidden="true"
                  className="absolute inset-y-0 left-0 w-1"
                  style={{ background: clusterColor(c.id) }}
                />
                <span className="text-xs font-semibold tracking-wider text-muted uppercase">
                  Cluster {c.id} · {c.size} {c.size === 1 ? "disease" : "diseases"}
                </span>
                <span className="mt-1 block font-semibold">{c.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
