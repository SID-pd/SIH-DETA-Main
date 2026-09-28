# Problem statement selection — rationale

Background on why **SIH26028 (Dynamic Forecast of ETA for Coaching Trains, Ministry of Railways)**
is the one being built. Source data: [sih_problems_data.json](../sih_problems_data.json), 226 SIH
2026 problem statements.

## Team resource profile

4 people, 2nd year: two strong at DSA/algorithms, one Infosys intern (production/enterprise dev),
one printdeed intern (full-stack), one with hands-on experience deploying RAG pipelines. No
hardware/embedded background, no budget. This fixes the search to **Software category, zero-budget /
no-hardware problem statements only** — Hardware (54 of 226 PS) was never in scope regardless of any
other consideration.

## Methodology used

The dataset's own `submittedCount`/`maxCount` fields are placeholders (0 and 500 for all 226 PS —
registrations hadn't opened), so there's no live competitor-count to rank by. Two proxies were used
instead:

- **Org/theme frequency** — how many PS share the same organization or theme, as a rough stand-in
  for how many teams are likely to gravitate there (flashy orgs like ISRO/DRDO/AICTE and popular
  themes pull bigger crowds; PSU/ministry names like Oil India, MRPL, Consumer Affairs pull fewer).
- **`complexityScore` distribution** — the dataset scores every PS 30/40/55/62/75/77/90. The two
  largest buckets are 30 (42 PS) and 62 (74 PS) — together ~51% of the dataset, i.e. the "modal"
  difficulty most teams are comfortable with.

## First-pass shortlist (RAG-fit + low visible competition)

Given the RAG-deployment specialist on the team, the first shortlist favored Software + `NLP & LLMs`
tagged PS in low-glamour orgs:

| ID | Title | Why it was shortlisted |
|---|---|---|
| SIH26045 | IP-SAKTI Sahayak — multilingual RAG assistant (Ministry of Ayush) | Title literally says "RAG-based, source-cited" — direct skill match, Ayush has only 5 PS total (low competition). |
| SIH26117 | Sovereign On-Premise Agentic AI Workbench (MRPL) | Requires self-hosting an LLM, filtering out teams that only know how to call an API. |
| SIH26107 / SIH26108 | AI assistant / recommendation engine over Indian Standards docs (Consumer Affairs) | Textbook retrieval-over-corpus use case, unglamorous domain. |
| SIH26121 / SIH26165 | NLP over drilling/safety reports (Oil India) | Real enterprise-NLP use case, PSU = low mindshare. |
| SIH26090 | AI cataloging for artisans (Social Justice) | Rarest theme in the whole dataset (Heritage & Culture, only 3 PS). |
| SIH26174 (fallback) | ISRO HAR — Foundational complexity (30) | Easiest PS in the dataset, high-prestige org, safety-net option. |

## What the team actually picked, and the pattern in it

The team's own shortlist (by `sno`): **28, 34, 56, 75, 187, 205**. Checking these against the
dataset revealed the real selection filter:

| sno | Complexity Score | Org (freq) | Theme (freq) |
|---|---|---|---|
| 28 | 62 | Ministry of Railways (3) | Smart Automation (55) |
| 34 | 30 | Consumer Affairs (10) | Miscellaneous (15) |
| 56 | 30 | MoSPI (4) | Smart Automation (55) |
| 75 | 62 | MoES (30) | Smart Education (11) |
| 187 | 62 | Home Affairs (11) | Blockchain & Cybersecurity (30) |
| 205 | 62 | **AICTE (34)** | Transportation & Logistics (7) |

Every single pick scores exactly **30 or 62** — the two most common complexity tiers — and nothing
scored 75/77/90. The real filter was a **complexity ceiling + a preference for concretely-scoped
problems** (one clear deliverable: a forecast, a scan verdict, a scraped index, a portal, a dashboard),
not competition-avoidance by theme/org rarity like the first-pass shortlist assumed.

Two risk flags surfaced from this: **sno 205** sits under AICTE, the single largest org (34 PS) and
is an open "submit your ideas" call with almost no spec — likely the most crowded of the six by a
wide margin. **sno 187** sits in Blockchain & Cybersecurity, the 2nd-largest theme (30 PS), and
"AI + surveillance + national security" tends to pull a disproportionate number of strong teams.
Every RAG-focused pick from the first-pass shortlist (SIH26045, SIH26117, etc.) also scores 62 or
30, so they remained valid lower-competition alternatives to 187/205 if a swap was ever wanted.

## Decision

**SIH26028** (sno 28, Dynamic ETA for Coaching Trains) was the one taken forward — it already
satisfied the team's own complexity ceiling, sits under a rare org (Ministry of Railways, only 3 PS
in this dataset), and has a genuinely concrete, well-scoped deliverable (a forecast number per
station) that plays directly to the DSA-strong members' strengths (graph traversal / delay
propagation) while still leaving room for the RAG specialist to add a real differentiator (the
delay-explanation assistant — see [project-architecture.md](./project-architecture.md)).
