import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import Repos from "./pages/Repos";
import Ask from "./pages/Ask";
import Code from "./pages/Code";
import Architecture from "./pages/Architecture";
import Tours from "./pages/Tours";
import Tasks from "./pages/Tasks";
import StatusBar from "./components/StatusBar";
import { applyTheme, getTheme } from "./theme";
import type { Theme } from "./theme";
import { providerLabel } from "./api/client";
import type { AskResponse } from "./api/client";

export interface AskState {
  q: string;
  why: boolean;
  answer: AskResponse | null;
}

const DEFAULT_ASK: AskState = {
  q: "How does user registration work?",
  why: false,
  answer: null,
};

export default function App() {
  const [repoId, setRepoId] = useState("fst");
  const [sha, setSha] = useState("7257e606cb94eada1dca40173e2b7f99dd549bc6");
  const [provider, setProvider] = useState("LOCAL");
  const [theme, setTheme] = useState<Theme>(() => getTheme());
  // Ask state lives here (not in the Ask page) so navigating to a citation
  // and back restores the exact question and answer instead of resetting.
  const [askState, setAskState] = useState<AskState>(DEFAULT_ASK);
  const [params] = useSearchParams();
  const location = useLocation();
  const routedRepo = params.get("repo") ?? repoId;

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  function onAnswer(a: AskResponse) {
    setProvider(providerLabel(a));
  }

  return (
    <div className="app">
      <header>
        <h1 className="brand">
          <span className="brand-mark" aria-hidden="true">
            {"</>"}
          </span>
          <span className="brand-text">Codebase Mentor</span>
        </h1>
        <nav>
          <NavLink to="/" end>
            Repos
          </NavLink>
          <NavLink to="/ask">Ask</NavLink>
          <NavLink to={`/code?repo=${routedRepo}`}>Code</NavLink>
          <NavLink to="/arch">Architecture</NavLink>
          <NavLink to="/tours">Tours</NavLink>
          <NavLink to="/tasks">Tasks</NavLink>
        </nav>
        <button
          className="ghost theme-toggle"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          aria-label="Toggle color theme"
        >
          {theme === "dark" ? (
            <svg
              className="icon"
              aria-hidden="true"
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
            </svg>
          ) : (
            <svg
              className="icon"
              aria-hidden="true"
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
            </svg>
          )}
        </button>
      </header>
      <main>
        <div className="page-enter" key={location.pathname}>
          <Routes location={location}>
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
            <Route
              path="/ask"
              element={
                <Ask
                  repoId={routedRepo}
                  onAnswer={onAnswer}
                  askState={askState}
                  onAskState={setAskState}
                />
              }
            />
            <Route path="/code" element={<Code />} />
            <Route path="/arch" element={<Architecture repoId={routedRepo} />} />
            <Route path="/tasks" element={<Tasks repoId={routedRepo} />} />
            <Route path="/tours" element={<Tours repoId={routedRepo} />} />
          </Routes>
        </div>
      </main>
      <StatusBar repoId={routedRepo} sha={sha} provider={provider} staleCount={0} />
    </div>
  );
}
