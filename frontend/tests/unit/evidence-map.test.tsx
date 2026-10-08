import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MapPage from "@/app/map/page";
import NodePage from "@/app/disease/[id]/page";
import { EvidenceMap } from "@/components/graph/EvidenceMap";
import { mockClient } from "@/lib/api/client";
import type { GraphMapResponse } from "@/lib/api/types";

const GAUCHER_2 = "MONDO:0009266";
const GAUCHER_3 = "MONDO:0009267";
const PD24 = "MONDO:0859183";
const GBA1 = "HGNC:4177";

async function graph(query: Parameters<typeof mockClient.getGraph>[0]) {
  const m = await mockClient.getGraph(query);
  if (!m) throw new Error("expected a map");
  return m;
}

function renderMap(m: GraphMapResponse, state = {}) {
  const view = render(<EvidenceMap graph={m} state={state} />);
  const node = (id: string) => view.container.querySelector(`[data-node-id="${id}"]`)!;
  const edges = () => [...view.container.querySelectorAll<SVGGElement>("[data-edge-id]")];
  return { ...view, node, edges };
}

describe("EvidenceMap", () => {
  it("draws every node as a labelled, focusable button, plus a legend", async () => {
    const m = await graph({ center: GAUCHER_2 });
    const { node } = renderMap(m, { center: GAUCHER_2 });
    for (const n of m.nodes) {
      const el = node(n.node.id);
      expect(el).toHaveAttribute("tabindex", "0");
      expect(el.getAttribute("aria-label")).toContain(n.node.label);
    }
    expect(node(GAUCHER_2).textContent).toBe("Gaucher disease type II");
    const legend = screen.getByRole("region", { name: "Map legend" });
    expect(within(legend).getByText("Disease")).toBeInTheDocument();
    expect(within(legend).getByText(/Dashed line: hypothesis/)).toBeInTheDocument();
    expect(within(legend).getByText(/sources\s+disagree/)).toBeInTheDocument();
  });

  it("draws inferred edges dashed and data edges solid", async () => {
    const { edges } = renderMap(await graph({ center: GAUCHER_3 }));
    const hypothesis = edges().filter((g) => g.dataset.style === "hypothesis");
    const data = edges().filter((g) => g.dataset.style === "data");
    expect(hypothesis.length).toBeGreaterThan(0);
    for (const g of hypothesis) {
      expect(g.querySelector(".edge-line")).toHaveAttribute("stroke-dasharray");
    }
    expect(data[0]!.querySelector(".edge-line")).not.toHaveAttribute("stroke-dasharray");
  });

  it("styles and labels contradictions", async () => {
    const { edges } = renderMap(await graph({ center: PD24 }));
    const contra = edges().filter((g) => g.dataset.style === "contradiction");
    expect(contra.length).toBeGreaterThanOrEqual(2);
    // Badges are drawn in their own layer above the nodes, keyed by edge id.
    const texts = contra.map(
      (g) => document.querySelector(`[data-edge-badge="${g.dataset.edgeId}"]`)?.textContent,
    );
    expect(texts).toContain("contradicts");
    expect(texts).toContain("contested");
    expect(contra[0]!.querySelector(".edge-line")!.getAttribute("style")).toContain(
      "--contradiction",
    );
  });

  it("hides a node type when its filter chip is switched off", async () => {
    const m = await graph({ center: GAUCHER_3 });
    const { container } = renderMap(m, { center: GAUCHER_3 });
    expect(container.querySelector(`[data-type="gene"]`)).not.toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: /Gene/ }));
    expect(container.querySelector(`[data-type="gene"]`)).toBeNull();
    // The center is always drawn.
    fireEvent.click(screen.getByRole("checkbox", { name: /Disease/ }));
    expect(container.querySelector(`[data-node-id="${GAUCHER_3}"]`)).not.toBeNull();
  });

  it("filters by evidence type and minimum confidence", async () => {
    const { edges } = renderMap(await graph({ center: GAUCHER_3 }));
    const before = edges().length;
    fireEvent.click(screen.getByRole("checkbox", { name: /Hypothesis/ }));
    expect(edges().every((g) => g.dataset.style !== "hypothesis")).toBe(true);
    fireEvent.change(screen.getByLabelText(/Min confidence/), { target: { value: "0.95" } });
    expect(edges().length).toBeLessThan(before);
  });

  it("shows collapsed types as badges with a link to load symptoms", async () => {
    renderMap(await graph({ center: GAUCHER_3 }), { center: GAUCHER_3 });
    const badge = screen.getByRole("link", { name: /^\+\d+ symptoms$/ });
    expect(badge).toHaveAttribute("href", "/map?center=MONDO%3A0009267&phenotypes=1");
  });

  it("lists the same nodes and links in the table view", async () => {
    const m = await graph({ center: GAUCHER_2 });
    renderMap(m);
    fireEvent.click(screen.getByRole("button", { name: "Table view" }));
    const nodesTable = screen.getByRole("table", { name: /Nodes on the map/ });
    const linksTable = screen.getByRole("table", { name: /Links on the map/ });
    expect(within(nodesTable).getAllByRole("row")).toHaveLength(m.nodes.length + 1);
    expect(within(linksTable).getAllByRole("row")).toHaveLength(m.edges.length + 1);
    expect(within(nodesTable).getByText("GBA1")).toBeInTheDocument();
    fireEvent.click(within(linksTable).getAllByRole("button", { name: /Evidence/ })[0]!);
    expect(screen.getByRole("complementary", { name: "Edge evidence" })).toBeInTheDocument();
  });

  it("opens the node panel on click and Enter, with encoded action links", async () => {
    const { node } = renderMap(await graph({ center: GAUCHER_2 }), { center: GAUCHER_2 });
    fireEvent.click(node(GBA1));
    const panel = screen.getByRole("complementary", { name: "Node details" });
    expect(within(panel).getByRole("heading", { name: "GBA1" })).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: "Open page" })).toHaveAttribute(
      "href",
      "/disease/HGNC%3A4177",
    );
    expect(within(panel).getByRole("link", { name: "Center map here" })).toHaveAttribute(
      "href",
      "/map?center=HGNC%3A4177",
    );
    expect(within(panel).getByRole("link", { name: "Expand neighbours" })).toHaveAttribute(
      "href",
      "/map?center=MONDO%3A0009266&expand=HGNC%3A4177",
    );
    fireEvent.click(within(panel).getByRole("button", { name: "Close details" }));
    fireEvent.keyDown(node(GAUCHER_2), { key: "Enter" });
    expect(
      within(screen.getByRole("complementary", { name: "Node details" })).getByRole("link", {
        name: "Open disease page",
      }),
    ).toHaveAttribute("href", "/disease/MONDO%3A0009266");
  });

  it("opens the edge evidence panel from a line and from the node panel", async () => {
    const { node, edges } = renderMap(await graph({ center: GAUCHER_2 }));
    const causedBy = edges().find((g) => g.dataset.edgeId === "E:61528699fb974eda")!;
    fireEvent.click(causedBy);
    const panel = screen.getByRole("complementary", { name: "Edge evidence" });
    expect(within(panel).getByText("Confidence")).toBeInTheDocument();
    expect(within(panel).getByText(/E:61528699fb974eda/)).toBeInTheDocument();

    fireEvent.click(node(GBA1));
    const nodePanel = screen.getByRole("complementary", { name: "Node details" });
    fireEvent.click(within(nodePanel).getAllByRole("button", { name: /Show evidence/ })[0]!);
    expect(screen.getByRole("complementary", { name: "Edge evidence" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Back to GBA1/ }));
    expect(screen.getByRole("complementary", { name: "Node details" })).toBeInTheDocument();
  });

  it("highlights a route and adds it to the legend", async () => {
    const m = await graph({ center: GAUCHER_2 });
    const { edges } = renderMap(m, { highlight: ["E:61528699fb974eda"] });
    const lit = edges().find((g) => g.dataset.edgeId === "E:61528699fb974eda")!;
    expect(lit.querySelector(".edge-line")!.getAttribute("style")).toContain("--focus");
    expect(screen.getByText(/the route you came from/)).toBeInTheDocument();
  });

  it("zooms with the buttons without losing nodes", async () => {
    const { container } = renderMap(await graph({ center: GAUCHER_2 }));
    const before = container.querySelector(`[data-node-id="${GBA1}"]`)!.getAttribute("transform");
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    const after = container.querySelector(`[data-node-id="${GBA1}"]`)!.getAttribute("transform");
    expect(after).not.toBe(before);
    fireEvent.click(screen.getByRole("button", { name: "Reset view" }));
    expect(container.querySelector(`[data-node-id="${GBA1}"]`)!.getAttribute("transform")).toBe(
      before,
    );
  });
});

