# Operator Guide — step by step, assuming nothing

This is what *you* do, in order, from a blank Mac to a submitted assignment. Claude Code does the
coding; this guide covers everything around it: accounts, installs, folder setup, starting Claude
Code, what to do at each gate, validating the dataset, testing the UI, approving GEPA, and
submitting.

Total: roughly 2 hours of setup on Day 0 (Parts 0–3), then 2–4 hours of your attention on each of
the three build days. Time estimates are for a first run. Commands are typed into the Terminal app unless stated
otherwise. Lines starting with `$` are commands (don't type the `$`). Anything in `<angle brackets>`
is a value you replace.

---

## Part 0 — Before you start (15 min)

You need five accounts. Open a note and keep the keys there temporarily; you will paste them into
one file (`.env`) and then delete the note.

| Account | Why | Where |
|---|---|---|
| Tavily | The search API the agent uses | https://app.tavily.com |
| Nebius Token Factory | Hosts the LLMs (Nemotron, Kimi, DeepSeek) | https://tokenfactory.nebius.com |
| LangSmith | Traces, datasets, evaluation | https://smith.langchain.com |
| GitHub | The deliverable repository | https://github.com |
| Claude (Pro or Max) | Claude Code | https://claude.ai |

**Claude plan note.** Three days of Claude Code building is heavy usage. Pro can hit usage limits
mid-session; Max is more comfortable. If you hit a limit, Claude Code tells you when it resets; you
can also check `/usage` inside a session.

### 0.1 Tavily key
1. Go to https://app.tavily.com and sign up or sign in.
2. Find **API Keys** in the left menu. Copy the key — it starts with `tvly-`.
3. Note your plan's monthly credit allowance. The build uses roughly 1,500–3,000 search/extract
   calls over three days including GEPA. If you are on a free tier, upgrade now rather than
   discovering the cap on Day 3.

### 0.2 Nebius Token Factory key
1. Go to https://tokenfactory.nebius.com and sign in (Google or email).
2. Add billing / credits if prompted. Expect roughly $10–40 total for the build depending on how
   much GEPA you run.
3. Go to **API keys** and create one. Copy it.
4. While you are there, open the model catalog and confirm these three appear:
   `nvidia/nemotron-3-super-120b-a12b`, `moonshotai/Kimi-K2.6`, `deepseek-ai/DeepSeek-V3.2`. If a
   name differs, write the exact name you see — you will give it to Claude Code in Part 5.

### 0.3 LangSmith key
1. Go to https://smith.langchain.com and sign up.
2. Click your avatar or **Settings** → **API Keys** → **Create API Key**. Copy it — it starts with
   `lsv2_`.
3. You do not need to create a project by hand; the code creates `prime-search` automatically.

### 0.4 GitHub repository
1. Sign in to https://github.com. Click **+** (top right) → **New repository**.
2. Name: `prime-search`. Visibility: **Private** for now (you can make it public or invite
   reviewers at submission). Do **not** tick "Add a README" — the repo must be empty.
3. Click **Create repository**. Leave the page open; you will need the URL that looks like
   `https://github.com/<your-username>/prime-search.git`.
4. If you have never pushed to GitHub from this Mac, you will need authentication. The simplest
   path is GitHub's CLI: install it in Part 1 and run `gh auth login`.

### 0.5 Claude subscription
Make sure you can sign in at https://claude.ai with a Pro or Max plan. That login is what Claude
Code will use.

---

## Part 1 — Install the tools (30–45 min)

Open **Terminal** (press `Cmd+Space`, type `Terminal`, press Enter).

### 1.1 Xcode command line tools (gives you git and compilers)
```
$ xcode-select --install
```
A dialog appears; click **Install**. Wait for it to finish (5–15 min). If it says "already
installed", good.

### 1.2 Homebrew (package manager for Mac)
```
$ /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Follow the prompts (it asks for your Mac password). At the end it prints two or three lines
starting with `echo` and `eval` under "Next steps" — copy and run those exactly, then close and
reopen Terminal. Check:
```
$ brew --version
```

### 1.3 Git, GitHub CLI, Node.js, pnpm
```
$ brew install git gh node
$ npm install -g pnpm
$ git --version && node --version && pnpm --version
```
Node should print `v20` or higher. Then authenticate GitHub:
```
$ gh auth login
```
Choose **GitHub.com** → **HTTPS** → **Login with a web browser**, follow the code prompt in the
browser.

### 1.4 uv (Python package manager) and Python
```
$ curl -LsSf https://astral.sh/uv/install.sh | sh
```
Close and reopen Terminal, then:
```
$ uv --version
$ uv python install 3.12
```

### 1.5 Claude Code
```
$ curl -fsSL https://claude.ai/install.sh | bash
```
Close and reopen Terminal, then:
```
$ claude --version
```
It should print a version number followed by `(Claude Code)`. (Alternative if that fails:
`brew install --cask claude-code`.)

### 1.6 A text editor
Install VS Code from https://code.visualstudio.com if you don't have one. You will use it to edit
`.env`, review the dataset, and edit the technical statement. After installing, open VS Code, press
`Cmd+Shift+P`, type `Shell Command: Install 'code' command in PATH`, press Enter — this lets you
type `code .` in Terminal to open a folder.

---

## Part 2 — Set up the project folder (15 min)

### 2.1 Create the working area
```
$ mkdir -p ~/tavily
$ cd ~/tavily
```

### 2.2 Put the starter agent OUTSIDE the repo
Move the `starter_agent.py` you received from Tavily into `~/tavily/` — that is, next to the repo,
not inside it. In Finder: drag the file into your home folder → `tavily`. Check:
```
$ ls ~/tavily
```
You should see `starter_agent.py`.

### 2.3 Unpack the planning package into the repo folder
Download `prime-search-planning.zip` from this chat. In Terminal:
```
$ cd ~/tavily
$ unzip ~/Downloads/prime-search-planning.zip
$ ls -a ~/tavily/prime-search
```
You should see `.claude`, `CLAUDE.md`, `KICKOFF_PROMPT.md`, `OPERATOR_GUIDE.md`, `README.md`,
`data`, `docs`. The `.claude` folder is hidden (that's why `ls -a`); it holds Claude Code's
settings, guard hooks, and the `/gate`, `/spec-review`, `/session-end`, `/validate-bench` skills.
Make the hook scripts executable:
```
$ chmod +x ~/tavily/prime-search/.claude/hooks/*.sh
```

### 2.4 Create the `.env` file with your keys
```
$ cd ~/tavily/prime-search
$ code .
```
In VS Code: **File → New File**, paste the following, replacing the placeholders with your real
keys (no quotes needed, no spaces around `=`):
```
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxx
NEBIUS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
LANGSMITH_API_KEY=lsv2_xxxxxxxxxxxxxxxxxxxx
LANGSMITH_PROJECT=prime-search
LANGSMITH_TRACING=true
```
Save it as `.env` (exactly, with the leading dot) inside `~/tavily/prime-search`. VS Code may warn
about dotfiles; that's fine. Now delete the note where you kept the keys.

### 2.5 Initialize git and connect GitHub
```
$ cd ~/tavily/prime-search
$ printf ".env\nruns/\n.cache/\nnode_modules/\nstarter_agent.py\n__pycache__/\n.venv/\n" > .gitignore
$ git init -b main
$ git add .
$ git commit -m "docs: planning package (PRD, specs, SearchBench seed, Claude Code config)"
$ git remote add origin https://github.com/<your-username>/prime-search.git
$ git push -u origin main
```
Refresh the GitHub page: you should see the files, including the `.claude` folder. **Check that
`.env` is NOT listed.** If it is, do not continue: run `git rm --cached .env && git commit -m "fix:
remove env" && git push`, then regenerate all three keys (they are now in GitHub history) and put
the new ones in `.env`.

### 2.6 Prove the keys work using the starter agent
This is a 60-second test that catches most setup problems before Claude Code starts.
```
$ cd ~/tavily
$ cp prime-search/.env .
$ uv run starter_agent.py "What is the Medicare LCD for glucose monitors?"
```
The first run downloads packages (1–2 min). You should see a tool call panel, a streamed answer,
and a LangSmith trace URL. Open the URL in a browser — you should see the trace. If anything fails,
see Part 9 before continuing.

---

## Part 3 — Start Claude Code (10 min)

```
$ cd ~/tavily/prime-search
$ claude
```
First run: it opens a browser to sign in with your Claude account. Approve. Back in Terminal you
see the Claude Code prompt.

**Permission mode.** Press `Shift+Tab` to cycle modes; the mode is shown near the prompt. There
are three you will use: **plan mode** (Claude reads and plans but changes nothing — use it while it
reads the docs and plans each phase), **auto / accept edits** (Claude edits and runs commands without
asking — the default on Pro/Max, and what you want while it builds), and **manual** (asks for each
change — not needed here). The repo's `.claude/settings.json` pre-approves the safe commands
(`uv`, `make`, `pnpm`, `git commit`) and blocks the dangerous ones, and two hooks block any write to
`.env` or `starter_agent.py` and any commit containing an API key. If Claude asks to approve a
command you don't recognize, ask it to explain first.

**Give it the kickoff prompt.** Type this and press Enter:
```
Read KICKOFF_PROMPT.md and follow everything below its horizontal rule as your instructions. Start now.
```
(Typing this one line avoids pasting a long multi-line prompt into the terminal.)

Claude Code first runs `/context` and `/hooks` to confirm its config loaded (you should see
`CLAUDE.md` listed and two PreToolUse hooks), then reads the docs in plan mode (2–5 min), gives you
a Day 1 phase summary, and starts task 1.1. If it reports that the hook or settings format is out
of date for its version, let it fix `.claude/settings.json` and log the change — that is expected
occasionally.

**What a gate looks like.** When Claude reaches a `[G]` task it runs `/gate <task-id>` and prints:
the commands it ran, their real output, LangSmith trace URLs, a "spec-review gap report" from a
separate reviewer, any decision-log lines added, and then `Gate 1.2 — waiting for your go-ahead.`
Read the gap report: items under "none" are fine; anything else, reply `fix the gaps first`. When
satisfied reply `approved, continue`.

**If it asks about model names** (because the catalog names differ from the spec), give it the
exact names you noted in 0.2.

---

## Part 4 — Day 1: what you do while it builds (2–4 hours of your attention over the day)

You do not need to watch every line. You need to be present at the gates. The gates are marked
**[G]** in `docs/09-implementation-plan.md`; Claude Code will stop and show you evidence at each.

### Gate 1.2 — Smoke test (`/gate 1.2`)
It shows the output of `make smoke`. What you are checking:
- Each role (root, sub-agent, judge) says **PASS**, or says **FALLBACK** with the model it switched
  to. Fallback is fine; it should say it logged the decision. Reply: `ok, continue`.
- Tavily search and extract both PASS. If extract fails on the CMS page, it should propose the
  raw-content fallback; reply `yes, implement the fallback and log it`.
- A LangSmith trace URL appears. Open it in your browser once.

### Gate 1.7 — First real answers (`/gate 1.7`)
It shows a PRIME answer and a baseline answer for the CGM non-insulin question, plus two trace
URLs. What you are checking:
- The PRIME answer has numbered citations like `[1]`, an **Effective dates relied on** section, and
  a **Sources** list where at least one source is `cms.gov`.
- The baseline answer is shorter with URL citations only.
- Open the PRIME trace URL. You should see nested runs: `understand`, `plan`, several
  `search_agent:*`, `synthesize`. Take a screenshot (`Cmd+Shift+4`) and save it as
  `build-log/day1-trace.png`; you can also drag the image into the Claude Code window if you want
  it to look at something in the trace.
If the PRIME answer has no citations or no cms.gov source, reply: `the answer is missing citations
/ primary sources — check the search_agent evidence rules in docs/03 §4 and fix before continuing`.

### After 1.8 — Source fetch diff
It shows, per SearchBench question, which key phrases were found and which dates or codes differ
from the drafts. Skim it; note anything surprising. You act on it on Day 2.

### Ending the Day 1 session
Type `/session-end 1`. It writes `build-log/day1.md`, checks the decision log, commits, pushes, and
prints a 10-line handoff summary — **copy that summary into a note; you paste it tomorrow.** Then
save the raw transcript: type `/export` and save to `build-log/day1-transcript.md` (if `/export`
isn't available in your version, ask: `write a detailed transcript of this session to
build-log/day1-transcript.md`). Then `/exit`.

### If the session gets long
Claude Code compacts its own memory when needed; you can also type `/compact` at a natural pause.
Type `/context` any time to see how full the context window is. Start each day as a **fresh
session** (Part 5.1) rather than continuing — a clean context with the handoff summary works better
than a long one.

---

## Part 5 — Day 2: your validation hour, then the UI (3–4 hours of attention)

### 5.1 Start a fresh Day 2 session
The dataset file is protected by a hook; unlock it for this session only, then start Claude Code:
```
$ cd ~/tavily/prime-search
$ export ALLOW_BENCH_EDIT=1
$ claude
```
Paste yesterday's handoff summary, then type:
`This is Day 2. Read CLAUDE.md, docs/09, and build-log/day1.md, then run /validate-bench.`

### 5.2 Validate the 30 answer keys (~1 hour) — this is the one task only you can do
`/validate-bench` walks you through one record at a time: the question, the draft claims, the
passages it found in the live CMS/FDA pages, any mismatch (dates, codes, wording), and a one-line
recommendation. For each question:

1. Read the draft `summary` and `required_claims`.
2. Read the matched passages. If a claim's passage is missing or says something different, the
   claim is wrong — decide the correct claim from the passage.
3. For anything you are unsure about, open the source URL in your browser and read the section
   yourself. For the CGM LCD, the section to check is **Coverage Indications, Limitations, and/or
   Medical Necessity**; the revision date is at the top under **Revision Effective Date**.
4. Tell Claude Code your corrections in plain English, e.g.:
   `cgm-elig-001: claim c3 date is wrong, the revision effective date on the page is <date>. cgm-code-001: the article lists codes <codes>; replace. glp1-path-005: replace the summary with: <your text>.`
   It edits the JSONL for you. You never need to hand-edit JSON.
5. When a record is right, say `cgm-elig-001 validated`. Claude Code sets `validated_by` to your
   name (it asks for it once) and `as_of` to today's date. It never marks a record validated on
   its own.

Start with the six highest-risk records listed in `data/searchbench/README.md`. It is fine to
simplify a key (fewer claims) if the live page doesn't support the draft; it is not fine to leave a
claim you couldn't find evidence for. If a question turns out to be unanswerable from primary
sources, tell Claude Code to convert it to an out-of-scope record or replace it with a simpler one.

When all 30 are done: `all validated — sync to LangSmith and continue with 2.2`.

### Gate 2.3 — Dev-split evaluation table (`/gate 2.3`)
It shows a small table: baseline vs prime on 5 questions, with all metric columns filled. Sanity
checks: prime should beat baseline on `evidence_recall` and `citation_correctness`; if a column is
all zeros or all ones, say so — that's usually an evaluator bug.

### Gate 2.5 — Try the UI yourself (`/gate 2.5`)
Claude Code will tell you it's ready. Open **two more Terminal windows** (`Cmd+N` in Terminal):

Window A:
```
$ cd ~/tavily/prime-search && make dev-api
```
Window B:
```
$ cd ~/tavily/prime-search && make dev-ui
```
Then open http://localhost:3000 in your browser.

1. Pick a preset question (e.g. the CGM non-insulin one). Click **Ask**.
2. Left pane finishes in ~10–20 s. Right pane shows the search tree growing over 1–3 min.
3. When done, hover a `[n]` citation in the right pane — an evidence passage should appear. Click
   it — the document view should open with the paragraph highlighted.
4. Click **Evidence** and **Claims** tabs; look for tier badges and status labels.
5. Click 👍 on the right pane. Open https://smith.langchain.com → project `prime-search` → the
   latest run → **Feedback** tab: `user_thumbs` should be there.
6. Try an out-of-scope preset ("Will Aetna cover my Ozempic?") — an amber scope warning should show.

Report anything broken to Claude Code in plain words ("citation hover shows nothing", "tree never
updates"). Leave windows A and B running; `Ctrl+C` stops them when you're done.

### Ending Day 2
If your Mac will stay on overnight, first type: `start make bench for baseline and prime-base on
holdout with cache on, in the background, and tell me how to check progress tomorrow`. Then
`/session-end 2`, `/export` to `build-log/day2-transcript.md`, copy the handoff summary, `/exit`.
In the Terminal window, run `unset ALLOW_BENCH_EDIT` so the dataset is locked again.

---

## Part 6 — Day 3: GEPA, report, statement, submit (3–5 hours)

### 6.1 Fresh Day 3 session and GEPA approval
```
$ cd ~/tavily/prime-search && claude
```
Paste the Day 2 handoff summary, then type:
`This is Day 3. Read CLAUDE.md, docs/09, and build-log/day2.md. Start task 3.1 and give me the cost estimate before running GEPA.`

It reports estimated Tavily calls, tokens, dollars, and wall time. Typical: 400–900 Tavily calls
(mostly cached), a few million tokens, $5–20, 1.5–3 h. If the estimate exceeds your Tavily
allowance or budget, reply: `reduce to plan.md and judge.md only and halve max_metric_calls`.
Otherwise: `approved, run it`. It runs in the background; you can keep working with Claude Code
on the README in the meantime.

### Gate 3.2 — Final report (`/gate 3.2`)
It shows the headline table (baseline / prime-base / prime-optimized × metrics on the holdout
split). Read it honestly: if GEPA didn't help, the report says so — that is acceptable and
believable. Open `reports/final-report.md` in VS Code and read the three worked examples; these are
what reviewers will read.

### 6.2 Edit the technical statement (45 min, you)
Claude Code drafts `TECHNICAL_STATEMENT.md`. Open it in VS Code and edit for your voice:
- First paragraph: why you picked this problem, in your words.
- Keep the table and one before/after example.
- Keep the "what I didn't build and why" paragraph — reviewers value scope judgement.
- Keep it under two pages when printed.
Save it, then tell Claude Code: `I edited TECHNICAL_STATEMENT.md; commit it.`

### 6.3 Packaging checks (you run these)
```
$ cd ~/tavily/prime-search
$ git status
```
Should say "nothing to commit, working tree clean". Then a fresh-clone test in a new folder:
```
$ cd ~/tavily
$ git clone https://github.com/<your-username>/prime-search.git fresh-check
$ cd fresh-check
$ cp ../prime-search/.env .
$ make setup && make smoke && make ask Q="Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?"
```
If that works from a fresh clone, a reviewer can run it. Also confirm:
```
$ ls ~/tavily/fresh-check | grep starter_agent   # must print nothing
$ ls -a ~/tavily/fresh-check | grep .claude        # must print .claude (reviewers get the skills too)
$ git -C ~/tavily/fresh-check log --oneline | wc -l   # a healthy history is dozens of commits
```
Then delete the check folder: `rm -rf ~/tavily/fresh-check`.

### 6.4 Build record
Run `/session-end 3` and `/export` to `build-log/day3-transcript.md` before the packaging checks
above if you haven't already. Confirm `build-log/` contains `day1.md`, `day2.md`, `day3.md`, the
three transcript exports, `day1-trace.png`, and a `README.md` index. If you made the optional screen recording, upload it somewhere shareable
(Google Drive with link access) and put the link in `build-log/README.md`.

### 6.5 Make the repo available
On GitHub → repository **Settings** → **General** → scroll to **Danger Zone** → **Change
visibility** → Public, *or* keep it private and add the reviewers as collaborators (**Settings →
Collaborators → Add people**) using the GitHub usernames Tavily gave you.

### 6.6 Rotate keys if the repo is public
Even though `.env` was never committed, rotate the Tavily, Nebius, and LangSmith keys after
submission as a habit (each console has a "regenerate/revoke" option). Update your local `.env`.

### 6.7 Submit
Send Tavily: the repository URL, the path to `TECHNICAL_STATEMENT.md`, and the path to
`build-log/README.md` (plus the recording link if any). Mention that `runs/examples/` contains
pre-recorded runs viewable in the UI without API keys, and that `make setup && make smoke` verifies
their environment.

---

## Part 7 — Things to know while Claude Code works

- **Keys you'll use:** `Esc` stops Claude mid-action (context is kept — you can redirect).
  `Esc Esc` or `/rewind` opens a menu to restore the conversation and the files to an earlier
  point. `Shift+Tab` changes permission mode. `/context` shows context usage. `/help` lists commands.
- **After two failed corrections on the same thing, stop correcting.** Type `/clear`, then give a
  new, more specific instruction that includes what you learned. A clean session with a better
  prompt beats a long session full of failed attempts.
- **Gates are run with `/gate <task-id>`**, which includes an adversarial review by a separate
  subagent. If the gap report lists real gaps, tell Claude to fix them before you approve.
- **It will ask before spending on GEPA and at every gate.** Everything else it does on its own.
- **When it asks a question you don't understand**, ask it to explain the two options and
  recommend one. Then say `go with your recommendation and log it`.
- **If it seems stuck** (same error three times), say: `stop, summarize what is failing and the
  three most likely causes, then try the most likely one`.
- **If it starts building something from the roadmap** (memory, skills, RL, other payers), say:
  `that's roadmap — stop and return to the plan`.
- **If you run out of Claude usage**, wait for the reset it reports; the repo and build log are on
  disk, nothing is lost. Resume the same day with `claude -c`; on a new day start fresh with the
  handoff summary.
- **Where the raw transcripts live** if you forget `/export`: Claude Code keeps every session under
  `~/.claude/projects/`. Ask Claude Code to `copy today's session transcript into build-log/`.
- **Cost check**: Nebius and Tavily consoles both show usage; glance at them at the end of Day 1
  and Day 2.
- **Never paste API keys into the Claude Code chat.** They live only in `.env`.

---

## Part 8 — Daily checklist

| | Day 1 | Day 2 | Day 3 |
|---|---|---|---|
| Start | `claude` + kickoff line | fresh `claude` + handoff (+ `export ALLOW_BENCH_EDIT=1`) | fresh `claude` + handoff |
| Your gates (`/gate`) | 1.2 smoke, 1.7 first answers | 2.1 validation (1 h, `/validate-bench`), 2.3 table, 2.5 UI | 3.1 GEPA approval, 3.2 report |
| Your writing | — | corrections to answer keys | technical statement |
| End | `/session-end 1` + `/export` | `/session-end 2` + `/export` (+ overnight bench) | `/session-end 3`, fresh-clone test, submit |

---

## Part 9 — Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: brew/uv/claude` after install | Close and reopen Terminal. If still missing, the installer printed a line to add to your shell profile — rerun the installer and read its last lines. |
| Starter test says `Missing TAVILY_API_KEY` | `.env` is not in the folder you ran from, or the line has quotes/spaces. Open `.env`, remove quotes, ensure `KEY=value` with no spaces. |
| Starter test: 401 / authentication error from Nebius | Key copied incorrectly, or no billing on the Token Factory account. Regenerate the key. |
| Starter test: model not found | The model name on Token Factory differs. Use the name from the catalog: `uv run starter_agent.py --model <exact-name> "..."`. Tell Claude Code the name. |
| No LangSmith trace URL printed | `LANGSMITH_API_KEY` missing or wrong prefix. Confirm it starts with `lsv2_`. |
| `git push` rejected / asks for password | Run `gh auth login` again. GitHub does not accept account passwords; the CLI handles tokens. |
| Claude Code says it can't run a command (permission) | Press `Shift+Tab` to switch to a mode that allows edits and commands, or approve the prompt. |
| UI shows nothing at localhost:3000 | Both `make dev-api` and `make dev-ui` must be running in separate windows. Check window A shows `Uvicorn running on http://127.0.0.1:8000`. |
| Right pane never finishes | Budget or deadline hit; the answer's Unknowns section will say so. If it truly hangs > 5 min, tell Claude Code and paste the last lines from window A. |
| Tavily "credits exhausted" | Upgrade plan or wait for reset; tell Claude Code to run with `tavily_cache=true` and reduce `max_searches`. |
| Claude usage limit reached | Wait for the reset time shown; resume with `claude -c` (same day) or a fresh session with the handoff (next day). |
| `/gate`, `/session-end`, `/validate-bench` not recognized | The `.claude/skills/` folder is missing or you started Claude Code outside the repo folder. `cd ~/tavily/prime-search` and restart. |
| Claude says a write was "BLOCKED" | That is the guard hook doing its job. For the dataset during Day 2, you forgot `export ALLOW_BENCH_EDIT=1` before starting `claude`. |

---

## Part 10 — What "done" looks like

- GitHub repo `prime-search` with: code, `docs/`, `.claude/`, `data/searchbench/` (validated),
  `reports/final-report.md`, `TECHNICAL_STATEMENT.md`, `build-log/`, `runs/examples/`, a runnable
  `README.md`, and no `starter_agent.py` or `.env`.
- LangSmith project `prime-search` with traces, dataset `searchbench-v0`, and three experiments on
  holdout.
- A UI a reviewer can start with two commands and use without your help.
- A decision log that shows, dated, every place reality differed from the plan.
