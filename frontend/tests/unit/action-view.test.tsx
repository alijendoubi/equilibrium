import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ActionsPage from "@/app/actions/[id]/page";
import NodePage from "@/app/disease/[id]/page";
import { splitPoints } from "@/components/actions/ActionPlan";
import { ExplainPanel, TEMPLATE_LABEL } from "@/components/explain/ExplainPanel";
import { mockClient, type AtlasClient } from "@/lib/api/client";
import type { ExplainResponse } from "@/lib/api/types";

async function renderActions(id: string) {
  render(await ActionsPage({ params: Promise.resolve({ id: encodeURIComponent(id) }) }));
}

function stubClient(response: ExplainResponse): () => AtlasClient {
  return () => ({ ...mockClient, explain: vi.fn().mockResolvedValue(response) });
}

const AI_RESPONSE: ExplainResponse = {
  steps: [
    {
      text: "Gaucher disease type II is caused by changes in GBA1.",
      edge_ids: ["E:61528699fb974eda"],
      is_hypothesis: false,
    },
    {
      text: "Parkinson's may share the same lysosomal problem.",
      edge_ids: ["E:36c6e1a96c92e376"],
      is_hypothesis: true,
    },
  ],
  summary: "Both communities study the same enzyme.",
  caveats: ["The shared mechanism is a hypothesis."],
  source: "live",
  model: "gpt-5-mini",
  prompt_version: "explain-v1",
  ai_generated: true,
};

describe("/actions/[id] (patient action view)", () => {
  it("lists partners with why, reusable assets with reusable vs what differs, and a checklist", async () => {
    await renderActions("MONDO:0009266");
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "What to do next for Gaucher disease type II",
      }),
    ).toBeInTheDocument();

    const partners = screen.getByRole("region", { name: "Who to talk to" });
    expect(within(partners).getByText("Cure Parkinson's")).toBeInTheDocument();
    expect(within(partners).getByText(/Funds ASPro-PD/)).toBeInTheDocument();

    const assets = screen.getByRole("region", { name: "What you can reuse" });
    expect(within(assets).getByText(/ASPro-PD: Ambroxol/)).toBeInTheDocument();
    const reusable = within(assets).getByRole("group", { name: "Reusable" });
    const differs = within(assets).getByRole("group", { name: "What differs" });
    expect(within(reusable).getByText(/Ambroxol dosing and safety monitoring/)).toBeInTheDocument();
    expect(within(differs).getAllByRole("listitem").length).toBeGreaterThan(1);

    const checklist = screen.getByRole("region", { name: "Check with an expert before acting" });
    expect(within(checklist).getAllByRole("checkbox").length).toBe(4);
  });

  it("marks the next experiment as a hypothesis with dashed styling", async () => {
    await renderActions("MONDO:0009266");
    const next = screen.getByRole("region", { name: /Next experiment/ });
    expect(next).toHaveClass("border-dashed");
    expect(within(next).getByText("hypothesis")).toBeInTheDocument();
  });

  it("opens the evidence panel from a cited edge chip", async () => {
    await renderActions("MONDO:0009266");
    const partners = screen.getByRole("region", { name: "Who to talk to" });
    fireEvent.click(within(partners).getAllByRole("button", { name: /E:3fe1decec2edca53/ })[0]!);
    const panel = screen.getAllByRole("complementary", { name: "Edge evidence" })[0]!;
    expect(within(panel).getByText(/funds/)).toBeInTheDocument();
  });

  it("drafts a template brief in mock mode, labelled as not AI", async () => {
    await renderActions("MONDO:0009266");
    fireEvent.click(screen.getAllByRole("button", { name: "Draft collaboration brief" })[1]!);
    const brief = await screen.findByRole("region", {
      name: "Collaboration brief: Gaucher disease type II and Cure Parkinson's",
    });
    expect(await within(brief).findByText(TEMPLATE_LABEL)).toBeInTheDocument();
    expect(within(brief).queryByText(/^AI-generated/)).toBeNull();
    // The brief explains the route disease -> GBA1 -> Parkinson's -> ASPro-PD -> Cure Parkinson's.
    expect(
      within(brief)
        .getAllByRole("listitem")
        .filter((li) => li.dataset.hypothesis !== undefined),
    ).toHaveLength(4);
  });

  it("shows the gap card for saposin C deficiency", async () => {
    await renderActions("MONDO:0012517");
    const gap = screen.getByRole("region", { name: /No community found yet/ });
    expect(within(gap).getByText("Help build the missing community")).toBeInTheDocument();
    expect(within(gap).getByText(/query.cond=saposin C deficiency/)).toBeInTheDocument();
    expect(within(gap).getAllByText(/International Gaucher Alliance/).length).toBeGreaterThan(0);
    expect(within(gap).getByText(/Would Gaucher natural history registries/)).toBeInTheDocument();
  });
});

