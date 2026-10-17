import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { codeMock } = vi.hoisted(() => ({ codeMock: vi.fn() }));
vi.mock("../src/api/client", () => ({ api: { code: codeMock } }));

import Code from "../src/pages/Code";

afterEach(() => cleanup());

beforeEach(() => {
  codeMock.mockReset();
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }),
  });
});

describe("code view", () => {
  it("plain view shows the full file with the evidence range highlighted", async () => {
    const lines = Array.from({ length: 60 }, (_, i) => `L${i + 1}`);
    codeMock.mockResolvedValue({
      path: "a.py",
      sha: "abc123def456",
      start: 10,
      end: 12,
      text: lines.join("\n"),
      truncated: false,
      content_hash: "h",
    });
    const url = "/code?repo=fst&path=a.py&start=10&end=12&plain=1";
    window.history.pushState({}, "", url);
    const { container } = render(
      <MemoryRouter initialEntries={[url]}>
        <Code />
      </MemoryRouter>
    );
    await screen.findByTestId("plain-view");
    expect(codeMock).toHaveBeenCalledWith("fst", "a.py", 10, 12, true);
    expect(screen.getByText("L60")).toBeTruthy();
    expect(screen.getByText("1").textContent).toBe("1");
    expect(screen.getByText("60").textContent).toBe("60");
    expect(screen.getByTestId("sha-banner").textContent).toContain(
      "a.py:10-12 @ abc123def456"
    );
    const hl = container.querySelectorAll(".hl-range");
    expect(hl.length).toBe(3);
    expect(hl[0].textContent).toContain("L10");
    expect(hl[2].textContent).toContain("L12");
  });
});
