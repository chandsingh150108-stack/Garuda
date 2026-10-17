import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import mermaid from "mermaid";
import { api } from "../api/client";
import { THEME_EVENT, getTheme, mermaidBaseConfig } from "../theme";

interface ArchNode {
  id: string;
  kind: string;
  label: string;
  paths: string[];
  evidence: { chunk_id: string; path: string; lines: string }[];
}

interface Arch {
  nodes: ArchNode[];
  edges: { from: string; to: string; kind: string }[];
  mermaid: string;
}

/** Architecture view: browser-side Mermaid parse check first; on failure the
 * deterministic component list renders instead. Nodes link to code. */
export default function Architecture({ repoId }: { repoId: string }) {
  const [arch, setArch] = useState<Arch | null>(null);
  const [rendered, setRendered] = useState(false);
  const [err, setErr] = useState("");
  const hostRef = useRef<HTMLDivElement>(null);
  const archRef = useRef<Arch | null>(null);

  async function renderDiagram(a: Arch): Promise<boolean> {
    try {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        ...mermaidBaseConfig(getTheme()),
      });
      // Parse check BEFORE rendering (spec task 5).
      await mermaid.parse(a.mermaid);
      const { svg } = await mermaid.render("arch-diagram", a.mermaid);
      // Trust boundary (D16.2 note): this SVG is produced by OUR
      // deterministic generator (escaped server-side) through mermaid's
      // DOMPurify-sanitized renderer. Model text NEVER flows into any
      // HTML path — answers render as React text nodes only.
      if (hostRef.current) {
        hostRef.current.innerHTML = svg;
        setErr("");
        return true;
      }
      return false;
    } catch (e) {
      setErr(`diagram parse failed, showing list: ${e}`);
      return false;
    }
  }

  useEffect(() => {
    let dead = false;
    setErr("");
    api
      .architecture(repoId)
      .then(async (a) => {
        if (dead) return;
        const typed = a as Arch;
        archRef.current = typed;
        setArch(typed);
        if (await renderDiagram(typed)) {
          if (!dead) setRendered(true);
        }
      })
      .catch((e) => !dead && setErr(`${e}`));
    return () => {
      dead = true;
    };
  }, [repoId]);

  // Re-render the diagram when the theme flips so Mermaid follows it.
  useEffect(() => {
    const onTheme = async () => {
      if (archRef.current) {
        setRendered(false);
        if (await renderDiagram(archRef.current)) setRendered(true);
      }
    };
    window.addEventListener(THEME_EVENT, onTheme);
    return () => window.removeEventListener(THEME_EVENT, onTheme);
  }, []);

  return (
    <div>
      <h2>Architecture</h2>
      <p className="page-sub">
        Built from import and route facts — the model only wrote the short
        labels. Click any component to open its code.
      </p>
      {err && <p className="error">{err}</p>}
      <div ref={hostRef} data-testid="arch-svg" className="diagram-frame" />
      {(!rendered || err) && arch && (
        <ul data-testid="arch-list">
          {arch.nodes.map((n) => (
            <li key={n.id}>
              {n.label} ({n.kind})
            </li>
          ))}
        </ul>
      )}
      {arch && (
        <ul className="arch-grid">
          {arch.nodes.map((n) => {
            const target = n.paths[0] ?? n.evidence[0]?.path;
            return (
              <li key={n.id}>
                {target ? (
                  <Link
                    className="arch-node"
                    to={`/code?repo=${repoId}&path=${encodeURIComponent(target)}&start=1&end=30`}
                  >
                    <strong>{n.label}</strong>
                    <span className="arch-kind">{n.kind}</span>
                  </Link>
                ) : (
                  <div className="arch-node">
                    <strong>{n.label}</strong>
                    <span className="arch-kind">{n.kind}</span>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
