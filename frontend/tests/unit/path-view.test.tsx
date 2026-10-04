import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PathPage from "@/app/path/page";

async function renderPath(from: string, to: string) {
  render(await PathPage({ searchParams: Promise.resolve({ from, to }) }));
}

describe("/path", () => {
  it("renders the chain disease -> gene -> mechanism -> disease -> org -> study", async () => {
    await renderPath("MONDO:0009267", "clinicaltrials:NCT05778617");
    const route = screen.getByRole("region", { name: "Route 1" });
    const links = within(route)
      .getAllByRole("link")
      .map((a) => a.textContent);
    expect(links).toEqual([
      "DiseaseGaucher disease type III",
      "GeneGBA1",
      "MechanismLysosomal dysfunction (glucosylceramide breakdown)",
      "Diseaselate-onset Parkinson disease",
      "Patient groupCure Parkinson's",
      "StudyASPro-PD: Ambroxol to Slow Progression in Parkinson Disease",
    ]);
  });

  it("draws inferred links dashed with a hypothesis label, data links solid", async () => {
    await renderPath("MONDO:0009267", "clinicaltrials:NCT05778617");
    const route = screen.getByRole("region", { name: "Route 1" });
    const buttons = within(route).getAllByRole("button");

    const inferred = buttons.find((b) => b.dataset.evidence === "inferred")!;
    const curated = buttons.find((b) => b.dataset.evidence === "curated")!;
    expect(within(inferred).getByTestId("edge-line")).toHaveClass("border-dashed");
    expect(within(inferred).getByText(/hypothesis/)).toBeInTheDocument();
    expect(within(curated).getByTestId("edge-line")).toHaveClass("border-solid");
    expect(within(curated).queryByText(/hypothesis/)).toBeNull();
  });

  it("shows the selected edge's source, date, confidence and quote in the side panel", async () => {
    await renderPath("MONDO:0009267", "clinicaltrials:NCT05778617");
    const route = screen.getByRole("region", { name: "Route 1" });
    fireEvent.click(within(route).getByRole("button", { name: /Cure Parkinson's funds ASPro-PD/ }));

    const panel = screen.getByRole("complementary", { name: "Edge evidence" });
    expect(within(panel).getByRole("link", { name: /curated · org-site/ })).toHaveAttribute(
      "href",
      "https://cureparkinsons.org.uk/2023/01/phase-3-trial-ambroxol-in-parkinsons/",
    );
    expect(within(panel).getByText("3 Oct 2026")).toBeInTheDocument();
    expect(within(panel).getByText("0.65")).toBeInTheDocument();
    expect(within(panel).getByText(/strategic partners/)).toBeInTheDocument();
  });

  it("explains an inferred edge in the panel as a hypothesis", async () => {
    await renderPath("MONDO:0009267", "clinicaltrials:NCT05778617");
    const route = screen.getByRole("region", { name: "Route 1" });
    fireEvent.click(within(route).getByRole("button", { name: /Hypothesis, confidence 0.62/ }));

    const panel = screen.getByRole("complementary", { name: "Edge evidence" });
    expect(within(panel).getByText("Hypothesis")).toBeInTheDocument();
    expect(within(panel).getByText(/A hypothesis, not proof/)).toBeInTheDocument();
    expect(within(panel).getByText("E:93468e247aa8c342, E:0123bcf2d717e9f0")).toBeInTheDocument();
  });

  it("URL-encodes CURIE ids and shows the trial id without its namespace", async () => {
    await renderPath("MONDO:0009267", "clinicaltrials:NCT05778617");
    const route = screen.getByRole("region", { name: "Route 1" });
    expect(within(route).getByRole("link", { name: /ASPro-PD/ })).toHaveAttribute(
      "href",
      "/disease/clinicaltrials%3ANCT05778617",
    );
    expect(screen.getByRole("link", { name: /Back to Gaucher disease type III/ })).toHaveAttribute(
      "href",
      "/disease/MONDO%3A0009267",
    );
  });

  it("is honest when no route exists", async () => {
    await renderPath("MONDO:0012517", "clinicaltrials:NCT05778617");
    expect(screen.getByText("No supported route between these two.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Coverage report" })).toBeInTheDocument();
  });
});
