#!/usr/bin/env bash
#
# run_benchmark.sh — Run benchmark matchups pair by pair.
#
# Copyright 2026 AshGrey <ashgrey.huaier@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the
# following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

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

echo "=== Tactical ===" >&2
run tactical tactical aggressive aggressive "$ROUNDS_FAST"
run tactical tactical defensive defensive "$ROUNDS_FAST"
run tactical tactical random random "$ROUNDS_FAST"

echo "=== Warrior ===" >&2
run warrior warrior aggressive aggressive "$ROUNDS_FAST"
run warrior warrior defensive defensive "$ROUNDS_FAST"
run warrior warrior random random "$ROUNDS_FAST"

echo "=== Ranger ===" >&2
run ranger ranger aggressive aggressive "$ROUNDS_FAST"
run ranger ranger defensive defensive "$ROUNDS_FAST"
run ranger ranger random random "$ROUNDS_FAST"

echo "=== Sniper ===" >&2
run sniper sniper aggressive aggressive "$ROUNDS_FAST"
run sniper sniper defensive defensive "$ROUNDS_FAST"
run sniper sniper warrior warrior "$ROUNDS_FAST"
run sniper sniper tactical tactical "$ROUNDS_FAST"
run sniper sniper ranger ranger "$ROUNDS_FAST"
run sniper sniper random random "$ROUNDS_FAST"

echo "=== Cross ===" >&2
run tactical tactical ranger ranger "$ROUNDS_FAST"
run warrior warrior tactical tactical "$ROUNDS_FAST"
run ranger ranger warrior warrior "$ROUNDS_FAST"
run aggressive aggressive sniper sniper "$ROUNDS_FAST"

echo "=== Done ===" >&2
