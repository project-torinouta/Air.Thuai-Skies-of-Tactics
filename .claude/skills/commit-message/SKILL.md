---
name: commit-message
description: >
  Generate a git commit message using the project convention (gitmoji + conventional
  commits). Use when: (1) User asks "write a commit message", "generate a commit
  message", or "commit this", (2) User explicitly invokes "/commit-message".
---

# Commit Message Convention

When asked to generate a commit message, follow the format:

```
:emoji: type(scope): short description
```

- **emoji**: A single gitmoji that matches the commit type (see table below).
- **type**: One of `feat`, `fix`, `chore`, `refactor`, `docs`, `style`, `test`,
  `perf`, `ci`, `build`, `revert`.
- **scope** (optional): The module or area the change affects (e.g. `sdk`,
  `strategies`, `license`, `gitignore`, `format`, `type`).
- **description**: Imperative present tense, no period, max ~72 chars.

The subject line is the full commit message. No body is written unless the
change requires explanation beyond the subject line.

## Emoji → Type Mapping

| Emoji                | Type              | When to use                             |
| -------------------- | ----------------- | --------------------------------------- |
| `:tada:`             | `feat`            | Initial project / major start           |
| `:package:`          | `feat`            | New feature or dependency               |
| `:sparkles:`         | `feat`            | Minor new feature                       |
| `:snowflake:`        | `fix`             | Bug fix                                 |
| `:recycle:`          | `refactor`        | Code restructuring, no behaviour change |
| `:art:`              | `style` / `chore` | Formatting, lint, whitespace            |
| `:page_facing_up:`   | `chore`           | License, legal headers                  |
| `:see_no_evil:`      | `chore`           | gitignore                               |
| `:e-mail:`           | `chore`           | Email, contact info                     |
| `:memo:`             | `docs`            | Documentation only                      |
| `:white_check_mark:` | `test`            | Adding or updating tests                |
| `:zap:`              | `perf`            | Performance improvement                 |
| `:green_heart:`      | `ci`              | CI / build system                       |
| `:rewind:`           | `revert`          | Reverting a previous change             |

## Examples from this project

```
:tada: feat(init): use uv as python management toolkit and init the project
:package: feat(sdk): download and translate the SDK package from saiblo
:snowflake: fix(nix): fix nix syntax error
:recycle: refactor(strategies): refactor the strategy factory functions to single-file under strategies folder
:art: chore(format): set indent space as 4 for python files
:page_facing_up: chore(license): add MIT license
:see_no_evil: chore(gitignore): init gitignore for normal uv project
```
