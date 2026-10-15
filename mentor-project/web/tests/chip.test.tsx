import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import CitationChip from "../src/components/CitationChip";
import { isStaleCitation } from "../src/api/client";

afterEach(() => cleanup());

describe("citation chip", () => {
  const ref = { id: "E1", path: "a.py", lines: "10-15", hash: "abc" };

  it("renders path, range, and links to the exact code location", () => {
    render(
      <MemoryRouter>
        <CitationChip repoId="fst" citation={ref} stale={false} />
      </MemoryRouter>
    );
    const chip = screen.getByTestId("chip-E1");
    expect(chip.textContent).toContain("[E1]");
    expect(chip.getAttribute("href")).toContain("path=a.py");
    expect(chip.getAttribute("href")).toContain("start=10");
    expect(chip.getAttribute("href")).toContain("end=15");
  });

  it("shows the stale badge on hash mismatch", () => {
    expect(isStaleCitation("abc", "def")).toBe(true);
    expect(isStaleCitation("abc", "abc")).toBe(false);
    expect(isStaleCitation("", "abc")).toBe(false);
    expect(isStaleCitation(undefined, "abc")).toBe(false);
    const { container } = render(
      <MemoryRouter>
        <CitationChip repoId="fst" citation={ref} stale={true} />
      </MemoryRouter>
    );
    expect(container.textContent).toContain("stale");
  });
});
