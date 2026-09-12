---
name: session-end
description: Close a build session — build log, decision log, commit, push. Invoke as /session-end 1 (day number)
disable-model-invocation: true
---
Day: $ARGUMENTS

1. Write build-log/day$ARGUMENTS.md with: tasks completed (ids), gates passed with evidence links, decisions made today (copy from the decision log), open issues, fallbacks in effect, and the exact commands to resume tomorrow (`make dev-api`, `make dev-ui`, pending task id).
2. Confirm docs/11-assumptions-and-approach.md decision log has every deviation from today. Add any that are missing.
3. `git status` — ensure .env, runs/, .cache/ are not tracked. Commit everything with `docs: day $ARGUMENTS build log` and push.
4. Print a 10-line handoff summary the user can paste into tomorrow's fresh session.
