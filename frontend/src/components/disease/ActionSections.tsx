import Link from "next/link";
import { TypeBadge } from "@/components/Badges";
import { CollapsibleCard } from "@/components/CollapsibleCard";
import { CoverageReportCard } from "@/components/CoverageReportCard";
import type { ActionsResponse } from "@/lib/api/types";
import { clusterHref, nodeHref, pathHref } from "@/lib/format";

function ExploreLink({ from, to }: { from: string; to: string }) {
  return (
    <Link
      href={pathHref(from, to)}
      className="text-sm font-medium text-cluster underline-offset-4 hover:underline"
    >
      Explore connection <span aria-hidden="true">→</span>
    </Link>
  );
}

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

/** "Who shares this", "What exists", "What next": the three questions, collapsed by default. */
interface ActionSectionsProps {
  actions: ActionsResponse;
  /** The page already shows the gap card, so "What next" only points to it. */
  gapShownAbove?: boolean;
  /** The disease's similarity cluster, linked from "Who shares this". */
  clusterId?: string | null;
}

export function ActionSections({
  actions,
  gapShownAbove = false,
  clusterId = null,
}: ActionSectionsProps) {
  const id = actions.disease_id;
  const gap = actions.coverage;

  return (
    <div className="space-y-4">
      <CollapsibleCard
        tone="cluster"
        label="Cluster"
        title="Who shares this"
        summary={
          actions.partners.length > 0
            ? plural(actions.partners.length, "connected community", "connected communities")
            : "No connected community found yet"
        }
      >
        {clusterId && (
          <p className="mb-4">
            <Link
              href={clusterHref(clusterId)}
              className="text-sm font-medium text-cluster underline-offset-4 hover:underline"
            >
              See its disease cluster ({clusterId}) <span aria-hidden="true">→</span>
            </Link>
          </p>
        )}
        {actions.partners.length === 0 ? (
          <p className="text-sm text-muted">
            We found no disease or patient group with a supported link. See &ldquo;What next&rdquo;
            for what we searched.
          </p>
        ) : (
          <ul className="space-y-4">
            {actions.partners.map((p) => (
              <li key={p.node.id} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-2">
                  <TypeBadge type={p.node.type} />
                  <Link href={nodeHref(p.node.id)} className="font-medium hover:underline">
                    {p.node.label}
                  </Link>
                </div>
                <p className="text-sm text-muted">{p.why}</p>
                <ExploreLink from={id} to={p.node.id} />
              </li>
            ))}
          </ul>
        )}
      </CollapsibleCard>

      <CollapsibleCard
        tone="evidence"
        label="Evidence"
        title="What exists"
        summary={
          actions.assets.length > 0
            ? plural(actions.assets.length, "reusable resource", "reusable resources")
            : "No reusable study or resource found yet"
        }
      >
        {actions.assets.length === 0 ? (
          <p className="text-sm text-muted">No trial, registry or publication is linked yet.</p>
        ) : (
          <ul className="space-y-5">
            {actions.assets.map((a) => (
              <li key={a.node.id} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-2">
                  <TypeBadge type={a.node.type} />
                  <Link href={nodeHref(a.node.id)} className="font-medium hover:underline">
                    {a.node.label}
                  </Link>
                </div>
                <dl className="mt-1 grid gap-1 text-sm sm:grid-cols-[7rem_1fr]">
                  <dt className="text-muted">Reusable</dt>
                  <dd>{a.reusable}</dd>
                  <dt className="text-muted">What differs</dt>
                  <dd>{a.differs}</dd>
                </dl>
                <ExploreLink from={id} to={a.node.id} />
              </li>
            ))}
          </ul>
        )}
      </CollapsibleCard>

      <CollapsibleCard
        tone="action"
        label="Action"
        title="What next"
        summary={gap ? "Honest gap: what we searched and what is missing" : "Suggested next step"}
        defaultOpen={Boolean(gap)}
      >
        {actions.next_experiment && (
          <div>
            <p className="text-xs font-semibold tracking-wider text-muted uppercase">
              {actions.next_experiment.is_hypothesis ? "Hypothesis to test" : "Next step"}
            </p>
            <p className="mt-1 text-sm">{actions.next_experiment.text}</p>
          </div>
        )}
        {actions.review_checklist.length > 0 && (
          <div className="mt-4">
            <p className="text-xs font-semibold tracking-wider text-muted uppercase">
              Questions for expert review
            </p>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
              {actions.review_checklist.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          </div>
        )}
        {gap && gapShownAbove && (
          <p className="text-sm text-muted">See the honest gap report at the top of this page.</p>
        )}
        {gap && !gapShownAbove && (
          <div className={actions.next_experiment ? "mt-4" : undefined}>
            <CoverageReportCard report={gap} />
          </div>
        )}
        {!actions.next_experiment && actions.review_checklist.length === 0 && !gap && (
          <p className="text-sm text-muted">No next step suggested yet.</p>
        )}
      </CollapsibleCard>
    </div>
  );
}
