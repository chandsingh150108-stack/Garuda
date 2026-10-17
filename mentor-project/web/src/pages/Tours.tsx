import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import mermaid from "mermaid";
import { api } from "../api/client";
import { THEME_EVENT, getTheme, mermaidBaseConfig } from "../theme";

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
  const [tourName, setTourName] = useState("");
  const [at, setAt] = useState(0);
  const [err, setErr] = useState("");
  const [themeTick, setThemeTick] = useState(0);
  const seqRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .tours(repoId)
      .then((t) => setNames(t as { name: string; question: string }[]))
      .catch((e) => setErr(`${e}`));
  }, [repoId]);

  useEffect(() => {
    const onTheme = () => setThemeTick((n) => n + 1);
    window.addEventListener(THEME_EVENT, onTheme);
    return () => window.removeEventListener(THEME_EVENT, onTheme);
  }, []);

  async function renderSequence(name: string, sequence: string) {
    try {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        ...mermaidBaseConfig(getTheme()),
      });
      await mermaid.parse(sequence);
      const { svg } = await mermaid.render(`tour-${name}`, sequence);
      if (seqRef.current) seqRef.current.innerHTML = svg;
    } catch (e) {
      setErr(`sequence parse failed: ${e}`);
    }
  }

  // Re-render the diagram when the theme flips (themeTick) or a tour opens.
  useEffect(() => {
    if (tour) renderSequence(tourName, tour.sequence);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [themeTick]);

  async function open(name: string) {
    setErr("");
    try {
      const t = (await api.tour(repoId, name)) as Tour;
      setTour(t);
      setTourName(name);
      setAt(0);
      await renderSequence(name, t.sequence);
    } catch (e) {
      setErr(`${e}`);
    }
  }

  const step = tour?.steps[at];
  const pct = tour ? Math.round(((at + 1) / tour.steps.length) * 100) : 0;

  return (
    <div>
      <h2>Guided tours</h2>
      <p className="page-sub">
        Follow a request through the code, step by step — every hop cites its lines.
      </p>
      {err && <p className="error">{err}</p>}
      <ul className="tour-list">
        {names.map((t) => (
          <li key={t.name}>
            <button onClick={() => open(t.name)}>
              <span className="tour-go" aria-hidden="true">
                ›
              </span>{" "}
              {t.question}
            </button>
          </li>
        ))}
      </ul>
      {tour && (
        <div data-testid="tour-steps" className="card">
          <h3>
            {tour.question}
            {tour.stale && <span className="risk-flag"> stale</span>}
          </h3>
          <div className="tour-progress" aria-label={`Step ${at + 1} of ${tour.steps.length}`}>
            <div style={{ width: `${pct}%` }} />
          </div>
          <div className="tour-dots" aria-hidden="true">
            {tour.steps.map((s, i) => (
              <button
                key={s.n}
                tabIndex={-1}
                className={`tour-dot${i < at ? " done" : ""}${i === at ? " now" : ""}`}
                onClick={() => setAt(i)}
              >
                {i + 1}
              </button>
            ))}
          </div>
          <div ref={seqRef} data-testid="tour-sequence" className="diagram-frame" />
          {step && (
            <div>
              <p>
                <span
                  className={`hop-badge ${step.hop === "calls" ? "hop-calls" : "hop-likely"}`}
                >
                  {step.hop === "calls" ? "calls" : "likely call"}
                </span>
                <strong>
                  Step {at + 1}/{tour.steps.length}: {step.title}
                </strong>
              </p>
              <p>{step.explanation}</p>
              <p>
                <Link
                  className="code-link"
                  to={`/code?repo=${repoId}&path=${encodeURIComponent(step.file)}&start=${step.start}&end=${step.end}`}
                >
                  {step.file}:{step.start}-{step.end}
                </Link>
                {step.narrated_by === "deterministic" && (
                  <span className="kind-tag"> deterministic</span>
                )}
              </p>
              <div>
                <button
                  className="ghost"
                  disabled={at === 0}
                  onClick={() => setAt(at - 1)}
                >
                  ← Prev
                </button>
                <button
                  disabled={at >= tour.steps.length - 1}
                  onClick={() => setAt(at + 1)}
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
