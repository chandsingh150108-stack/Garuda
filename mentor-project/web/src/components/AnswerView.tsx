import CitationChip from "./CitationChip";
import { isStaleCitation, providerLabel } from "../api/client";
import type { AskResponse, EvidenceRef } from "../api/client";

interface Props {
  repoId: string;
  answer: AskResponse;
  codeHashes: Record<string, string>;
}

/**
 * Plain-text answer rendering (D16.2): segment text is rendered as React
 * text nodes, never as HTML — the raw-HTML injection API is banned in this
 * codebase (see tests/test_web_build.py) and model text never flows into
 * the Mermaid SVG path either.
 */
export default function AnswerView({ repoId, answer, codeHashes }: Props) {
  const byId: Record<string, EvidenceRef> = {};
  for (const e of [...answer.evidence, ...answer.closest]) byId[e.id] = e;

  if (answer.status === "abstain") {
    return (
      <div className="abstain" data-testid="abstain-panel">
        <h3>Not enough evidence — abstained</h3>
        <ul>
          {answer.missing.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ul>
        {answer.closest.length > 0 && <p>Closest evidence:</p>}
        <div className="chips">
          {answer.closest.map((c) => (
            <CitationChip
              key={c.id}
              repoId={repoId}
              citation={c}
              stale={isStaleCitation(c.hash, codeHashes[c.id] ?? "") && !!codeHashes[c.id]}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="answer">
      {answer.segments.map((s, i) => (
        <div key={i} className={`segment segment-${s.kind}`}>
          <p>{s.text}</p>
          <div className="chips">
            {s.evidence_ids.map((eid) =>
              byId[eid] ? (
                <CitationChip
                  key={eid}
                  repoId={repoId}
                  citation={byId[eid]}
                  stale={
                    !!codeHashes[eid] &&
                    isStaleCitation(byId[eid].hash, codeHashes[eid])
                  }
                />
              ) : (
                <span key={eid} className="chip chip-broken">
                  [{eid}?]
                </span>
              )
            )}
          </div>
          {s.kind !== "fact" && <span className="kind-tag">{s.kind}</span>}
        </div>
      ))}
      <p className="provider" data-testid="provider-label">
        {providerLabel(answer)} · {answer.model} · repairs {answer.repairs}
        {answer.cached ? " · cached" : ""}
      </p>
    </div>
  );
}
