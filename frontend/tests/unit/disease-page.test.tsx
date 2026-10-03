import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import NodePage from "@/app/disease/[id]/page";

async function renderNode(id: string) {
  render(await NodePage({ params: Promise.resolve({ id: encodeURIComponent(id) }) }));
}

describe("/disease/[id]", () => {
  it("renders the summary first: cause, top symptoms, mechanism", async () => {
    await renderNode("MONDO:0009267");
    expect(
      screen.getByRole("heading", { level: 1, name: "Gaucher disease type III" }),
    ).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Summary" });
    expect(within(summary).getByText("GBA1")).toBeInTheDocument();
    expect(within(summary).getByText("Oculomotor apraxia")).toBeInTheDocument();
    expect(
      within(summary).getByText("Lysosomal dysfunction (glucosylceramide breakdown)"),
    ).toBeInTheDocument();
    // The propagated mechanism is inferred, so it is labelled as a hypothesis.
    expect(within(summary).getByText("Hypothesis")).toBeInTheDocument();
  });

  it("renders the three sections as collapsible cards", async () => {
    await renderNode("MONDO:0009267");
    for (const title of ["Who shares this", "What exists", "What next"]) {
      const summaryEl = screen.getByText(title).closest("summary");
      expect(summaryEl).not.toBeNull();
      expect(summaryEl!.closest("details")).toBeInTheDocument();
    }
    expect(screen.getByText("Cure Parkinson's")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Explore connection/ })[0]).toHaveAttribute(
      "href",
      "/path?from=MONDO%3A0009267&to=MONDO%3A1040030",
    );
  });

  it("shows an honest coverage report for the gap disease", async () => {
    await renderNode("MONDO:0012517");
    const report = screen.getByRole("region", { name: "Coverage report" });
    expect(within(report).getByText(/No supported route/)).toBeInTheDocument();
    expect(within(report).getByText(/query.cond=saposin C deficiency/)).toBeInTheDocument();
    expect(screen.getByText("No connected community found yet")).toBeInTheDocument();
  });

  it("lists connections for non-disease nodes", async () => {
    await renderNode("HGNC:4177");
    expect(screen.getByRole("heading", { name: /Connections/ })).toBeInTheDocument();
  });
});
