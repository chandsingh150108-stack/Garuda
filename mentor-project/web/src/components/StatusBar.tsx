interface Props {
  repoId: string;
  sha: string;
  provider: string;
  staleCount: number;
}

/** Persistent status bar: repo@SHA, provider, freshness. */
export default function StatusBar({ repoId, sha, provider, staleCount }: Props) {
  const pill = provider.startsWith("CLOUD")
    ? "provider-cloud"
    : provider.includes("cached")
      ? "provider-cached"
      : "provider-local";
  return (
    <footer className="statusbar" data-testid="statusbar">
      <span>
        {repoId}@{sha.slice(0, 12)}
      </span>
      <span className={`provider-pill ${pill}`}>{provider}</span>
      <span>
        <span
          className={`status-dot ${staleCount > 0 ? "stale" : "fresh"}`}
          aria-hidden="true"
        />
        {staleCount > 0 ? `${staleCount} stale` : "current"}
      </span>
    </footer>
  );
}
