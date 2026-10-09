import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RouteError from "@/app/error";

describe("route error boundary", () => {
  it("explains the failure, focuses the heading and offers a way out", () => {
    render(<RouteError error={new Error("boom")} reset={() => {}} />);
    const heading = screen.getByRole("heading", {
      level: 1,
      name: "Something went wrong on this page",
    });
    expect(heading).toHaveFocus();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to search" })).toHaveAttribute("href", "/");
  });

  it("retries in place", () => {
    const reset = vi.fn();
    render(<RouteError error={new Error("boom")} reset={reset} />);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledOnce();
  });

  it("shows the server digest as a support reference, never the raw message", () => {
    const error = Object.assign(new Error("secret internal detail"), { digest: "3814127394" });
    render(<RouteError error={error} reset={() => {}} />);
    expect(screen.getByText("3814127394")).toBeInTheDocument();
    expect(screen.queryByText(/secret internal detail/)).not.toBeInTheDocument();
  });

  it("omits the reference line when there is no digest", () => {
    render(<RouteError error={new Error("client-side")} reset={() => {}} />);
    expect(screen.queryByText(/this reference/)).not.toBeInTheDocument();
  });
});
