"""Project-wide configuration defaults (Phase 2).

Zero-cost rule: every default here must be free/open. No paid dependency.
Cloud is default-off; see A10.
"""
import os

ALLOW_FREE_CLOUD = False
INDEX_SCHEMA_VERSION = 2
# Task LLM polish (tasks refresh Phase 3, default OFF): precompute may spend
# local inference polishing task blurbs; serving overlays them only on
# id + evidence-hash match, else deterministic text. Never required.
ALLOW_TASK_POLISH = False

# Phase 19 serving modes (D19.1): LOCAL (default) and LOCAL-OFFLINE (no
# network required; all optional lookups disabled) never need the network;
# CLOUD-PUBLIC-DEMO additionally requires ALLOW_FREE_CLOUD=true and is only
# ever valid for allowlisted public repositories. Never required.
MODES = ("LOCAL", "LOCAL-OFFLINE", "CLOUD-PUBLIC-DEMO")


def active_mode() -> str:
    """Serving mode from MENTOR_MODE (fail-safe: unknown values -> LOCAL)."""
    mode = os.environ.get("MENTOR_MODE", "LOCAL").upper().replace("_", "-")
    return mode if mode in MODES else "LOCAL"


def cloud_enabled() -> bool:
    """Whether any cloud call may happen. Offline mode vetoes unconditionally."""
    if active_mode() == "LOCAL-OFFLINE":
        return False
    return bool(ALLOW_FREE_CLOUD)


def mode_banner() -> str:
    mode = active_mode()
    if mode == "LOCAL-OFFLINE":
        return "mode=LOCAL-OFFLINE (loopback only; cloud + gh lookup disabled)"
    if mode == "CLOUD-PUBLIC-DEMO":
        state = "armed" if ALLOW_FREE_CLOUD else "requested but ALLOW_FREE_CLOUD=false"
        return f"mode=CLOUD-PUBLIC-DEMO ({state}; public repos only)"
    return "mode=LOCAL (loopback only; cloud disabled by default)"

# Phase 11 free-cloud (D11, default OFF). Model names are NEVER hardcoded:
# they are chosen from the provider's live model list at demo time
# (`list_models`) and set via these values. Empty = unconfigured = blocked.
CLOUD_GROQ_MODEL = ""
CLOUD_GEMINI_MODEL = ""
CLOUD_MAX_TOKENS = 6000  # redacted-evidence cap per cloud call (chars//4)
CLOUD_BUDGET_DB = "data/budget.sqlite"
# Recorded free-tier limits, dated (RESEARCH_LOG.md Phase 11, 2026-10-16).
# Empty dict = fail-closed: provider never called until limits are recorded.
GROQ_LIMITS = {"rpd": 1000, "tpd": 200000}
GEMINI_LIMITS = {}

# Phase 10 service defaults (D10.1-D10.3, LOCKED).
WEB_ORIGIN = "http://127.0.0.1:5173"  # single local web origin for CORS
MAX_BODY_BYTES = 1_000_000  # request size limit (413 beyond)
AUDIT_STORE_TEXT = False  # audit keeps hashes only unless explicitly enabled

# Phase 14 history (D14.3): `gh` PR lookup is OFF by default (no network).
GH_PR_LOOKUP = False
DEFAULT_REPO_ID = "fst"

# Ingest limits (spec Phase 2, LOCKED via D2 decisions)
MAX_FILE_BYTES = 1_000_000
LOCKFILE_MAX_BYTES = 200_000

# Parser limits (spec Phase 3, LOCKED via D3.2)
PARSE_TIMEOUT_S = 10.0
PARSE_MAX_BYTES = 1_000_000

# Dense retrieval default (spec Phase 7, G1 outcome 2026-10-12: REJECTED).
# "none" = lexical-only B3 ships. Any other value must name a MODEL_SPECS
# entry in mentor/retrieve/dense.py and requires a full index rebuild (D7.3).
DENSE_MODEL = "none"

# Local LLM defaults (spec Phase 8; G2 chose the values 2026-10-15, DECISIONS.md).
# Provider "ollama" is the documented default; "llamacpp" is the A17 fallback
# in live use until the Ollama installer is obtainable (D8.0). G2 was measured
# on llamacpp-vulkan; Ollama/CUDA re-measurement is future work.
LLM_PROVIDER = "llamacpp"
LLM_MODEL = "qwen3-4b-instruct-q4_k_m"
LLM_CTX = 8192
LLM_ENDPOINT = "http://127.0.0.1:8080"
# Qwen3 thinking control (G2 outcome): the 4B model must run in non-thinking
# mode ("/no_think" in the system prompt). Without it, thinking tokens consume
# the budget and content arrives empty (measured 5.1 s + empty vs 0.3 s + JSON).
# Phase 9+ prompts must include this suffix while LLM_MODEL is qwen3-4b.
LLM_SYSTEM_SUFFIX = "/no_think"
# Qualified fallback (passes all G2 gates; code-specialized): 7B needs no suffix.
LLM_FALLBACK_MODEL = "qwen2.5-coder-7b-instruct-q4_k_m"
LLM_FALLBACK_SYSTEM_SUFFIX = ""
# Phase 15 task scoring (D15.2/D15.3): engineering judgment, calibrated in
# evals/tasks_calibration.md. difficulty = W1*log(lines) + W2*files + W3*fan_in.
TASK_W1 = 1.0
TASK_W2 = 2.0
TASK_W3 = 0.5
TASK_HIGH_RISK = 8  # risk >= this sinks below the top five (still listed)
