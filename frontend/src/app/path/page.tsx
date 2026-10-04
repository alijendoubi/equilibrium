import type { Metadata } from "next";
import Link from "next/link";
import { CoverageReportCard } from "@/components/CoverageReportCard";
import { MockBanner } from "@/components/MockBanner";
import { PageHeader } from "@/components/PageHeader";
import { PathExplorer } from "@/components/path/PathExplorer";
import { getAtlasClient } from "@/lib/api/client";
import { nodeHref } from "@/lib/format";
import { firstParam } from "@/lib/params";

export const metadata: Metadata = { title: "Connection · Equilibrium" };

interface PathPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function PathPage({ searchParams }: PathPageProps) {
  const params = await searchParams;
  const from = firstParam(params.from).trim();
  const to = firstParam(params.to).trim();
  const client = getAtlasClient();

  if (!from || !to) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-8">
        <PageHeader />
        <h1 className="mt-8 text-2xl font-semibold">Explore a connection</h1>
        <p className="mt-2 text-muted">
          Open a disease and choose &ldquo;Explore connection&rdquo; to see how two things link.
        </p>
      </main>
    );
  }

  const [response, fromNode, toNode] = await Promise.all([
    client.getPath(from, to),
    client.getNode(from),
    client.getNode(to),
  ]);
  const fromLabel = fromNode?.node.label ?? from;
  const toLabel = toNode?.node.label ?? to;

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <PageHeader />
      <div className="mt-6">
        <MockBanner isMock={client.isMock} />
      </div>
      <p className="mt-8 text-sm">
        <Link href={nodeHref(from)} className="text-muted underline-offset-4 hover:underline">
          <span aria-hidden="true">←</span> Back to {fromLabel}
        </Link>
      </p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">
        How {fromLabel} connects to {toLabel}
      </h1>

      <div className="mt-6">
        {response.paths.length > 0 ? (
          <PathExplorer paths={response.paths} />
        ) : (
          <>
            <p className="mb-4 text-muted">No supported route between these two.</p>
            {response.coverage && <CoverageReportCard report={response.coverage} />}
          </>
        )}
      </div>
    </main>
  );
}
