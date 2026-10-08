import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AiThinkingOrbAndInput } from "@/components/ui/ai-thinking-orb-and-input";
import { hexToRgbChannels } from "@/components/ui/thinking-orb";
import { traceNode, traceQuery } from "@/lib/trace";
import { normalizeQuery, summarizeTrace, type TraceResult } from "@/lib/trace-result";

async function found(query: string) {
  const result = await traceQuery(query);
  if (result.status !== "found" || !result.graph) throw new Error(`expected a map for ${query}`);
  return { ...result, graph: result.graph };
}

describe("traceQuery (mock atlas)", () => {
  it("finds a disease and returns its real depth-1 evidence map", async () => {
    const result = await found("Gaucher");
    expect(result.graph.center).toBe(result.match.node.id);
    expect(result.graph.nodes.length).toBeGreaterThan(1);
    expect(result.isMock).toBe(true);
  });

  it("rejects blank or non-string input without searching", async () => {
    expect(await traceQuery("   ")).toMatchObject({ status: "invalid" });
    expect(await traceQuery(42)).toMatchObject({ status: "invalid" });
  });

  it("reports an honest miss with what was searched", async () => {
    const result = await traceQuery("zzqx-not-a-disease");
    expect(result.status).toBe("not_found");
    if (result.status === "not_found") expect(result.searched.length).toBeGreaterThan(0);
  });

  it("refuses ids that are not CURIEs", async () => {
    expect(await traceNode("not an id")).toMatchObject({ status: "error" });
    expect(await traceNode("MONDO:0009266")).toMatchObject({ status: "ok" });
  });
});

describe("trace helpers", () => {
  it("caps and trims queries", () => {
    expect(normalizeQuery("  GBA1  ")).toBe("GBA1");
    expect(normalizeQuery("x".repeat(500))).toHaveLength(200);
    expect(normalizeQuery(null)).toBe("");
  });

  it("summarises neighbours without counting the center", async () => {
    const { graph } = await found("Gaucher");
    const summary = summarizeTrace(graph);
    const total = summary.neighbours.reduce((n, t) => n + t.count, 0);
    expect(total).toBe(graph.nodes.length - 1);
    expect(summary.links).toBe(graph.edges.length);
  });

  it("converts theme hex colours for the orb canvas", () => {
    expect(hexToRgbChannels(" #0f766e")).toBe("15 118 110");
    expect(hexToRgbChannels("#fff")).toBe("255 255 255");
    expect(hexToRgbChannels("teal")).toBe("15 118 110");
  });
});

describe("AiThinkingOrbAndInput", () => {
  const box = () => screen.getByRole("searchbox", { name: "Search the atlas" });

  it("traces a query and shows the real map with onward links", async () => {
    const result = await found("Gaucher");
    render(<AiThinkingOrbAndInput trace={async () => result} minThinkMs={0} />);
    fireEvent.change(box(), { target: { value: "Gaucher" } });
    fireEvent.submit(box().closest("form")!);

    expect(await screen.findByRole("heading", { level: 2 })).toHaveTextContent(
      result.match.node.label,
    );
    expect(screen.getByRole("link", { name: /Open full map/ })).toHaveAttribute(
      "href",
      `/map?center=${encodeURIComponent(result.match.node.id)}`,
    );
    expect(screen.getByRole("link", { name: "See all matches" })).toHaveAttribute(
      "href",
      "/search?q=Gaucher",
    );
  });

  it("asks for input instead of tracing an empty query", () => {
    const trace = vi.fn(traceQuery);
    render(<AiThinkingOrbAndInput trace={trace} minThinkMs={0} />);
    fireEvent.submit(box().closest("form")!);
    expect(trace).not.toHaveBeenCalled();
    expect(screen.getByText("Type a disease, gene or symptom first.")).toBeInTheDocument();
  });

  it("shows a retry when the atlas is unreachable, then resets to the search", async () => {
    const trace = vi.fn<(q: string) => Promise<TraceResult>>().mockRejectedValue(new Error("x"));
    render(<AiThinkingOrbAndInput trace={trace} minThinkMs={0} />);
    fireEvent.click(screen.getByRole("button", { name: "GBA1" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not trace “GBA1”");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(trace).toHaveBeenCalledTimes(2));
    fireEvent.click(await screen.findByRole("button", { name: "New search" }));
    await waitFor(() => expect(box()).toHaveValue(""));
  });

  it("re-centres on an alternative match and offers the old one back", async () => {
    const result = await found("Gaucher");
    const alternative = result.alternatives[0];
    if (!alternative) throw new Error("mock search should return several Gaucher hits");
    const pick = vi.fn(traceNode);
    render(<AiThinkingOrbAndInput trace={async () => result} pick={pick} minThinkMs={0} />);
    fireEvent.click(screen.getByRole("button", { name: "Gaucher disease" }));
    await screen.findByRole("heading", { level: 2, name: result.match.node.label });

    const chooser = screen.getByText("Not what you meant?").parentElement!;
    fireEvent.click(within(chooser).getByRole("button", { name: alternative.node.label }));

    expect(
      await screen.findByRole("heading", { level: 2, name: alternative.node.label }),
    ).toBeInTheDocument();
    expect(pick).toHaveBeenCalledWith(alternative.node.id);
    expect(within(chooser).getByRole("button", { name: result.match.node.label })).toBeEnabled();
  });
});
