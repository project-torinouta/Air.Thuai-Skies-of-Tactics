---
name: release
description: 'Create a GitHub release with nix-built artifacts (zip + PDFs). Use when: (1)
  User says "/release", "create release", "cut release", "release version X.Y.Z";
  (2) User wants to tag and publish a new version; (3) User asks for an emergency
  hotfix release'
---

# Release

When the user invokes this skill, create a tagged GitHub release with build
artifacts via the nix build system.

## Steps

### 1. Determine Version

Read `src/pyproject.toml` for the current version. Match the tag and release
to that version. For hotfixes, append `-hotfix` (e.g., `v0.1.2-hotfix`).

Also check `changelog/` for existing version markers to understand the release
history and naming convention.

```bash
grep version src/pyproject.toml
```

```bash
ls changelog/
```

```bash
git tag -l 'v*'
```

### 2. Verify Working Tree

```bash
git status
```

Warn the user if there are uncommitted changes — they should commit or stash
before releasing. If the working tree is clean, proceed.

### 3. Build Artifacts with Nix

```bash
nix run .#clean
nix run .#build
nix run .#documents
```

Verify the outputs in `build/`:

```bash
ls -lh build/
```

### 4. Rename the Zip

`nightly-latest.zip` is the generic CI name. For a versioned release, rename
it to match the version tag:

```bash
mv build/nightly-latest.zip build/v<VERSION>.zip
```

(Only the zip gets renamed — the PDFs keep their original names.)

### 5. Create and Push Tag

```bash
git tag -a v<VERSION> -m "v<VERSION> — <description>"
git push origin v<VERSION>
```

### 6. Create GitHub Release

Upload the versioned zip and all PDFs:

```bash
gh release create v<VERSION> \
  --title "v<VERSION> — <description>" \
  --notes "<release notes>" \
  'build/v<VERSION>.zip' \
  'build/aggressive.pdf' \
  'build/defensive.pdf' \
  'build/mcts.pdf' \
  'build/alpha_beta.pdf' \
  'build/tactical.pdf' \
  'build/warrior.pdf' \
  'build/sniper.pdf'
```

### 7. Report Back

Report to the user with the release URL.

## Important Notes

- **Always use `nix run #.build` and `nix run #.documents`** — never ad-hoc
  `zip` or `typst compile` commands.
- **Zip renaming**: Only `nightly-latest.zip` → `v<VERSION>.zip`. PDFs stay
  as `build/*.pdf`, never rename them.
- If the tag already exists, delete and recreate it:
  `gh release delete v<VERSION> -y && git tag -d v<VERSION> && git push --delete origin v<VERSION>`
- Write release notes that summarise commits since the last tag:
  `git log --oneline <last-tag>..HEAD`
