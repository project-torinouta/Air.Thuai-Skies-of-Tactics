```plaintext
❯ uv run benchmark.py  --p1 tactical --p2 aggressive --rounds 100
THUAI9 Strategy Benchmark
Board: ./BoardCase/case1.txt
Games per matchup: 100
Max in-game rounds: 100

Matchup: tactical (P1) vs aggressive (P2)
  Init: P1=tactical, P2=aggressive
  Action: P1=tactical, P2=aggressive
==============================================================================
Matchup                         P1 Wins  P2 Wins  Draws  P1 Win%
------------------------------------------------------------------------------
tactical vs aggressive               84       16      0    84.0%
==============================================================================
```
