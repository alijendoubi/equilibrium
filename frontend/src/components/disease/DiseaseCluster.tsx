import Link from "next/link";
import type { ClusterDetail } from "@/lib/api/types";
import { clusterHref, nodeHref } from "@/lib/format";

const MAX_LISTED = 6;

/** "Who shares this" at a glance: the disease's cluster, a few fellow members, and a way in. */
export function DiseaseCluster({
  diseaseId,
  cluster,
}: {
  diseaseId: string;
  cluster: ClusterDetail;
}) {
  const labels = new Map(cluster.nodes.map((n) => [n.node.id, n.node.label]));
  const others = cluster.member_ids.filter((id) => id !== diseaseId);
  const listed = others.slice(0, MAX_LISTED);
  const why = [
    ...cluster.features.genes.slice(0, 1).map((f) => `gene ${f.node.label}`),
    ...cluster.features.mechanisms.slice(0, 1).map((f) => f.node.label),
  ];

  return (
    <section
      aria-labelledby="disease-cluster"
      className="relative overflow-hidden rounded-2xl border border-border bg-surface p-5 pl-6"
    >
      <span aria-hidden="true" className="absolute inset-y-0 left-0 w-1 bg-cluster" />
      <p className="text-xs font-semibold tracking-wider text-cluster uppercase">
        Cluster {cluster.id}
      </p>
      <h2 id="disease-cluster" className="mt-1 text-lg font-semibold">
        Who shares this: {cluster.label}
      </h2>
      {others.length === 0 ? (
        <p className="mt-2 text-sm text-muted">
          No other disease is similar enough to join this cluster yet.
          {cluster.bridges.length > 0 &&
            " Its closest links to other clusters are in the cluster view."}
        </p>
      ) : (
        <>
          <p className="mt-2 text-sm text-muted">
            {others.length} other {others.length === 1 ? "disease" : "diseases"}
            {why.length > 0 && `, sharing ${why.join(" and ")}`}:
          </p>
          <ul className="mt-2 flex flex-wrap gap-2 text-sm">
            {listed.map((id) => (
              <li key={id}>
                <Link
                  href={nodeHref(id)}
                  className="inline-block rounded-full border border-cluster px-3 py-1 hover:bg-background"
                >
                  {labels.get(id) ?? id}
                </Link>
              </li>
            ))}
            {others.length > listed.length && (
              <li className="px-1 py-1 text-muted">and {others.length - listed.length} more</li>
            )}
          </ul>
        </>
      )}
      <p className="mt-3">
        <Link
          href={clusterHref(cluster.id)}
          className="text-sm font-medium text-cluster underline-offset-4 hover:underline"
        >
          Open the cluster view: graph, bridges and counterexamples{" "}
          <span aria-hidden="true">→</span>
        </Link>
      </p>
    </section>
  );
}
