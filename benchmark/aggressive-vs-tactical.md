```plaintext
❯ uv run benchmark.py --rounds 10 --p1 aggressive --p2 tactical --rounds 1000
THUAI9 Strategy Benchmark
Board: ./BoardCase/case1.txt
Games per matchup: 1000
Max in-game rounds: 100

Matchup: aggressive (P1) vs tactical (P2)
  Init: P1=aggressive, P2=tactical
  Action: P1=aggressive, P2=tactical
// Ignored
==============================================================================
Matchup                         P1 Wins  P2 Wins  Draws  P1 Win%
------------------------------------------------------------------------------
aggressive vs tactical              202      798      0    20.2%
==============================================================================
```
