```plaintext
❯ uv run benchmark.py  --p1 aggressive --p2 ranger --rounds 100
THUAI9 Strategy Benchmark
Board: ./BoardCase/case1.txt
Games per matchup: 100
Max in-game rounds: 100

Matchup: aggressive (P1) vs ranger (P2)
  Init: P1=aggressive, P2=ranger
  Action: P1=aggressive, P2=ranger
// Ignored
==============================================================================
Matchup                         P1 Wins  P2 Wins  Draws  P1 Win%
------------------------------------------------------------------------------
aggressive vs ranger                 13       84      3    13.0%
==============================================================================
```
