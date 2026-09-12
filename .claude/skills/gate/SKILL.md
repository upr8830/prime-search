---
name: gate
description: Assemble the evidence for a [G] gate in docs/09 and stop for user approval. Invoke as /gate 1.2
#disable-model-invocation: true
---
Gate: $ARGUMENTS

1. Read the gate's acceptance check in docs/09-implementation-plan.md.
2. Run the check(s). Capture real output; do not paraphrase.
3. Run /spec-review for the same task id.
4. Present, in this order: the command(s) run; the output (trimmed to the relevant lines); LangSmith trace URLs if any; the spec-review gap report; any decision-log lines added today.
5. Say exactly: "Gate $ARGUMENTS — waiting for your go-ahead." and stop. Do not start the next task.
