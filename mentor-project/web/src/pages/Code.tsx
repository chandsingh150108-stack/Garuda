import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { THEME_EVENT, getTheme } from "../theme";

function usePlain(): boolean {
  return new URLSearchParams(window.location.search).get("plain") === "1";
}

/** Read-only code view: full file with the requested range highlighted +
 * SHA banner. Falls back to a plain line-numbered view if Monaco fails
 * (recorded rollback). */
export default function Code() {
  const [params] = useSearchParams();
  const repo = params.get("repo") ?? "fst";
  const path = params.get("path") ?? "";
  const start = Number(params.get("start") ?? 1);
  const end = Number(params.get("end") ?? start);
  const wantHash = params.get("hash") ?? "";
  const [text, setText] = useState<string | null>(null);
  const [sha, setSha] = useState("");
  const [hash, setHash] = useState("");
  const [err, setErr] = useState("");
  const [theme, setTheme] = useState(getTheme());
  const hostRef = useRef<HTMLDivElement>(null);
  const plain = usePlain();

  useEffect(() => {
    const onTheme = () => setTheme(getTheme());
    window.addEventListener(THEME_EVENT, onTheme);
    return () => window.removeEventListener(THEME_EVENT, onTheme);
  }, []);

  useEffect(() => {
    let dead = false;
    api
      .code(repo, path, start, end, true)
      .then((c) => {
        if (dead) return;
        setText(c.text);
        setSha(c.sha);
        setHash(c.content_hash);
      })
      .catch((e) => !dead && setErr(`${e}`));
    return () => {
      dead = true;
    };
  }, [repo, path, start, end]);

  useEffect(() => {
    if (plain || text === null || !hostRef.current) return;
    let editor: { dispose(): void } | null = null;
    let dead = false;
    (async () => {
      try {
        // Lazy Monaco: a top-level import crashes the whole bundle if the
        // editor environment fails; dynamic import keeps the app alive and
        // falls back to the plain view (recorded rollback).
        const monaco = await import("monaco-editor");
        if (dead || !hostRef.current) return;
        // Syntax tokenizers run in web workers; without this the editor
        // renders monochrome. Workers are same-origin build assets (CSP
        // worker-src 'self'), not blob: URLs.
        const [{ default: EditorWorker }, { default: TsWorker }] =
          await Promise.all([
            import("monaco-editor/esm/vs/editor/editor.worker?worker"),
            import("monaco-editor/esm/vs/language/typescript/ts.worker?worker"),
          ]);
        (self as unknown as {
          MonacoEnvironment: {
            getWorker: (workerId: string, label: string) => Worker;
          };
        }).MonacoEnvironment = {
          getWorker: (_workerId, label) =>
            label === "typescript" ? new TsWorker() : new EditorWorker(),
        };
        const ed = monaco.editor.create(hostRef.current, {
          value: text,
          language: path.endsWith(".py")
            ? "python"
            : path.endsWith(".md")
              ? "markdown"
              : "typescript",
          theme: theme === "dark" ? "vs-dark" : "vs",
          readOnly: true,
          domReadOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          padding: { top: 10 },
        });
        editor = ed;
        ed.deltaDecorations(
          [],
          [
            {
              range: new monaco.Range(start, 1, end, 1),
              options: { inlineClassName: "hl-range" },
            },
          ]
        );
        ed.revealLinesInCenter(start, end);
      } catch {
        if (!dead) setErr("monaco failed; use ?plain=1");
      }
    })();
    return () => {
      dead = true;
      editor?.dispose();
    };
  }, [text, path, start, end, plain, theme]);

  const stale = wantHash !== "" && hash !== "" && wantHash !== hash;

  return (
    <div>
      <h2>Code viewer</h2>
      <p className="page-sub">
        Read-only snapshot at the pinned commit — never the live working tree.
      </p>
      <p data-testid="sha-banner" className="sha-banner">
        {path}:{start}-{end} @ {sha.slice(0, 12)}
        {stale && <span className="chip chip-stale"> stale-citation</span>}
      </p>
      {err && <p className="error">{err}</p>}
      {text !== null &&
        (plain ? (
          <pre data-testid="plain-view">
            {text.split("\n").map((ln, i) => (
              <div key={i} className={i + 1 >= start && i + 1 <= end ? "hl-range" : ""}>
                <span className="ln">{i + 1}</span> {ln}
              </div>
            ))}
          </pre>
        ) : (
          <div ref={hostRef} data-testid="monaco-host" className="monaco-host" />
        ))}
    </div>
  );
}
