#!/bin/bash
# Usage: cd src && bash battle_rl/scripts/evaluate.sh

MODEL=${1:-checkpoints/ppo_child6.pt}
GAMES=${2:-50}

uv run python -m battle_rl.evaluate \
    --model "$MODEL" \
    --games "$GAMES" \
    --opponent child6
