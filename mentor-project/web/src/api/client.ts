export interface EvidenceRef {
  id: string;
  path: string;
  lines: string;
  hash?: string;
}

export interface Segment {
  text: string;
  kind: string;
  evidence_ids: string[];
  provenance?: string | null;
}

export interface AskResponse {
  status: "answer" | "abstain";
  segments: Segment[];
  missing: string[];
  evidence: EvidenceRef[];
  closest: EvidenceRef[];
  repairs: number;
  model: string;
  provider: string;
  prompt_version: string;
  cached: boolean;
  fallback: boolean;
  cloud_status: string;
}

export interface CodeResponse {
  path: string;
  sha: string;
  start: number;
  end: number;
  text: string;
  truncated: boolean;
  content_hash: string;
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  registerRepo: (path: string, sha: string, id = "fst") =>
    req("/api/repos", {
      method: "POST",
      body: JSON.stringify({ path, sha, id }),
    }),
  status: (id: string) => req(`/api/repos/${id}/status`),
  ask: (id: string, question: string, k = 10, why = false) =>
    req<AskResponse>(`/api/repos/${id}/ask`, {
      method: "POST",
      body: JSON.stringify({ question, k, why }),
    }),
  code: (id: string, path: string, start: number, end: number, full = false) =>
    req<CodeResponse>(
      `/api/repos/${id}/code?path=${encodeURIComponent(path)}&start=${start}&end=${end}${full ? "&full=1" : ""}`
    ),
  architecture: (id: string) => req(`/api/repos/${id}/architecture`),
  tours: (id: string) => req("/api/repos/" + id + "/tours"),
  tour: (id: string, name: string) => req(`/api/repos/${id}/tours/${name}`),
  tasks: (id: string, limit = 10) =>
    req(`/api/repos/${id}/tasks?limit=${limit}`),
};

export function providerLabel(a: Pick<AskResponse, "provider" | "fallback">): string {
  if (a.fallback) return "LOCAL (fallback)";
  if (a.provider === "groq" || a.provider === "gemini")
    return "CLOUD (public demo repo)";
  return "LOCAL";
}

export function isStaleCitation(
  citationHash: string | undefined,
  contentHash: string
): boolean {
  if (!citationHash) return false; // history refs carry no hash: not checked
  return citationHash !== contentHash;
}
