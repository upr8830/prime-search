#!/usr/bin/env bash
# Blocks writes to files that must never be created or changed by the agent.
# Receives the tool call as JSON on stdin. Exit 2 = block with the message on stderr.
input=$(cat)
path=$(printf '%s' "$input" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)
case "$path" in
  *starter_agent.py)   echo "BLOCKED: starter_agent.py must never exist in this repo." >&2; exit 2 ;;
  *.env|*/.env)        echo "BLOCKED: never write .env; edit .env.example instead." >&2; exit 2 ;;
  *data/searchbench/searchbench_v0.jsonl)
    if [ "${ALLOW_BENCH_EDIT:-0}" != "1" ]; then
      echo "BLOCKED: searchbench_v0.jsonl is edited only during task 2.1 validation. Run: export ALLOW_BENCH_EDIT=1 in the shell before that task, then unset it." >&2; exit 2
    fi ;;
esac
exit 0
