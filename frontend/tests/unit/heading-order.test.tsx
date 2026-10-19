import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CoverageReportCard } from "@/components/CoverageReportCard";
import { MapLegend } from "@/components/graph/MapLegend";
import { getAtlasClient } from "@/lib/api/client";

// Headings must not skip levels (axe "heading-order"): each card takes its level from its parent.

async function gapReport() {
  const report = await getAtlasClient().getCoverage("MONDO:0012517");
  if (!report) throw new Error("mock data should have a coverage report for the gap disease");
  return report;
}

describe("heading order", () => {
  it("coverage report headings default to h4 and can sit one level higher", async () => {
    const report = await gapReport();
    const { unmount } = render(<CoverageReportCard report={report} />);
    expect(screen.getByRole("heading", { level: 4, name: "Searched" })).toBeInTheDocument();
    unmount();

    render(<CoverageReportCard report={report} headingLevel={3} />);
    expect(screen.getByRole("heading", { level: 3, name: "Searched" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 4 })).not.toBeInTheDocument();
  });

  it("the map legend is an h2 on the full map and an h3 in a compact map", () => {
    const { unmount } = render(<MapLegend types={["disease", "gene"]} />);
    expect(screen.getByRole("heading", { level: 2, name: "Legend" })).toBeInTheDocument();
    unmount();

    render(<MapLegend types={["disease", "gene"]} compact />);
    expect(screen.getByRole("heading", { level: 3, name: "Legend" })).toBeInTheDocument();
  });
});
