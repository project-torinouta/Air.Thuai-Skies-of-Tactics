---
name: create-pr
description:
  'Create a GitHub Pull Request using the project template. Use when: (1) User
  says "/create-pr" or "create a PR", (2) User wants to submit changes for
  review, (3) User asks to open/push a PR for the current branch, (4) User wants
  to publish their branch as a PR following the repo convention'
---

# Create PR

When the user invokes this skill, create a pull request for the current branch.

## Steps

### 1. Gather Context

Run the following commands in parallel to understand the current state:

```bash
git status
```

```bash
git diff
```

```bash
git log --oneline -10
```

```bash
git diff origin/main...HEAD --stat
```

```bash
gh pr view --json title,body,state 2>/dev/null || echo "No existing PR found"
```

Check if the branch tracks a remote. If it doesn't, determine the branch name
and plan to push with `-u`.

### 2. Read the PR Template

Read the PR template at `.github/PULL_REQUEST_TEMPLATE.md` to understand the
required format. Also check the commit format convention from memory/CLAUDE.md.

### 3. Analyze Changes

From the gathered context, determine:

- **Type of Change**: Match the changes to the PR template categories (`feat`,
  `fix`, `docs`, `style`, `refactor`, `test`, `chore`)
- **Directories Affected**: Which top-level directory (`docs/`, `.github/`, etc.) is affected
- **Files Changed**: List the files
- **Summary**: 1-3 bullet points describing what the PR does and why

### 4. Prepare PR Body

Fill in the PR template from `.github/PULL_REQUEST_TEMPLATE.md`. Use this
format:

- **Title**: Follow the commit message convention:
  `emoji: type(scope): short description`
- **Body**: The full template with all relevant sections filled in

### 5. Push and Create

```bash
# Push the current branch to remote with upstream tracking
git push -u origin HEAD

# Create the PR
gh pr create --title "TITLE" --body "BODY"
```

Use `gh pr create` with the `--title` and `--body` flags. Pass the body via
heredoc.

### After Creation

Report back to the user with:

- The PR URL (from `gh pr create` output)
- A brief summary of what was included

## Important Notes

- Do NOT commit changes — the user should already have committed before invoking
  this skill
- If there are uncommitted changes, warn the user and ask if they want to
  include them or commit first
- If the branch already has an open PR, ask the user if they want to update it
  (use `gh pr edit <number> --title "..." --body "..."`)
- Follow the commit message format from the project conventions
