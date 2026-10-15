import { useState } from "react";
import { api } from "../api/client";

export default function Repos({ onRepo }: { onRepo: (id: string, sha: string) => void }) {
  const [path, setPath] = useState("data/repos/fst");
  const [sha, setSha] = useState("7257e606cb94eada1dca40173e2b7f99dd549bc6");
  const [id, setId] = useState("fst");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function register() {
    setBusy(true);
    setMsg("");
    try {
      await api.registerRepo(path, sha, id);
      onRepo(id, sha);
      setMsg(`registered ${id}`);
    } catch (e) {
      setMsg(`failed: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>Repositories</h2>
      <label>
        Path <input value={path} onChange={(e) => setPath(e.target.value)} size={30} />
      </label>
      <label>
        SHA <input value={sha} onChange={(e) => setSha(e.target.value)} size={44} />
      </label>
      <label>
        ID <input value={id} onChange={(e) => setId(e.target.value)} size={8} />
      </label>
      <button onClick={register} disabled={busy}>
        Register
      </button>
      <p data-testid="repos-msg">{msg}</p>
    </div>
  );
}
