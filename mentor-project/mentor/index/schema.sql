-- Codebase Mentor index schema, version 1 (spec Phase 4).
-- One SQLite file per repository. FTS5 provides lexical BM25.
-- Rule: schema changes bump user_version and rebuild; never migrate silently.

CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE repos (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE snapshots (
  sha TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repos(id),
  file_count INTEGER NOT NULL
);

CREATE TABLE files (
  snapshot_sha TEXT NOT NULL,
  path TEXT NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT,
  language TEXT NOT NULL,
  skipped TEXT,
  PRIMARY KEY (snapshot_sha, path)
);

CREATE TABLE symbols (
  snapshot_sha TEXT NOT NULL,
  path TEXT NOT NULL,
  qualname TEXT NOT NULL,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  parent TEXT,
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  signature_line INTEGER NOT NULL,
  docstring TEXT,
  params TEXT,
  bases_json TEXT,
  decorators_json TEXT
);

CREATE TABLE imports (
  snapshot_sha TEXT NOT NULL,
  path TEXT NOT NULL,
  module TEXT NOT NULL,
  names_json TEXT NOT NULL,
  line INTEGER NOT NULL,
  level INTEGER NOT NULL,
  resolved TEXT
);

CREATE TABLE edges (
  snapshot_sha TEXT NOT NULL,
  kind TEXT NOT NULL,
  label TEXT NOT NULL,
  from_ref TEXT NOT NULL,
  to_ref TEXT,
  detail_json TEXT NOT NULL
);

CREATE TABLE routes (
  snapshot_sha TEXT NOT NULL,
  file TEXT NOT NULL,
  method TEXT NOT NULL,
  path TEXT,
  handler TEXT NOT NULL,
  handler_start INTEGER NOT NULL,
  handler_end INTEGER NOT NULL,
  decorator_line INTEGER NOT NULL,
  router_var TEXT,
  router_prefix TEXT,
  prefix_unknown INTEGER NOT NULL
);

CREATE TABLE models (
  snapshot_sha TEXT NOT NULL,
  file TEXT NOT NULL,
  class TEXT NOT NULL,
  qualname TEXT NOT NULL,
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  table_name TEXT NOT NULL,
  table_inferred INTEGER NOT NULL,
  bases_json TEXT NOT NULL,
  fields_json TEXT NOT NULL
);

CREATE TABLE config_facts (
  snapshot_sha TEXT NOT NULL,
  file TEXT NOT NULL,
  kind TEXT NOT NULL,
  data_json TEXT NOT NULL,
  PRIMARY KEY (snapshot_sha, file)
);

CREATE TABLE chunks (
  chunk_id TEXT PRIMARY KEY,
  snapshot_sha TEXT NOT NULL,
  path TEXT NOT NULL,
  start_line INTEGER NOT NULL,
  end_line INTEGER NOT NULL,
  method TEXT NOT NULL,
  header TEXT NOT NULL,
  text TEXT NOT NULL,
  embed_text TEXT NOT NULL,
  identifiers TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  approx_tokens INTEGER NOT NULL,
  is_exception INTEGER NOT NULL
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
  chunk_id UNINDEXED,
  header,
  identifiers,
  text,
  tokenize='unicode61'
);

CREATE TABLE artifacts (
  kind TEXT NOT NULL,
  key TEXT NOT NULL,
  content_json TEXT NOT NULL,
  dep_hash TEXT NOT NULL,
  created_sha TEXT NOT NULL,
  PRIMARY KEY (kind, key)
);

CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY,
  event TEXT NOT NULL,
  detail_json TEXT NOT NULL
);
