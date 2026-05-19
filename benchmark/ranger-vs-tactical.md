```plaintext
❯ uv run benchmark.py  --p1 ranger --p2 tactical --rounds 100
THUAI9 Strategy Benchmark
Board: ./BoardCase/case1.txt
Games per matchup: 100
Max in-game rounds: 100

Matchup: ranger (P1) vs tactical (P2)
  Init: P1=ranger, P2=tactical
  Action: P1=ranger, P2=tactical
// Ignored
==============================================================================
Matchup                         P1 Wins  P2 Wins  Draws  P1 Win%
------------------------------------------------------------------------------
ranger vs tactical                   75       23      2    75.0%
==============================================================================
```
