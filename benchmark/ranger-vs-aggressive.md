```plaintext
❯ uv run benchmark.py  --p1 ranger --p2 aggressive --rounds 100
THUAI9 Strategy Benchmark
Board: ./BoardCase/case1.txt
Games per matchup: 100
Max in-game rounds: 100

Matchup: ranger (P1) vs aggressive (P2)
  Init: P1=ranger, P2=aggressive
  Action: P1=ranger, P2=aggressive
// Ignored
==============================================================================
Matchup                         P1 Wins  P2 Wins  Draws  P1 Win%
------------------------------------------------------------------------------
ranger vs aggressive                 87       12      1    87.0%
==============================================================================
```
