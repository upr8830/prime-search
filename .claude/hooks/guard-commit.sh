#!/usr/bin/env bash
# Before any git commit: refuse if staged changes contain secrets or forbidden files.
input=$(cat)
cmd=$(printf '%s' "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p' | head -n1)
case "$cmd" in
  *"git commit"*)
    if git diff --cached --name-only 2>/dev/null | grep -Eq '(^|/)(\.env|starter_agent\.py)$'; then
      echo "BLOCKED: .env or starter_agent.py is staged. Unstage it." >&2; exit 2
    fi
    if git diff --cached 2>/dev/null | grep -Eq '(tvly-[A-Za-z0-9]{10,}|lsv2_[A-Za-z0-9_]{10,})'; then
      echo "BLOCKED: an API key pattern is in the staged diff." >&2; exit 2
    fi ;;
esac
exit 0
