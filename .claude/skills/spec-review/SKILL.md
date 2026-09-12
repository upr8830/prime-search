---
name: spec-review
description: Adversarial review of the current diff against its spec before a gate. Invoke with the task id, e.g. /spec-review 1.7
#disable-model-invocation: true
---
Task under review: $ARGUMENTS (a task id from docs/09-implementation-plan.md).

1. Read the task's entry in docs/09 and list the spec sections it cites.
2. Run `git diff --stat` and `git diff` for uncommitted work, or `git log --oneline -20` and the diff since the last gate commit if the work is committed.
3. Use the `spec-reviewer` subagent with: the task id, the spec sections, and the diff.
4. For each reported gap that affects correctness or a stated requirement: fix it, re-run the task's check, and re-review once.
5. Print the final gap report (should be mostly "none") followed by the gate evidence the task asks for.
