# RESEARCH_LOG

Verification ledger copied from CODEBASE_MENTOR_EXECUTABLE.md v1.0 (Oct 2026). Status as of this pass.

| # | Claim | Status | Evidence | Consequence |
|---|---|---|---|---|
| V1 | RTX 5060 Laptop 8GB GDDR7 128-bit | VERIFIED | Notebookcheck Apr 2025, NVIDIA announcement | 8GB hard ceiling |
| V2 | 3,328 CUDA, 45-100W TGP, 384GB/s; aggregators conflict (3,840 cores/448GB/s/115W = desktop) | VERIFIED launch specs; CONFLICT in aggregators | Notebookcheck specs table | Phase 0 must read real device with nvidia-smi; machine TGP/VRAM override spec sheet |
| V3 | Groq free tier gpt-oss-120b: 30RPM/1000RPD/8K TPM/200K TPD, per-model per-org | VERIFIED via secondary repro Sep 2026 | Aggregators quoting console.groq.com/docs/rate-limits | Live check required before demo |
| V4 | Groq model qwen3.8-27b 1000RPD | UNVERIFIED, suspicious name, single source | Single aggregator | Do not hardcode; read live model list Phase 11 |
| V5 | Gemini free 15RPM/10K RPD/1M TPD Flash-class | UNVERIFIED likely STALE; per-project console now | Google rate-limits page | Remove numbers; read console Phase 11 |
| V6 | Gemini free prompts may train Google products | VERIFIED | Google pricing page free-tier column | Gemini forbidden for private code |
| V7 | OpenRouter :free 20RPM/50RPD (1K/day after $10) | VERIFIED two sources | 2026 audits | Emergency reserve only |
| V8 | Cerebras free = card-gated trial | CONFLICTING (some claim 1M/day free) | Mixed | Excluded either way |
| V9 | GitHub Models retired 30 Jul 2026 | UNVERIFIED single report | Report only | Excluded either way |
| V10 | CoREB arXiv 2605.04615: rerankers not net-positive; keyword collapse | VERIFIED paper exists/says this | arXiv abstract | Limits: LiveCodeBench CP problems, self-reported; fine-tuned reranker only consistent gainer; directional hint only |
| V11 | CodeGrep arXiv 2608.05886: precision band 0.45-0.68 | VERIFIED exists; WEAKLY SUPPORTED for us | Abstract+tables | 3 retrievers, SWE-Bench Verified, 14B searcher (no laptop fit); band is 3-point observation; Phase 5 measures own precision |
| V12 | cAST EMNLP25 arXiv 2506.15655: +4.3 Recall@5 RepoEval, +2.67 Pass@1 SWE-bench | VERIFIED correct | ACL Anthology, arXiv v2 | Adopt AST chunking |
| V13 | bge-m3 568M/1024d/8K MIT | VERIFIED in report, not re-fetched | FlagEmbedding repo | Fallback candidate |
| V14 | jina-embeddings-v2-base-code 161M/768d/8K Apache-2.0 | PARTIALLY VERIFIED; license check Phase 7 | Report | Candidate pending card check |
| V15 | jina-code-embeddings 0.5B/1.5B exist (Qwen2.5-Coder bases) | VERIFIED exist; converter card says CC-BY-NC-4.0 non-commercial | Jina pages + HF converter card | Report jina-code Apache refers to old v2; newer = non-commercial until source card says otherwise |
| V16 | Qwen2.5-Coder-7B Apache-2.0/128K/28 layers/GQA 4KV | VERIFIED | Model docs + spec sheets | Enables KV arithmetic Phase 8 |
| V17 | Qwen2.5-Coder-14B Q4 9.9GB/12GB coder | CORRECTED: GGUF Q4_K_M ~8.4-9GB | Community GGUF files | Still >8GB; conclusion holds, number was wrong |
| V18 | Ollama format JSON schema since 0.5.0 | VERIFIED, adherence not guaranteed; Qwen3.x issue Apr 2026 | Ollama docs + issues | Server validator + repair mandatory |
| V19 | fastapi/full-stack-fastapi-template MIT ~43.5K stars Jun 2026 (report said 45K) | VERIFIED | GitHub + snapshot | Primary demo candidate; high contamination risk (Phase 2) |
| V20 | Claude Sonnet 5 $2/$10 1M ctx | UNVERIFIED possibly outdated (5.5 lineup) | Report only | Paid path excluded; no change |
| V21 | Qdrant vs pgvector 9ms vs 51ms; 290MB vs 1.1GB | UNVERIFIED third-party blog | Blogs | Decision no longer depends on them (C1) |
| V22 | Sourcegraph dropped embeddings; Claude Code grep-first; WarpGrep numbers | NOT RE-VERIFIED; OBSERVED PRACTICE w/ caution | Company blogs | Directional support only |

Local probe 2026-10-08 (dev machine, NOT target): RTX 4050 Laptop 6GB, driver 581.57, Python 3.14.0, Node v24.19.0, Ollama client 0.34.0 (no daemon). Target RTX 5060 8GB probe pending. [INFERENCE: dev != target, Phase 8 must re-measure]
