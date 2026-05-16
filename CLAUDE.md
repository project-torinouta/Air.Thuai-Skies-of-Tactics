# THUAI9 Skies of Tactics — Project Context

## Overview

THUAI9 苍穹棋域 (Skies of Tactics) is a turn-based AI competition game where two
players control 3 pieces each on a grid board. Contestants write Python
strategies (initialization + per-turn actions) to compete.

## Project Structure

```
docs/
├── rules/              # Game rules, API docs, ranking rules (zh/en bilingual)
│   ├── api.zh.md / api.en.md
│   ├── game.zh.md / game.en.md
│   └── rank.zh.md / rank.en.md
└── reference/          # Additional reference materials (TBD)
```

## Key Conventions

- **Documentation**: All docs have both Chinese (`*.zh.md`) and English
  (`*.en.md`) versions. Update both when modifying.
- **Commit style**: Follow conventional commits with emoji prefix, e.g.,
  `:art: chore(format): ...`.
- **Language**: Code and comments in English; docs bilingual.
