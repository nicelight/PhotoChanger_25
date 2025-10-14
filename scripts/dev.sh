#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log_step() {
  printf '\n==> %s\n' "$1"
}

run_optional() {
  local cmd_name="$1"
  shift
  if command -v "$cmd_name" >/dev/null 2>&1; then
    "$cmd_name" "$@"
  else
    printf 'Skipping %s: command not found\n' "$cmd_name" >&2
  fi
}

log_step "Checking Python sources compile"
python -m compileall src

log_step "Running ruff (if available)"
run_optional ruff check src

log_step "Running pytest (if available)"
if command -v pytest >/dev/null 2>&1; then
  pytest -q "$@"
else
  printf 'Skipping pytest: command not found\n' >&2
fi
