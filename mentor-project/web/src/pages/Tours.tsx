import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import mermaid from "mermaid";
import { api } from "../api/client";

mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });

interface Step {
  n: number;
  symbol: string;
  file: string;
  start: number;
  end: number;
  hop: string;
  hop_detail: string;
  title: string;
  explanation: string;
  narrated_by: string;
  evidence: { chunk_id: string; path: string; lines: string }[];
}

interface Tour {
  name: string;
  question: string;
  steps: Step[];
  sequence: string;
  stale: boolean;
}

/** Tours: list, stepper with sequence diagram, per-step code links. */
export default function Tours({ repoId }: { repoId: string }) {
  const [names, setNames] = useState<{ name: string; question: string }[]>([]);
  const [tour, setTour] = useState<Tour | null>(null);
  const [at, setAt] = useState(0);
  const [err, setErr] = useState("");
  const seqRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .tours(repoId)
      .then((t) => setNames(t as { name: string; question: string }[]))
      .catch((e) => setErr(`${e}`));
  }, [repoId]);

  async function open(name: string) {
    setErr("");
    try {
      const t = (await api.tour(repoId, name)) as Tour;
      setTour(t);
      setAt(0);
      try {
        await mermaid.parse(t.sequence);
        const { svg } = await mermaid.render(`tour-${name}`, t.sequence);
        if (seqRef.current) seqRef.current.innerHTML = svg;
      } catch (e) {
        setErr(`sequence parse failed: ${e}`);
      }
    } catch (e) {
      setErr(`${e}`);
    }
  }

  const step = tour?.steps[at];

  return (
    <div>
      <h2>Tours</h2>
      {err && <p className="error">{err}</p>}
      <ul>
        {names.map((t) => (
          <li key={t.name}>
            <button onClick={() => open(t.name)}>{t.question}</button>
          </li>
        ))}
      </ul>
      {tour && (
        <div data-testid="tour-steps">
          <h3>{tour.question}</h3>
          <div ref={seqRef} data-testid="tour-sequence" />
          {step && (
            <div>
              <p>
                Step {at + 1}/{tour.steps.length}: {step.title}
              </p>
              <p>{step.explanation}</p>
              <Link
                to={`/code?repo=${repoId}&path=${encodeURIComponent(step.file)}&start=${step.start}&end=${step.end}`}
              >
                {step.file}:{step.start}-{step.end}
              </Link>
              <div>
                <button disabled={at === 0} onClick={() => setAt(at - 1)}>
                  Prev
                </button>
                <button
                  disabled={at >= tour.steps.length - 1}
                  onClick={() => setAt(at + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
