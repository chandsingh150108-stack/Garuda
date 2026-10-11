"""Phase 0 gate: probe_env.py outputs valid JSON with all required keys (null allowed)."""
import json
import subprocess
import sys
from pathlib import Path


REQUIRED_KEYS = [
    "os_name", "os_version", "os_release", "python_version",
    "node_version", "git_version",
    "nvidia_name", "nvidia_memory_total", "nvidia_memory_free",
    "nvidia_power_limit", "nvidia_power_max_limit", "nvidia_driver_version",
    "ollama_version", "free_disk_gb",
]


def test_probe_valid_json():
    probe = Path(__file__).resolve().parent.parent / "scripts" / "probe_env.py"
    out = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, f"probe failed: {out.stderr}"
    data = json.loads(out.stdout)
    for k in REQUIRED_KEYS:
        assert k in data, f"missing key: {k}"
