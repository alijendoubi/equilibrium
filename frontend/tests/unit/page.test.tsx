import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "@/app/page";

describe("HomePage", () => {
  it("renders the product name", () => {
    render(<HomePage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Equilibrium · Rare Disease Atlas" }),
    ).toBeInTheDocument();
  });

  it("renders Maria's three questions", () => {
    render(<HomePage />);
    for (const question of [
      "Who shares our disease characteristics?",
      "What useful work already exists?",
      "What should we do together next?",
    ]) {
      expect(screen.getByRole("heading", { level: 3, name: question })).toBeInTheDocument();
    }
  });

  it("exposes the global search input with an accessible label", () => {
    render(<HomePage />);
    const input = screen.getByLabelText("Search the atlas");
    expect(input).toHaveAttribute("type", "search");
    expect(input).toHaveAttribute(
      "placeholder",
      'Search a disease, gene, or symptom — e.g. "GBA1"',
    );
    expect(screen.getByRole("searchbox", { name: "Search the atlas" })).toBe(input);
  });
});
