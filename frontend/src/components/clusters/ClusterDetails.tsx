import Link from "next/link";
import type { ReactNode } from "react";
import type { ClusterDetail, SharedFeature } from "@/lib/api/types";
import { clusterHref, nodeHref } from "@/lib/format";

const linkClass = "font-medium underline-offset-4 hover:underline";

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="rounded-2xl border border-border bg-surface p-5">
      <h2 id={id} className="text-lg font-semibold">
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function FeatureList({
  title,
  items,
  size,
}: {
  title: string;
  items: SharedFeature[];
  size: number;
}) {
  return (
    <div>
      <h3 className="text-xs font-semibold tracking-wider text-muted uppercase">{title}</h3>
      {items.length === 0 ? (
        <p className="mt-1 text-sm text-muted">None shared by two or more members.</p>
      ) : (
        <ul className="mt-1 space-y-1 text-sm">
          {items.map((f) => (
            <li key={f.node.id}>
              <Link href={nodeHref(f.node.id)} className={linkClass}>
                {f.node.label}
              </Link>{" "}
              <span className="text-muted">
                shared by {f.member_ids.length} of {size}
                {f.ic !== null && ` · specificity (IC) ${f.ic.toFixed(1)}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Accessible list view of a cluster: the same facts as the graph, as text. */
export function ClusterDetails({ detail }: { detail: ClusterDetail }) {
  const labels = new Map(detail.nodes.map((n) => [n.node.id, n.node.label]));
  const label = (id: string) => labels.get(id) ?? id;
  const degree = new Map(detail.nodes.map((n) => [n.node.id, n.degree]));

  return (
    <div className="space-y-4">
      <Section id="cluster-members" title={`Members (${detail.size})`}>
        <ul className="space-y-1 text-sm">
          {detail.member_ids.map((id) => (
            <li key={id}>
              <Link href={nodeHref(id)} className={linkClass}>
                {label(id)}
              </Link>{" "}
              <span className="text-muted">· {degree.get(id) ?? 0} similarity links</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="cluster-features" title="What they share">
        <div className="grid gap-4 sm:grid-cols-3">
          <FeatureList title="Genes" items={detail.features.genes} size={detail.size} />
          <FeatureList title="Mechanisms" items={detail.features.mechanisms} size={detail.size} />
          <FeatureList
            title="Specific symptoms"
            items={detail.features.phenotypes}
            size={detail.size}
          />
        </div>
      </Section>

      <Section id="cluster-bridges" title="Bridges to other clusters">
        {detail.bridges.length === 0 ? (
          <p className="text-sm text-muted">No similarity strong enough to bridge clusters.</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {detail.bridges.map((b) => (
              <li key={`${b.member_id}:${b.other_id}`}>
                <Link href={nodeHref(b.member_id)} className={linkClass}>
                  {label(b.member_id)}
                </Link>{" "}
                <span aria-hidden="true">- - -</span>{" "}
                <Link href={nodeHref(b.other_id)} className={linkClass}>
                  {label(b.other_id)}
                </Link>{" "}
                <span className="text-muted">
                  (in{" "}
                  <Link href={clusterHref(b.other_cluster_id)} className="underline">
                    cluster {b.other_cluster_id}
                  </Link>
                  , score {b.score.toFixed(2)})
                </span>
                <ul className="mt-1 list-disc pl-5 text-muted">
                  {b.reasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section id="cluster-counterexamples" title="Counterexamples: same gene, different cluster">
        {detail.counterexamples.length === 0 ? (
          <p className="text-sm text-muted">
            No counterexample in this snapshot: no gene of these members also links to a disease in
            another cluster.
          </p>
        ) : (
          <ul className="space-y-3 text-sm">
            {detail.counterexamples.map((c) => (
              <li key={`${c.gene.id}:${c.member_id}:${c.other_id}`}>
                <span className="font-medium">{c.gene.label}</span>:{" "}
                <Link href={nodeHref(c.member_id)} className={linkClass}>
                  {label(c.member_id)}
                </Link>{" "}
                vs{" "}
                <Link href={nodeHref(c.other_id)} className={linkClass}>
                  {label(c.other_id)}
                </Link>{" "}
                <span className="text-muted">(cluster {c.other_cluster_id})</span>
                <p className="mt-1 text-muted">{c.note}</p>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
