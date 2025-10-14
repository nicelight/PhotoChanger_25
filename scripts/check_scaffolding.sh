#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run_step() {
  local title="$1"
  shift
  printf '\n==> %s\n' "$title"
  "$@"
}

run_optional() {
  local title="$1"
  local cmd="$2"
  shift 2
  if command -v "$cmd" >/dev/null 2>&1; then
    run_step "$title" "$cmd" "$@"
  else
    printf 'Skipping %s: %s not found\n' "$title" "$cmd" >&2
  fi
}

CHECK_TARGETS=(
  "scripts"
  "src/app/core"
  "src/app/providers"
  "src/app/api/generated"
  "src/app/api/schemas"
)

run_optional "ruff check" ruff check "${CHECK_TARGETS[@]}"
run_optional "ruff format --check" ruff format --check "${CHECK_TARGETS[@]}"
run_optional "mypy" mypy --ignore-missing-imports --follow-imports=skip "${CHECK_TARGETS[@]}"
run_optional "pytest" pytest -q
