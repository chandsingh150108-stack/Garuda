import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import AnswerView from "../src/components/AnswerView";
import type { AskResponse } from "../src/api/client";

afterEach(() => cleanup());

const BASE: AskResponse = {
  status: "answer",
  segments: [],
  missing: [],
  evidence: [{ id: "E1", path: "a.py", lines: "1-5", hash: "h" }],
  closest: [],
  repairs: 0,
  model: "m",
  provider: "llamacpp",
  prompt_version: "p9v2",
  cached: false,
  fallback: false,
  cloud_status: "local-only",
};

describe("answer view", () => {
  it("renders script payloads as text, never HTML", () => {
    const answer: AskResponse = {
      ...BASE,
      segments: [
        {
          text: "<script>alert(1)</script> and <img src=x onerror=y>",
          kind: "fact",
          evidence_ids: ["E1"],
        },
      ],
    };
    const { container } = render(
      <MemoryRouter>
        <AnswerView repoId="fst" answer={answer} codeHashes={{}} />
      </MemoryRouter>
    );
    // No script/img elements created: text only.
    expect(container.querySelectorAll("script").length).toBe(0);
    expect(container.querySelectorAll("img").length).toBe(0);
    expect(screen.getByTestId("answer").textContent).toContain("<script>");
  });

  it("renders abstention with the missing list and no answer citations", () => {
    const answer: AskResponse = {
      ...BASE,
      status: "abstain",
      missing: ["no billing code in evidence"],
      closest: [{ id: "E2", path: "b.py", lines: "3-9", hash: "" }],
    };
    render(
      <MemoryRouter>
        <AnswerView repoId="fst" answer={answer} codeHashes={{}} />
      </MemoryRouter>
    );
    const panel = screen.getByTestId("abstain-panel");
    expect(panel.textContent).toContain("no billing code in evidence");
    expect(screen.queryByTestId("answer")).toBeNull();
  });

  it("shows the provider label", () => {
    render(
      <MemoryRouter>
        <AnswerView repoId="fst" answer={BASE} codeHashes={{}} />
      </MemoryRouter>
    );
    expect(screen.getByTestId("provider-label").textContent).toContain("LOCAL");
  });
});
