# 13 — Claude Code Practices Applied to This Build

Source: Claude Code's official best-practices guide (code.claude.com/docs, checked September 12,
2026). This doc maps each practice to where it lives in this repo so nobody has to remember it.

| Practice (from the guide) | Where it is applied here |
|---|---|
| **Keep `CLAUDE.md` short**; bloated files get ignored | `CLAUDE.md` is ~35 lines: commands, hard constraints, non-default conventions, workflow rules. Layout moved to `docs/01` §10; long specs stay in `docs/` and are read on demand. |
| Emphasize the one rule that keeps getting skipped | `IMPORTANT:` on the decision-log rule only. |
| Tell Claude what to preserve when compacting | Last line of `CLAUDE.md`. |
| **Give Claude a check it can run** | Every task in `docs/09` has an acceptance check; `CLAUDE.md` requires showing real output. `make smoke`, `make test`, `curl` checks, bench rows. |
| **Explore → plan → code → commit**, plan mode for multi-file work | Kickoff prompt: plan mode at the start of each task group, skip for one-liners. |
| Adversarial review in a fresh context before calling work done | `.claude/agents/spec-reviewer.md` + `/spec-review <task>`; run automatically by `/gate`. |
| Hooks for things that must happen every time | `.claude/hooks/guard-paths.sh` (no `.env`, no `starter_agent.py`, dataset locked outside validation) and `guard-commit.sh` (no secrets or forbidden files in a commit). |
| Permission allowlists to cut prompts | `.claude/settings.json` allows `uv`, `make`, `pnpm`, `git` (no force-push), `curl localhost`; denies reading/writing `.env`. |
| Skills for repeatable workflows, `disable-model-invocation` for side-effectful ones | `/gate`, `/session-end`, `/validate-bench`, `/spec-review` in `.claude/skills/`. |
| Use subagents for investigation to keep context clean | Kickoff prompt rule; spec-reviewer is a subagent. |
| Course-correct early; `/clear` after two failed corrections | Operator guide Part 7; kickoff prompt "failed twice → stop and re-plan". |
| Fresh session per workstream instead of endless continuation | One session per day, started with the `/session-end` handoff summary. |
| Use CLI tools (`gh`) | Operator guide installs `gh`; Claude can open PRs/issues if needed. |
| Have Claude show evidence rather than assert success | `/gate` output format: commands, output, trace URLs, gap report. |
| Checkpoints / `/rewind` for risky attempts | Operator guide Part 7. |

## What was deliberately not added

- **Stop hooks that block the turn until tests pass.** Useful for unattended runs; this build is
  attended and gated, and a strict stop hook can loop on flaky live-API tests. Add later if you run
  bench or GEPA unattended.
- **Agent teams / worktrees.** The plan is sequential and the gates are human; parallel sessions
  would add coordination cost without saving time in three days.
- **MCP servers.** Nothing here needs one; LangSmith is used through its SDK in code.

## Verifying the config loaded

In a session: `/context` (CLAUDE.md present), `/hooks` (two PreToolUse hooks listed), `/` (the four
skills appear). If the hook or settings schema has changed in your Claude Code version, ask Claude
Code to update `.claude/settings.json` to the current schema and log it.
