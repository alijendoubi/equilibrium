import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ClusterPage from "@/app/clusters/[id]/page";
import ClustersPage from "@/app/clusters/page";
import NodePage from "@/app/disease/[id]/page";
import { ClusterDetails } from "@/components/clusters/ClusterDetails";
import { loadMockClusters } from "@/lib/api/clusters-mock";
import type { ClusterDetail } from "@/lib/api/types";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

async function renderCluster(id: string) {
  render(await ClusterPage({ params: Promise.resolve({ id: encodeURIComponent(id) }) }));
}

function detail(id: string): ClusterDetail {
  return structuredClone(loadMockClusters().details.get(id)!);
}

describe("/clusters", () => {
  it("lists every cluster with a link, size and label", async () => {
    render(await ClustersPage());
    expect(screen.getByRole("heading", { level: 1, name: "Disease clusters" })).toBeVisible();
    const link = screen.getByRole("link", { name: /Cluster C1 · 4 diseases/ });
    expect(link).toHaveAttribute("href", "/clusters/C1");
    expect(within(link).getByText(/^GBA1 · /)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Cluster C2 · 1 disease/ })).toHaveAttribute(
      "href",
      "/clusters/C2",
    );
  });

  it("shows an honest empty state when the API has no clusters", async () => {
    vi.stubEnv("NEXT_PUBLIC_USE_MOCKS", "false");
    const body = { clusters: [], method: loadMockClusters().list.method };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } }),
        ),
    );
    render(await ClustersPage());
    expect(screen.getByText(/No clusters yet/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Cluster C1/ })).toBeNull();
  });
});

describe("/clusters/[id]", () => {
  it("renders members, shared features and bridges as an accessible list", async () => {
    await renderCluster("C1");
    expect(screen.getByRole("heading", { level: 1, name: /^GBA1 · / })).toBeVisible();
    const members = screen.getByRole("region", { name: "Members (4)" });
    expect(within(members).getByRole("link", { name: "Gaucher disease type II" })).toHaveAttribute(
      "href",
      "/disease/MONDO%3A0009266",
    );
    const features = screen.getByRole("region", { name: "What they share" });
    expect(within(features).getByRole("link", { name: "GBA1" })).toBeInTheDocument();
    expect(within(features).getByText(/specificity \(IC\) 7\.2/)).toBeInTheDocument();
    const bridges = screen.getByRole("region", { name: "Bridges to other clusters" });
    expect(within(bridges).getByRole("link", { name: "cluster C2" })).toHaveAttribute(
      "href",
      "/clusters/C2",
    );
    expect(within(bridges).getByText(/Splenomegaly/)).toBeInTheDocument();
    const counter = screen.getByRole("region", { name: /Counterexamples/ });
    expect(within(counter).getByText(/No counterexample in this snapshot/)).toBeInTheDocument();
  });

  it("draws solid within-cluster links and dashed bridges", async () => {
    const { container } = render(await ClusterPage({ params: Promise.resolve({ id: "C1" }) }));
    const graph = screen.getByRole("group", { name: /Cluster C1 graph/ });
    expect(graph).toBeInTheDocument();
    const bridges = container.querySelectorAll('line[data-kind="bridge"]');
    const within_ = container.querySelectorAll('line[data-kind="within"]');
    expect(bridges).toHaveLength(1);
    expect(bridges[0]).toHaveAttribute("stroke-dasharray");
    expect(within_).toHaveLength(6);
    for (const line of within_) expect(line).not.toHaveAttribute("stroke-dasharray");
    expect(screen.getByText("Dashed line: bridge to another cluster")).toBeInTheDocument();
  });

  it("makes every graph node a labelled link with an encoded id", async () => {
    const { container } = render(await ClusterPage({ params: Promise.resolve({ id: "C1" }) }));
    const anchors = [...container.querySelectorAll("svg a")];
    expect(anchors).toHaveLength(5);
    const hrefs = anchors.map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/disease/MONDO%3A0009266");
    expect(hrefs.every((h) => h?.startsWith("/disease/MONDO%3A"))).toBe(true);
    const far = anchors.find((a) => a.getAttribute("href") === "/disease/MONDO%3A0012517");
    expect(far).toHaveAttribute("aria-label", expect.stringMatching(/in cluster C2/));
    // Colour is not the only signal: the other cluster's id is written in the label.
    expect(within(far as HTMLElement).getByText(/\(C2\)$/)).toBeInTheDocument();
  });

  it("returns not found for an unknown or malformed cluster id", async () => {
    await expect(renderCluster("C99")).rejects.toThrow();
    await expect(ClusterPage({ params: Promise.resolve({ id: "%E0%A4%A" }) })).rejects.toThrow();
  });
});

describe("cluster list view", () => {
  it("shows counterexamples with their note when the data has them", () => {
    const base = detail("C1");
    const gene = base.features.genes[0]!.node;
    const withCounter: ClusterDetail = {
      ...base,
      counterexamples: [
        {
          gene,
          member_id: "MONDO:0009266",
          other_id: "MONDO:0012517",
          other_cluster_id: "C2",
          score: 0.21,
          note: "Both linked to GBA1 (caused_by) but grouped apart: similarity 0.21.",
        },
      ],
    };
    render(<ClusterDetails detail={withCounter} />);
    const counter = screen.getByRole("region", { name: /Counterexamples/ });
    expect(within(counter).getByText(/grouped apart: similarity 0.21/)).toBeInTheDocument();
    expect(within(counter).getByText("(cluster C2)")).toBeInTheDocument();
  });

  it("says so when a cluster has no bridge or shared feature", () => {
    const lonely: ClusterDetail = {
      ...detail("C2"),
      bridges: [],
      edges: [],
    };
    render(<ClusterDetails detail={lonely} />);
    expect(screen.getByText(/No similarity strong enough to bridge/)).toBeInTheDocument();
    expect(screen.getAllByText(/None shared by two or more members/)).toHaveLength(3);
  });
});

describe("disease page cluster section", () => {
  it("links 'Who shares this' to the disease's cluster", async () => {
    render(
      await NodePage({ params: Promise.resolve({ id: encodeURIComponent("MONDO:0009267") }) }),
    );
    const section = screen.getByRole("region", { name: /Who shares this: GBA1/ });
    expect(within(section).getByText(/3 other diseases, sharing gene GBA1/)).toBeInTheDocument();
    expect(within(section).getByRole("link", { name: /Open the cluster view/ })).toHaveAttribute(
      "href",
      "/clusters/C1",
    );
    expect(screen.getByRole("link", { name: /See its disease cluster \(C1\)/ })).toHaveAttribute(
      "href",
      "/clusters/C1",
    );
  });

  it("is honest about a cluster of one", async () => {
    render(
      await NodePage({ params: Promise.resolve({ id: encodeURIComponent("MONDO:0012517") }) }),
    );
    const section = screen.getByRole("region", { name: /Who shares this/ });
    expect(within(section).getByText(/No other disease is similar enough/)).toBeInTheDocument();
  });
});
