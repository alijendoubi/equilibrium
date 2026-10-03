import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SearchPage from "@/app/search/page";

async function renderSearch(q: string) {
  render(await SearchPage({ searchParams: Promise.resolve({ q }) }));
}

describe("/search", () => {
  it("lists results with type badge and match reason", async () => {
    await renderSearch("GBA1");
    const results = screen.getByRole("list", { name: "Search results" });
    const first = within(results).getAllByRole("listitem")[0]!;

    expect(within(first).getByText("GBA1")).toBeInTheDocument();
    expect(within(first).getByText("Gene")).toBeInTheDocument();
    expect(within(first).getByText("Exact match")).toBeInTheDocument();
    expect(within(first).getByRole("link")).toHaveAttribute("href", "/disease/HGNC%3A4177");
  });

  it("shows the matched synonym for synonym hits", async () => {
    await renderSearch("neuronopathic");
    const item = screen.getByRole("link", { name: /Gaucher disease type III/ });

    expect(within(item).getByText("Synonym match")).toBeInTheDocument();
    expect(within(item).getByText(/chronic neuronopathic Gaucher disease/)).toBeInTheDocument();
  });

  it("finds the honest-gap disease by its placeholder name", async () => {
    await renderSearch("Saposin C deficiency");
    expect(
      screen.getByRole("link", { name: /Gaucher disease due to saposin C deficiency/ }),
    ).toBeInTheDocument();
  });

  it("is honest when nothing matches", async () => {
    await renderSearch("zzqx");
    expect(screen.getByRole("heading", { name: "No match." })).toBeInTheDocument();
    expect(screen.getByText(/We searched: labels, synonyms/)).toBeInTheDocument();
  });
});
