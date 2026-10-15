import { useState } from "react";
import { api, providerLabel } from "../api/client";
import type { AskResponse } from "../api/client";
import AnswerView from "../components/AnswerView";

export default function Ask({
  repoId,
  onAnswer,
}: {
  repoId: string;
  onAnswer: (a: AskResponse) => void;
}) {
  const [q, setQ] = useState("How does user registration work?");
  const [why, setWhy] = useState(false);
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setErr("");
    try {
      const a = await api.ask(repoId, q, 10, why);
      setAnswer(a);
      onAnswer(a);
    } catch (e) {
      setErr(`${e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>Ask</h2>
      <textarea
        value={q}
        onChange={(e) => setQ(e.target.value)}
        rows={3}
        cols={70}
        data-testid="ask-box"
      />
      <label>
        <input
          type="checkbox"
          checked={why}
          onChange={(e) => setWhy(e.target.checked)}
        />
        why (history)
      </label>
      <button onClick={run} disabled={busy} data-testid="ask-run">
        Ask
      </button>
      {err && <p className="error">{err}</p>}
      {answer && (
        <AnswerView repoId={repoId} answer={answer} codeHashes={{}} />
      )}
      {answer && <p>{providerLabel(answer)}</p>}
    </div>
  );
}
