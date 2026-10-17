import { useState } from "react";
import { api, providerLabel } from "../api/client";
import type { AskResponse } from "../api/client";
import type { AskState } from "../App";
import AnswerView from "../components/AnswerView";

export default function Ask({
  repoId,
  onAnswer,
  askState,
  onAskState,
}: {
  repoId: string;
  onAnswer: (a: AskResponse) => void;
  askState: AskState;
  onAskState: (s: AskState) => void;
}) {
  const { q, why, answer } = askState;
  const setQ = (next: string) => onAskState({ ...askState, q: next, answer: null });
  const setWhy = (next: boolean) => onAskState({ ...askState, why: next });
  const setAnswer = (next: AskResponse | null) =>
    onAskState({ ...askState, answer: next });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(question?: string) {
    const query = question ?? q;
    if (question !== undefined) setQ(question);
    setBusy(true);
    setErr("");
    try {
      const a = await api.ask(repoId, query, 10, why);
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
      <h2>Ask the codebase</h2>
      <p className="page-sub">
        Every answer cites exact file lines — click a chip to see the proof.
      </p>
      <textarea
        value={q}
        onChange={(e) => setQ(e.target.value)}
        rows={3}
        cols={70}
        data-testid="ask-box"
        className="ask-box"
        placeholder="e.g. How does user registration (`register_user`) work?"
      />
      <div className="suggestions" aria-label="Example questions">
        {[
          "How does user registration (`register_user`) work?",
          "How does login issue access tokens?",
          "What database models exist?",
          "Where is the signup page built?",
        ].map((s) => (
          <button
            key={s}
            className="ghost suggestion"
            disabled={busy}
            onClick={() => run(s)}
          >
            {s}
          </button>
        ))}
      </div>
      <div className="ask-row">
        <label>
          <input
            type="checkbox"
            checked={why}
            onChange={(e) => setWhy(e.target.checked)}
          />
          why (history)
        </label>
        <button onClick={() => run()} disabled={busy} data-testid="ask-run">
          {busy ? "Thinking…" : "Ask"}
        </button>
      </div>
      {err && <p className="error">{err}</p>}
      {busy && (
        <div className="skeleton" aria-label="Loading answer">
          <div className="bar" style={{ width: "90%" }} />
          <div className="bar" style={{ width: "70%" }} />
          <div className="bar" style={{ width: "80%" }} />
        </div>
      )}
      {answer && !busy && (
        <AnswerView repoId={repoId} answer={answer} codeHashes={{}} />
      )}
      {answer && !busy && <p>{providerLabel(answer)}</p>}
    </div>
  );
}
