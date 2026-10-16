# Backup demo recording (Phase 21, D21.2)

- Location (git-ignored runtime, NOT committed):
  `data/demo_recording/demo-video-demo-walkthrough-recording-chromium/video.webm`
- SHA-256: `fbf628d8ad1a20680b004407fdf94423859e82d70c53dcbf1e4fe0d2342388ae`
- Size: ~37 KB, 1280×800, Chromium via Playwright 1.49.1 video capture.
- Covers: ask signup → answer → chip click → code@SHA → arch diagram →
  tours list → tasks list (all cache-served, no model needed).
- Reproduced by: start `python -m mentor.cli serve --index
  data/indexes/fst.sqlite`, then
  `cd web && npx playwright test -c playwright.demo.config.ts`.
- Plays when: the browser fails at showtime (D21.2 fallback order:
  live local → labelled cache → honest abstain → this recording).
