import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import mermaid from "mermaid";
import { api } from "../api/client";

mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });

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

  useEffect(() => {
    let dead = false;
    api
      .architecture(repoId)
      .then(async (a) => {
        if (dead) return;
        setArch(a as Arch);
        try {
          // Parse check BEFORE rendering (spec task 5).
          await mermaid.parse((a as Arch).mermaid);
          const { svg } = await mermaid.render("arch-diagram", (a as Arch).mermaid);
          // Trust boundary (D16.2 note): this SVG is produced by OUR
          // deterministic generator (escaped server-side) through mermaid's
          // DOMPurify-sanitized renderer. Model text NEVER flows into any
          // HTML path — answers render as React text nodes only.
          if (!dead && hostRef.current) {
            hostRef.current.innerHTML = svg;
            setRendered(true);
          }
        } catch (e) {
          if (!dead) setErr(`diagram parse failed, showing list: ${e}`);
        }
      })
      .catch((e) => !dead && setErr(`${e}`));
    return () => {
      dead = true;
    };
  }, [repoId]);

  return (
    <div>
      <h2>Architecture</h2>
      {err && <p className="error">{err}</p>}
      <div ref={hostRef} data-testid="arch-svg" />
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
        <ul>
          {arch.nodes.map((n) => (
            <li key={n.id}>
              <Link
                to={`/code?repo=${repoId}&path=${encodeURIComponent(n.paths[0] ?? "")}&start=1&end=30`}
              >
                {n.label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
