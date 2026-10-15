import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

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
}

/** Starter tasks with read-first tour links. */
export default function Tasks({ repoId }: { repoId: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .tasks(repoId, 10)
      .then((t) => setTasks((t as { tasks: Task[] }).tasks))
      .catch((e) => setErr(`${e}`));
  }, [repoId]);

  return (
    <div>
      <h2>Starter tasks</h2>
      {err && <p className="error">{err}</p>}
      <ol>
        {tasks.map((t) => (
          <li key={t.id}>
            <strong>{t.title}</strong> (d={t.difficulty.toFixed(2)} r={t.risk}
            {t.high_risk ? " HIGH RISK" : ""})
            <p>{t.description}</p>
            <Link
              to={`/code?repo=${repoId}&path=${encodeURIComponent(t.file)}&start=${t.start}&end=${t.end}`}
            >
              {t.file}:{t.start}-{t.end}
            </Link>
            {t.tours.map((name) => (
              <span key={name}>
                {" "}
                <Link to={`/tours?repo=${repoId}&tour=${name}`}>
                  read first: {name}
                </Link>
              </span>
            ))}
          </li>
        ))}
      </ol>
    </div>
  );
}
