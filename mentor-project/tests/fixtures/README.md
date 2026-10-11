# tests/fixtures

Fixture notes (spec Phase 2). Large / platform-sensitive fixtures are
generated at test runtime in `tmp_path` (never committed):

- `symlink_escape`: created at runtime — a symlink inside the repo pointing
  to a file outside the repo. Must be skipped with reason `symlink` and its
  target never read.
- `oversized`: created at runtime — a file of 1 MiB + 1 byte. Skipped `size`.
- `canary_secret`: `canary_secret_example.txt` (committed, FAKE AWS-docs
  example key `AKIAIOSFODNN7EXAMPLE`, not real) + runtime copies. Files with
  matches are excluded with reason `secret`; only hashes stored.
- `path_traversal`: pure unit test of `safe_join` with `../` (no file).
- `submodule`: created at runtime — a dir with a `.git` file (gitlink style).
  Skipped with reason `submodule`, never descended into.
