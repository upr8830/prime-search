# 07 — UI Specification (Next.js test harness)

Purpose: let a reviewer run one question through the starter-equivalent agent and PRIME Search side
by side, watch the investigation unfold, inspect evidence, and leave feedback. It is a test harness,
not a product UI. Clarity beats polish; every element should map to a concept in the specs.

## 1. Stack

- Next.js 15 (App Router), TypeScript, Tailwind. `pnpm`.
- Data: `@tanstack/react-query` for REST, a custom `useRunEvents(runId)` hook over `EventSource`.
- No component library; a handful of local components. Dark/light follows system.
- `next.config.js` rewrites `/api/:path*` → `http://localhost:8000/:path*`.

## 2. Routes

| Route | Purpose |
|---|---|
| `/` | Compare view (main) |
| `/runs` | Run history list (from `GET /runs`) |
| `/runs/[id]` | Single run detail (replays `events.jsonl`) |
| `/bench` | Latest bench summary table (from `GET /bench/summary`), links to LangSmith experiments |
| `/docs/[runId]/[docId]` | Document view with paragraph highlighting |

## 3. Compare view (`/`)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ PRIME Search harness                                        [Runs] [Bench]     │
├───────────────────────────────────────────────────────────────────────────────┤
│ Question [__________________________________________________] [Ask ▶]         │
│ Presets: [CGM eligibility ▾]   Depth: (● deep ○ fast)   Prompts: (● base ○ opt)│
├──────────────────────────────────────┬────────────────────────────────────────┤
│ SIMPLE SEARCH (starter)              │ PRIME SEARCH                            │
│ model · 1 tool                        │ root · subagent · budget                │
│──────────────────────────────────────│────────────────────────────────────────│
│ ▸ search: "medicare cgm coverage..." │ Understanding: cgm · eligibility · high │
│   5 results                           │ ┌ Search tree ───────────────────────┐ │
│                                       │ │ b1 LCD criteria        ● 4 ev  done │ │
│ Answer (streaming)…                   │ │   ├ search "L33822 coverage…" 8    │ │
│                                       │ │   ├ fetch LCD L33822 (primary,      │ │
│                                       │ │   │        rev 2023-04-16)          │ │
│                                       │ │   └ evidence ×4                     │ │
│                                       │ │ b2 Documentation reqs  ● 2 ev  done │ │
│                                       │ │ b3 Codes (article)     ◐ running    │ │
│                                       │ │ ── round 1: judge → insufficient,   │ │
│                                       │ │    2 new tasks                      │ │
│                                       │ │ b4 Recent changes      ○ pending    │ │
│                                       │ └────────────────────────────────────┘ │
│                                       │ [Answer] [Evidence 9] [Claims 6] [Critic]│
│                                       │ Answer (streaming)…                     │
│──────────────────────────────────────│────────────────────────────────────────│
│ 1 search · 8 s · 3.1k tok             │ 11 searches · 6 fetches · 4 agents ·    │
│ 👍 👎 [comment]     LangSmith ↗        │ 2 rounds · 74 s · 41k tok  👍 👎  ↗     │
└──────────────────────────────────────┴────────────────────────────────────────┘
```

Behavior:

- **Ask** starts two runs (`POST /run` × 2) and subscribes to both event streams. Baseline and prime
  run concurrently.
- Presets dropdown lists SearchBench questions (from `GET /bench/questions`) grouped by domain and
  tier, plus "custom".
- Left pane renders baseline events with the same components as the right pane, minus the tree.
- Right pane tabs: **Answer** (Markdown with `[n]` citations as hover cards → evidence text, tier,
  date; click → document view), **Evidence** (table: claim, stance, tier, date, doc, confidence;
  filter by branch; click row → document view with paragraph highlighted), **Claims** (list with
  status badges: supported / contested / weak / unresolved; contested shows both sides),
  **Critic** (weak claims, missing interpretations, recommended searches, completion probability).
- Search tree: a nested list, not a graph library. Branch nodes show status (pending/running/done),
  evidence count, and a one-line `TaskResult.summary` on expand. Round separators show the judge's
  verdict and how many tasks it added. Critic-triggered tasks are labeled `critic`.
- Footer per pane: `Usage` numbers, thumbs, comment, LangSmith trace link (when tracing is on).
- Feedback: thumbs sends `POST /feedback`; the button locks with a check mark. Comment is optional;
  on the prime pane the user can also flag claims from the Claims tab (adds `claim_ids_flagged`).
- Errors: `error` events render as a red banner in the affected pane; the other pane continues.
- Scope warning (`Answer.scope_warning`) renders as an amber banner above the answer.

## 4. Run detail (`/runs/[id]`)

Same right-pane layout, fed by replaying `GET /runs/{id}/events` (non-streaming JSON array).
Plus a **Plan** tab showing the raw `SearchPlan` and the root's plan code (from the `plan` event
payload, `code` field) — this is where the RLM code-as-action is visible to a reviewer.

## 5. Bench (`/bench`)

Table from `GET /bench/summary` (reads `reports/latest.json`): rows = configs (baseline / prime base
/ prime optimized), columns = metrics from 05 §2, plus per-tier expander. Links to the LangSmith
experiment URLs. If no report exists, show the `make bench` command.

## 6. Document view (`/docs/[runId]/[docId]`)

Renders `runs/<run_id>/docs/<doc_id>.txt` as paragraphs with indices; `?p=<index>` scrolls to and
highlights a paragraph; a sidebar lists all evidence drawn from this document. Header shows title,
tier, publisher, doc type, external id, effective/revision dates, URL.

## 7. API endpoints consumed

| Endpoint | Method | Body / Response |
|---|---|---|
| `/run` | POST | `RunRequest` → `{run_id}` |
| `/run/{id}/events` | GET | SSE (02 §4) |
| `/runs` | GET | `[{run_id, question, mode, status, started_at, usage}]` |
| `/runs/{id}` | GET | `RunRecord` |
| `/runs/{id}/events` | GET | `[event]` |
| `/docs/{run_id}/{doc_id}` | GET | `{document, paragraphs[], evidence[]}` |
| `/feedback` | POST | `{run_id, thumbs, comment?, claim_ids_flagged?}` → `{ok}` |
| `/ui-event` | POST | `{run_id?, type, payload}` → `{ok}` |
| `/bench/questions` | GET | SearchBench records (question, id, domain, tier) |
| `/bench/summary` | GET | latest report JSON or `{missing: true}` |

## 8. Components

`QuestionBar`, `PaneHeader`, `SearchTree` (+ `BranchNode`, `RoundSeparator`), `AnswerView`
(Markdown with citation hover), `EvidenceTable`, `ClaimList`, `CriticPanel`, `UsageFooter`,
`FeedbackControls`, `DocumentView`, `BenchTable`. Each takes typed props derived from the Pydantic
schemas (generate `ui/src/types.ts` from the FastAPI OpenAPI schema with `openapi-typescript` so
the contract stays in sync).

## 9. States and edge cases

- Tracing off → footer shows "tracing off" instead of a link.
- Budget exhausted → prime footer shows an amber "budget hit" chip; answer's Unknowns section
  explains.
- Baseline finishes first (always) → its pane shows complete while prime continues.
- Reconnect: if the SSE drops, the hook reconnects and replays from `GET /runs/{id}/events`.
- Long documents: document view paginates paragraphs at 200.

## 10. Design notes

- Typography-first, generous spacing, one accent color for prime, one neutral for baseline.
- Tier badges: primary (solid), official secondary (outline), professional/trade/web (muted).
- Status colors: supported green, contested amber, weak grey, unresolved red — always with a text
  label, never color alone.
- Keep everything server-independent of LangSmith: the UI must work with tracing off.
