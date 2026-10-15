"""Project-wide configuration defaults (Phase 2).

Zero-cost rule: every default here must be free/open. No paid dependency.
Cloud is default-off; see A10.
"""

ALLOW_FREE_CLOUD = False
INDEX_SCHEMA_VERSION = 2

# Phase 10 service defaults (D10.1-D10.3, LOCKED).
WEB_ORIGIN = "http://127.0.0.1:5173"  # single local web origin for CORS
MAX_BODY_BYTES = 1_000_000  # request size limit (413 beyond)
AUDIT_STORE_TEXT = False  # audit keeps hashes only unless explicitly enabled
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
