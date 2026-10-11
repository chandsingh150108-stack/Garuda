"""Phase 0 environment probe. Prints JSON to stdout. Never fails on missing tools (null)."""
import json
import platform
import shutil
import subprocess
import sys


def run(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if out.returncode == 0:
            return out.stdout.strip()
        return None
    except Exception:
        return None


def get_nvidia():
    base = {"name": None, "memory.total": None, "memory.free": None,
            "power.limit": None, "power.max_limit": None, "driver_version": None}
    if shutil.which("nvidia-smi") is None:
        return base
    csv = run(["nvidia-smi",
               "--query-gpu=name,memory.total,memory.free,power.limit,power.max_limit,driver_version",
               "--format=csv,noheader,nounits"])
    if not csv:
        return base
    parts = [p.strip() for p in csv.split(",")]
    keys = ["name", "memory.total", "memory.free", "power.limit", "power.max_limit", "driver_version"]
    for k, v in zip(keys, parts):
        if v in ("[N/A]", "[NOT SUPPORTED]", "", "N/A"):
            base[k] = None
        else:
            base[k] = v
    return base


def main():
    nvidia = get_nvidia()
    ollama_v = run(["ollama", "--version"])
    # free disk space in GB for PROJECT_ROOT drive
    try:
        import shutil as _sh
        total, used, free = _sh.disk_usage(".")
        free_gb = round(free / (1024 ** 3), 2)
    except Exception:
        free_gb = None
    result = {
        "os_name": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "python_version": platform.python_version(),
        "node_version": run(["node", "--version"]),
        "git_version": run(["git", "--version"]),
        "nvidia_name": nvidia["name"],
        "nvidia_memory_total": nvidia["memory.total"],
        "nvidia_memory_free": nvidia["memory.free"],
        "nvidia_power_limit": nvidia["power.limit"],
        "nvidia_power_max_limit": nvidia["power.max_limit"],
        "nvidia_driver_version": nvidia["driver_version"],
        "ollama_version": ollama_v,
        "free_disk_gb": free_gb,
    }
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