describe("/map page", () => {
  it("renders the overview with the mock notice", async () => {
    render(await MapPage({ searchParams: Promise.resolve({}) }));
    expect(
      screen.getByRole("heading", { level: 1, name: /slice at a glance/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("Mock data.")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-map")).toBeInTheDocument();
  });

  it("centres on an encoded id, expands and highlights", async () => {
    const { container } = render(
      await MapPage({
        searchParams: Promise.resolve({
          center: GAUCHER_2,
          expand: "MONDO:0008199",
          highlight: "E:61528699fb974eda",
        }),
      }),
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "Gaucher disease type II" }),
    ).toBeInTheDocument();
    expect(container.querySelector(`[data-node-id="MONDO:0008199"]`)).not.toBeNull();
    expect(screen.getByRole("link", { name: "Open disease page" })).toHaveAttribute(
      "href",
      "/disease/MONDO%3A0009266",
    );
  });

  it("explains an unknown center", async () => {
    render(await MapPage({ searchParams: Promise.resolve({ center: "MONDO:0000000" }) }));
    expect(screen.getByRole("heading", { name: "Not on the map" })).toBeInTheDocument();
  });
});

describe("disease page map entry", () => {
  it("links to the map and embeds a compact map", async () => {
    const { container } = render(
      await NodePage({ params: Promise.resolve({ id: encodeURIComponent(GAUCHER_2) }) }),
    );
    expect(screen.getByRole("link", { name: /View on evidence map/ })).toHaveAttribute(
      "href",
      "/map?center=MONDO%3A0009266",
    );
    expect(screen.getByRole("region", { name: /Evidence map · direct links/ })).toBeInTheDocument();
    expect(container.querySelector(`[data-node-id="${GBA1}"]`)).not.toBeNull();
  });
});
