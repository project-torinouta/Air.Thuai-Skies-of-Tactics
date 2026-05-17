#!/usr/bin/env bash
#
# run_benchmark.sh — Run benchmark matchups pair by pair.
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR/src"

ROUNDS_FAST=${1:-30}
ROUNDS_SLOW=${2:-10}

BOARD_OPTS="--board-dir BoardCase/ --max-game-rounds 60 --seed 42"

# Generate shared boards once
uv run python benchmark.py --generate-boards 30 --board-rows 16 --board-cols 16 \
  --obstacle-density 0.12 --p1 aggressive --p2 defensive \
  --rounds 1 --max-game-rounds 5 2>/dev/null

run() {
  local p1_init=$1 p1_action=$2 p2_init=$3 p2_action=$4 rounds=$5
  local p1_label=$p1_init
  local p2_label=$p2_init
  [ "$p1_init" != "$p1_action" ] && p1_label="${p1_init}+${p1_action}"
  [ "$p2_init" != "$p2_action" ] && p2_label="${p2_init}+${p2_action}"
  local file="${PROJECT_DIR}/benchmark/${p1_label}-vs-${p2_label}.md"

  echo "  [${p1_label} vs ${p2_label}] x${rounds} ..." >&2
  local out
  out=$(uv run python benchmark.py \
    --p1-init "$p1_init" --p1-action "$p1_action" \
    --p2-init "$p2_init" --p2-action "$p2_action" \
    --rounds "$rounds" $BOARD_OPTS 2>&1) || true
  { echo '```plaintext'; echo "$out"; echo '```'; } > "$file"
  echo "$out" | grep -E "^[a-z]+.*[0-9]+" | tail -1 >&2
}

echo "=== Standard ===" >&2
run aggressive aggressive defensive defensive "$ROUNDS_FAST"
run aggressive aggressive random random "$ROUNDS_FAST"
run defensive defensive aggressive aggressive "$ROUNDS_FAST"
run defensive defensive random random "$ROUNDS_FAST"
run random random aggressive aggressive "$ROUNDS_FAST"
run random random defensive defensive "$ROUNDS_FAST"

echo "=== MCTS (aggressive init) ===" >&2
run aggressive mcts defensive defensive "$ROUNDS_SLOW"
run aggressive mcts aggressive aggressive "$ROUNDS_SLOW"
run aggressive mcts random random "$ROUNDS_SLOW"

echo "=== Alpha-Beta (aggressive init) ===" >&2
run aggressive alpha_beta defensive defensive "$ROUNDS_SLOW"
run aggressive alpha_beta aggressive aggressive "$ROUNDS_SLOW"
run aggressive alpha_beta random random "$ROUNDS_SLOW"

echo "=== Done ===" >&2
