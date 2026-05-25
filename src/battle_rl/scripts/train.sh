#!/bin/bash
# Usage: cd src && bash battle_rl/scripts/train.sh

uv run python -m battle_rl.train \
    --steps 100000 \
    --eval-interval 10000 \
    --eval-games 10 \
    --horizon 512 \
    --batch-size 64 \
    --epochs 4 \
    --lr 3e-4 \
    --opponent child6 \
    --save checkpoints/ppo_child6.pt
