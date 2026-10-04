import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GlobalSearch } from "@/components/GlobalSearch";
import { routerMock } from "../../vitest.setup";

describe("GlobalSearch", () => {
  it("navigates to /search?q= with the trimmed query on submit", () => {
    render(<GlobalSearch />);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search the atlas" }), {
      target: { value: "  Gaucher disease " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(routerMock.push).toHaveBeenCalledWith("/search?q=Gaucher+disease");
  });

  it("does not navigate on an empty query and explains why", () => {
    render(<GlobalSearch />);
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(routerMock.push).not.toHaveBeenCalled();
    expect(screen.getByText("Type a disease, gene or symptom first.")).toBeInTheDocument();
    expect(screen.getByRole("searchbox")).toHaveAttribute("aria-invalid", "true");
  });

  it("offers the three example chips as search links", () => {
    render(<GlobalSearch />);
    expect(screen.getByRole("link", { name: "Gaucher disease" })).toHaveAttribute(
      "href",
      "/search?q=Gaucher+disease",
    );
    expect(screen.getByRole("link", { name: "GBA1" })).toHaveAttribute("href", "/search?q=GBA1");
    expect(screen.getByRole("link", { name: "Saposin C deficiency" })).toHaveAttribute(
      "href",
      "/search?q=Saposin+C+deficiency",
    );
  });
});
