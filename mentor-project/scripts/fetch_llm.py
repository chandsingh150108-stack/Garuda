"""Fetch Phase 8 serving stack (spec D8.0): llama.cpp Vulkan zip (resume-capable,
slow CDN) + two GGUFs from HF (fast CDN). Models land in data/models/
(git-ignored runtime). Prints sizes + SHA-256 for the decision record."""
import hashlib
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(r"C:\Users\Lenovo\Desktop\Apex\Garuda\mentor-project\data\models")
OUT.mkdir(parents=True, exist_ok=True)

LLAMA_URL = ("https://github.com/ggml-org/llama.cpp/releases/download/b11429/"
             "llama-b11429-bin-win-vulkan-x64.zip")


def resume_http(url: str, dst: Path, deadline_s: float) -> int:
    have = dst.stat().st_size if dst.exists() else 0
    t0 = time.time()
    while time.time() - t0 < deadline_s:
        req = urllib.request.Request(url, headers={"User-Agent": "mentor-phase8",
                                                    "Range": f"bytes={have}-"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp, \
                    open(dst, "ab") as fh:
                if resp.status == 200 and have > 0:
                    print("server ignored Range; restarting", flush=True)
                    dst.unlink(missing_ok=True)
                    have = 0
                    continue
                while time.time() - t0 < deadline_s:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        return have
                    fh.write(chunk)
                    have += len(chunk)
                return have
        except Exception as e:
            print(f"stall ({type(e).__name__}), resume in 5s", flush=True)
            time.sleep(5)
    return have


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "llama"):
        dst = OUT / "llama-b11429-bin-win-vulkan-x64.zip"
        got = resume_http(LLAMA_URL, dst, 25 * 60)
        print(f"llama zip: {got/1e6:.1f} MB sha256={sha256(dst)[:16]}...", flush=True)
    if which in ("all", "gguf"):
        from huggingface_hub import hf_hub_download
        for repo, fname in [
                ("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
                 "qwen2.5-coder-7b-instruct-q4_k_m.gguf"),
                ("Qwen/Qwen3-4B-GGUF", "Qwen3-4B-Q4_K_M.gguf")]:
            t0 = time.time()
            path = hf_hub_download(repo, fname, local_dir=OUT, local_dir_use_symlinks=False,
                                   resume_download=True)
            size = Path(path).stat().st_size
            print(f"{fname}: {size/1e9:.2f} GB in {(time.time()-t0)/60:.1f} min", flush=True)
    print("fetch done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
