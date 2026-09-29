# ClipFactory docs — index

Start here. This is the map of `docs/`. Each file has one job.

## 🟢 Start here
| Doc | What it is |
| --- | --- |
| [v1-scope.md](v1-scope.md) | What V1 ships (and what it does not). |
| [global-video-understanding.md](global-video-understanding.md) | Why story-first, multi-segment clips. The product rationale. |

## 🎬 Pipeline & models
| Doc | What it is |
| --- | --- |
| [pipeline.md](pipeline.md) | Full execution spec — story path + simple path, step by step. |
| [clip-judge.md](clip-judge.md) | The native-video judge (Gemini 3 Flash) that watches the moments and picks the best clips. |
| [unit-economics.md](unit-economics.md) | Per-stage model prices, cost per credit / per video, margins. **Financial source of truth.** |

## 🛠️ Engineering reference
| Doc | What it is |
| --- | --- |
| [api-contract.md](api-contract.md) | HTTP API contract (endpoints, payloads). |
| [db-schema.md](db-schema.md) | Database schema. |
| [deploy.md](deploy.md) | Deploy runbook (VPS, Vercel, env). |
| [admin.md](admin.md) | Admin dashboard reference. |
| [security-audit.md](security-audit.md) | Security review and posture. |

## 📈 Growth
| Doc | What it is |
| --- | --- |
| [seo.md](seo.md) | SEO notes. |

## 🗄️ Legacy / handoff (kept for history, not maintained)
These are pre-build handoff artifacts. Safe to ignore for current work; archive
or delete when you want (ask before I move them).
| Doc | What it is |
| --- | --- |
| [handoff-codex.md](handoff-codex.md) | Original Codex handoff (558 lines, pre-build). |
| [codex-brief.md](codex-brief.md) | Original Codex brief. |
| [plan.md](plan.md) | Original V1 build plan. |

---

_Convention: one topic per file. New cross-cutting specs (like `clip-judge.md`)
get their own file and a row here — keep this index in sync._
