import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

interface TaskOpenFirst {
  path: string;
  lines: string;
}

interface Task {
  id: string;
  kind: string;
  title: string;
  description: string;
  file: string;
  start: number;
  end: number;
  difficulty: number;
  risk: number;
  high_risk: boolean;
  prerequisites: string[];
  tours: string[];
  acceptance: string[];
  verify: string;
  example_test: string | null;
  open_first: TaskOpenFirst | null;
  polished: boolean;
}

/** Starter tasks with read-first tour links. */
export default function Tasks({ repoId }: { repoId: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [err, setErr] = useState("");
  const [kindFilter, setKindFilter] = useState("all");
  const [open, setOpen] = useState<Record<string, boolean>>({});

  useEffect(() => {
    api
      .tasks(repoId, 10)
      .then((t) => setTasks((t as { tasks: Task[] }).tasks))
      .catch((e) => setErr(`${e}`));
  }, [repoId]);

  const kinds = ["all", ...Array.from(new Set(tasks.map((t) => t.kind)))];
  const shown =
    kindFilter === "all" ? tasks : tasks.filter((t) => t.kind === kindFilter);

  return (
    <div>
      <h2>Starter tasks</h2>
      <p className="page-sub">
        Small, evidence-backed first contributions — sorted easy → hard.
      </p>
      {err && <p className="error">{err}</p>}
      {kinds.length > 2 && (
        <div className="suggestions" aria-label="Filter by task kind">
          {kinds.map((k) => (
            <button
              key={k}
              className="ghost suggestion"
              disabled={kindFilter === k}
              onClick={() => setKindFilter(k)}
            >
              {k}
            </button>
          ))}
        </div>
      )}
      <ol className="task-list">
        {shown.map((t, i) => (
          <li key={t.id} className="card hoverable task-card">
            <h3>
              <span className="task-index" aria-hidden="true">
                {i + 1}
              </span>{" "}
              {t.title}
              {t.polished && <span className="kind-tag"> polished</span>}
            </h3>
            <div className="task-meta">
              <span className="difficulty" title={`difficulty ${t.difficulty.toFixed(2)}`}>
                <span className="meter" aria-hidden="true">
                  {[1, 2, 3, 4, 5].map((p) => (
                    <span
                      key={p}
                      className={`pip${p <= Math.max(1, Math.min(5, Math.round(t.difficulty))) ? " on" : ""}`}
                    />
                  ))}
                </span>
                d={t.difficulty.toFixed(2)}
              </span>
              <span className="kind-pill">{t.kind}</span>
              {t.high_risk && <span className="risk-flag">high risk</span>}
            </div>
            <p>{t.description}</p>
            <p>
              <Link
                className="code-link"
                to={`/code?repo=${repoId}&path=${encodeURIComponent(t.file)}&start=${t.start}&end=${t.end}`}
              >
                {t.file}:{t.start}-{t.end}
              </Link>
            </p>
            {t.tours.length > 0 && (
              <div className="task-meta">
                {t.tours.map((name) => (
                  <Link
                    key={name}
                    className="tour-link"
                    to={`/tours?repo=${repoId}&tour=${name}`}
                  >
                    read first: {name}
                  </Link>
                ))}
              </div>
            )}
            {t.prerequisites.length > 0 && (
              <p className="page-sub">Needs: {t.prerequisites.join(" · ")}</p>
            )}
            <div>
              <button
                className="ghost"
                onClick={() => setOpen({ ...open, [t.id]: !open[t.id] })}
                aria-expanded={!!open[t.id]}
              >
                {open[t.id] ? "Hide details" : "How to do it"}
              </button>
            </div>
            {open[t.id] && (
              <div className="task-detail">
                {t.acceptance.length > 0 && (
                  <>
                    <p>
                      <strong>Done when:</strong>
                    </p>
                    <ul>
                      {t.acceptance.map((a, j) => (
                        <li key={j}>{a}</li>
                      ))}
                    </ul>
                  </>
                )}
                {t.verify && (
                  <p>
                    <strong>Verify: </strong>
                    <code>{t.verify}</code>
                  </p>
                )}
                {t.example_test && (
                  <p>
                    <strong>Copy from: </strong>
                    <Link
                      className="code-link"
                      to={`/code?repo=${repoId}&path=${encodeURIComponent(t.example_test)}&start=1&end=30`}
                    >
                      {t.example_test}
                    </Link>
                  </p>
                )}
                {t.open_first && (
                  <p>
                    <strong>Open first: </strong>
                    <Link
                      className="code-link"
                      to={`/code?repo=${repoId}&path=${encodeURIComponent(t.open_first.path)}&start=${t.open_first.lines.split("-")[0]}&end=${t.open_first.lines.split("-")[1] ?? t.open_first.lines.split("-")[0]}`}
                    >
                      {t.open_first.path}:{t.open_first.lines}
                    </Link>
                  </p>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
