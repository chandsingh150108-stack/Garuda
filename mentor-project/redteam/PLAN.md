# Redteam plan (Phase 22, D22.1)

Method: scripted attacks (`attacks/run_all.py`, model-free except F9/F12
which use the loopback model server) + manual support sampling of cached
demo answers. Every family names its expected safe behaviour; deviations
are findings with severity, fix, and retest. Severity scale (D22.1):
Critical (confidentiality/integrity/grounding failure reachable by a normal
user — must be fixed before completion), High, Medium, Low.

| # | Family | Expected safe behaviour | Test |
|---|---|---|---|
| 1 | Hallucinated citations | nonexistent IDs / uncited facts rejected (V2/V3) | invalid suite 100% + crafted bad-ID sweep |
| 2 | Fake line ranges | server clamps to file; never renders outside; traversal 400/404 | range battery on live file |
| 3 | Stale citations | edited lines read stale; clean tree reads current | Phase 17 suite + live clean-tree check |
| 4 | Prompt injection | corpus + counterfactual payloads all rejected; CF retrieval structure-grounded | T2 sweep + CF renamed-identifier search |
| 5 | Exfiltration | bulk phrasing refused pre-retrieval; no secret formats in index | bulk battery + index secret scan |
| 6 | Access control (single-user adapted) | traversal refused; repo A never serves repo B rows | traversal battery + two-index check |
| 7 | Malicious repos | size/symlink/submodule/nesting contained | hostile-tree spot checks |
| 8 | Quota failure (429) | same-contract local fallback, labelled | injected RATE_LIMITED adapter |
| 9 | Model failure mid-request | structured gateway abstain; no partial shown as complete | injected TRANSPORT failure on live index |
| 10 | Indexing failure | corrupt file contained; build completes; counts consistent | hostile build test |
| 11 | Unsupported questions | 6 gold unanswerables + 12 adversarial rephrasings abstain pre-model | retrieval-gate battery |
| 12 | Contamination | B3-recall parity + B6 sample on original vs counterfactual | harness numbers + live B6 sample |
| 13 | Documentation drift | dep edits flag tours stale; unrelated edits don't | Phase 17 suite (referenced) |

Gates: G3 (file-P@10 measured; adopt agent only above benefit level) and G4
(reranker; adopt only on held-out gain with intervals excluding zero) are
decided from these numbers in DECISIONS.md.
