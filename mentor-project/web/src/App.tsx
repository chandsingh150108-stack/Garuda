import { useState } from "react";
import { Link, Route, Routes, useSearchParams } from "react-router-dom";
import Repos from "./pages/Repos";
import Ask from "./pages/Ask";
import Code from "./pages/Code";
import Architecture from "./pages/Architecture";
import Tours from "./pages/Tours";
import Tasks from "./pages/Tasks";
import StatusBar from "./components/StatusBar";
import { providerLabel } from "./api/client";
import type { AskResponse } from "./api/client";

export default function App() {
  const [repoId, setRepoId] = useState("fst");
  const [sha, setSha] = useState("7257e606cb94eada1dca40173e2b7f99dd549bc6");
  const [provider, setProvider] = useState("LOCAL");
  const [params] = useSearchParams();
  const routedRepo = params.get("repo") ?? repoId;

  function onAnswer(a: AskResponse) {
    setProvider(providerLabel(a));
  }

  return (
    <div className="app">
      <header>
        <h1>Codebase Mentor</h1>
        <nav>
          <Link to="/">Repos</Link> | <Link to="/ask">Ask</Link> |{" "}
          <Link to={`/code?repo=${routedRepo}`}>Code</Link> |{" "}
          <Link to="/arch">Architecture</Link> | <Link to="/tours">Tours</Link>{" "}
          | <Link to="/tasks">Tasks</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route
            path="/"
            element={
              <Repos
                onRepo={(id, s) => {
                  setRepoId(id);
                  setSha(s);
                }}
              />
            }
          />
          <Route path="/ask" element={<Ask repoId={routedRepo} onAnswer={onAnswer} />} />
          <Route path="/code" element={<Code />} />
          <Route path="/arch" element={<Architecture repoId={routedRepo} />} />
          <Route path="/tours" element={<Tours repoId={routedRepo} />} />
          <Route path="/tasks" element={<Tasks repoId={routedRepo} />} />
        </Routes>
      </main>
      <StatusBar repoId={routedRepo} sha={sha} provider={provider} staleCount={0} />
    </div>
  );
}
