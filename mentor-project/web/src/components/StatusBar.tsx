interface Props {
  repoId: string;
  sha: string;
  provider: string;
  staleCount: number;
}

/** Persistent status bar: repo@SHA, provider, freshness. */
export default function StatusBar({ repoId, sha, provider, staleCount }: Props) {
  return (
    <footer className="statusbar" data-testid="statusbar">
      <span>
        {repoId}@{sha.slice(0, 12)}
      </span>
      <span>{provider}</span>
      <span>{staleCount > 0 ? `${staleCount} stale` : "current"}</span>
    </footer>
  );
}
