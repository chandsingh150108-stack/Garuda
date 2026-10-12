"""Project-wide configuration defaults (Phase 2).

Zero-cost rule: every default here must be free/open. No paid dependency.
Cloud is default-off; see A10.
"""

ALLOW_FREE_CLOUD = False
INDEX_SCHEMA_VERSION = 1
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