describe("gap card on the disease page", () => {
  it("shows the gap card first for MONDO:0012517 with a call to action", async () => {
    render(await NodePage({ params: Promise.resolve({ id: "MONDO%3A0012517" }) }));
    const gap = screen.getByRole("region", { name: /No community found yet/ });
    expect(
      within(gap).getByRole("link", { name: /Contact International Gaucher Alliance/ }),
    ).toHaveAttribute("href", "https://www.gaucheralliance.org");
    expect(screen.getAllByRole("region", { name: "Coverage report" })).toHaveLength(1);
  });

  it("links a supported disease to its action view with an encoded id", async () => {
    render(await NodePage({ params: Promise.resolve({ id: "MONDO%3A0009266" }) }));
    expect(screen.getByRole("link", { name: /What to do next/ })).toHaveAttribute(
      "href",
      "/actions/MONDO%3A0009266",
    );
  });
});

describe("ExplainPanel labels", () => {
  const props = {
    edgeIds: ["E:61528699fb974eda", "E:36c6e1a96c92e376"],
    edges: [],
    nodes: [],
    triggerLabel: "Explain this path",
    title: "Route 1 in plain language",
  };

  it("shows 'AI-generated (<model>)' only when ai_generated is true", async () => {
    render(<ExplainPanel {...props} getClient={stubClient(AI_RESPONSE)} />);
    fireEvent.click(screen.getByRole("button", { name: "Explain this path" }));
    expect(await screen.findByText("AI-generated (gpt-5-mini)")).toBeInTheDocument();
    expect(screen.queryByText(TEMPLATE_LABEL)).toBeNull();
  });

  it("shows the neutral template label when ai_generated is false", async () => {
    const template = {
      ...AI_RESPONSE,
      source: "template" as const,
      model: null,
      ai_generated: false,
    };
    render(<ExplainPanel {...props} getClient={stubClient(template)} />);
    fireEvent.click(screen.getByRole("button", { name: "Explain this path" }));
    expect(await screen.findByText(TEMPLATE_LABEL)).toBeInTheDocument();
    expect(screen.queryByText(/^AI-generated/)).toBeNull();
  });

  it("draws hypothesis steps dashed with a label, and lists caveats", async () => {
    render(<ExplainPanel {...props} getClient={stubClient(AI_RESPONSE)} />);
    fireEvent.click(screen.getByRole("button", { name: "Explain this path" }));
    const items = await screen.findAllByRole("listitem");
    const steps = items.filter((li) => li.dataset.hypothesis !== undefined);
    expect(steps[0]).toHaveClass("border-solid");
    expect(steps[1]).toHaveClass("border-dashed");
    expect(within(steps[1]!).getByText("hypothesis")).toBeInTheDocument();
    expect(screen.getByText("The shared mechanism is a hypothesis.")).toBeInTheDocument();
  });

  it("re-asks for the other audience and copies the brief", async () => {
    const explain = vi.fn().mockResolvedValue(AI_RESPONSE);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<ExplainPanel {...props} getClient={() => ({ ...mockClient, explain })} />);
    fireEvent.click(screen.getByRole("button", { name: "Explain this path" }));
    await screen.findByText(AI_RESPONSE.summary);
    fireEvent.click(screen.getByRole("button", { name: "For researchers" }));
    await screen.findByText(AI_RESPONSE.summary);
    expect(explain).toHaveBeenLastCalledWith(props.edgeIds, "researcher");
    fireEvent.click(screen.getByRole("button", { name: "Copy text" }));
    expect(await screen.findByText("Copied")).toBeInTheDocument();
    expect(writeText.mock.calls[0]![0]).toContain("Route 1 in plain language");
  });
});

describe("splitPoints", () => {
  it("splits on sentence ends and semicolons", () => {
    expect(splitPoints("Dosing; safety. Adults only.")).toEqual([
      "Dosing",
      "safety.",
      "Adults only.",
    ]);
  });
});
