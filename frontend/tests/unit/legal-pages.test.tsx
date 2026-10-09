import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AboutPage from "@/app/about/page";
import DisclaimerPage from "@/app/disclaimer/page";
import PrivacyPage from "@/app/privacy/page";
import TermsPage from "@/app/terms/page";
import { SiteFooter } from "@/components/SiteFooter";

describe("legal and about pages", () => {
  it.each([
    ["About", AboutPage, "About Equilibrium"],
    ["Disclaimer", DisclaimerPage, "Medical disclaimer"],
    ["Privacy", PrivacyPage, "Privacy"],
    ["Terms", TermsPage, "Terms of use"],
  ])("%s renders its title and a last-updated date", (_name, Page, title) => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
    expect(screen.getByText(/Last updated/)).toBeInTheDocument();
  });

  it("the disclaimer leads with 'not medical advice'", () => {
    render(<DisclaimerPage />);
    expect(screen.getByText(/It is not medical advice/)).toBeInTheDocument();
  });

  it("the privacy page states there are no cookies or accounts", () => {
    render(<PrivacyPage />);
    expect(screen.getByText(/No cookies, local storage or tracking pixels/)).toBeInTheDocument();
    expect(
      screen.getByText(/No accounts, names, email addresses or passwords/),
    ).toBeInTheDocument();
  });
});

describe("SiteFooter", () => {
  it("links every legal page and the source", () => {
    render(<SiteFooter />);
    const nav = screen.getByRole("navigation", { name: "Legal and project" });
    for (const [name, href] of [
      ["About", "/about"],
      ["Medical disclaimer", "/disclaimer"],
      ["Privacy", "/privacy"],
      ["Terms", "/terms"],
    ]) {
      expect(within(nav).getByRole("link", { name })).toHaveAttribute("href", href);
    }
    expect(within(nav).getByRole("link", { name: "Source on GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/alijendoubi/equilibrium",
    );
  });
});
