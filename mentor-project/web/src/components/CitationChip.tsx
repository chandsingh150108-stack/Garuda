import { Link } from "react-router-dom";
import type { EvidenceRef } from "../api/client";

interface Props {
  repoId: string;
  citation: EvidenceRef;
  stale: boolean;
}

/** Citation chip: opens the exact path/range/SHA. Stale badge on mismatch. */
export default function CitationChip({ repoId, citation, stale }: Props) {
  const [start, end] = citation.lines.split("-").map(Number);
  return (
    <Link
      data-testid={`chip-${citation.id}`}
      className={stale ? "chip chip-stale" : "chip"}
      to={`/code?repo=${repoId}&path=${encodeURIComponent(citation.path)}&start=${start}&end=${end}&hash=${citation.hash ?? ""}`}
      title={`${citation.path}:${citation.lines}${stale ? " (stale: lines changed)" : ""}`}
    >
      [{citation.id}]{stale ? " stale" : ""}
    </Link>
  );
}
