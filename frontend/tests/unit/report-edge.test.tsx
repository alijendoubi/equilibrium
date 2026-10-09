import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EdgePanel } from "@/components/path/EdgePanel";
import { getAtlasClient } from "@/lib/api/client";
import type { AtlasNode, Edge } from "@/lib/api/types";
import { edgeReportUrl } from "@/lib/report";

async function sampleEdge(): Promise<{ edge: Edge; nodes: Map<string, AtlasNode> }> {
  const summary = await getAtlasClient().getNode("MONDO:0009266");
  if (!summary?.edges[0]) throw new Error("mock data should have edges for Gaucher type II");
  const nodes = new Map([summary.node, ...summary.neighbors].map((n) => [n.id, n]));
  return { edge: summary.edges[0], nodes };
}

describe("edgeReportUrl", () => {
  it("targets the edge-report form and prefills its fields by id", async () => {
    const { edge, nodes } = await sampleEdge();
    const url = new URL(edgeReportUrl(edge, (id) => nodes.get(id)?.label ?? id, "https://atlas/x"));
    expect(url.origin + url.pathname).toBe("https://github.com/alijendoubi/equilibrium/issues/new");
    const q = url.searchParams;
    expect(q.get("template")).toBe("edge-report.yml");
    expect(q.get("edge_id")).toBe(edge.id);
    expect(q.get("title")).toBe(`data: problem with edge ${edge.id}`);
    expect(q.get("claim")).toContain(nodes.get(edge.source_id)!.label);
    expect(q.get("sources")).toContain(edge.provenance.source_record_id);
    expect(q.get("page")).toBe("https://atlas/x");
    expect(q.has("problem")).toBe(false);
  });

  it("caps long fields so the URL stays within limits", async () => {
    const { edge } = await sampleEdge();
    const url = edgeReportUrl(edge, () => "x".repeat(5000));
    expect(new URL(url).searchParams.get("claim")!.length).toBeLessThanOrEqual(1500);
    expect(url.length).toBeLessThan(8000);
  });
});

describe("EdgePanel", () => {
  it("offers a 'Report a problem' link that opens the prefilled form safely", async () => {
    const { edge, nodes } = await sampleEdge();
    render(<EdgePanel edge={edge} nodesById={nodes} />);
    const link = screen.getByRole("link", { name: /Report a problem/ });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(new URL(link.getAttribute("href")!).searchParams.get("edge_id")).toBe(edge.id);
    expect(screen.getByText(/Do not include personal health information/)).toBeInTheDocument();
  });
});
