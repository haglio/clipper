# clipper — Project-Specific Instructions

Shared rules are in the global `~/.claude/CLAUDE.md`. This file contains only clipper-specific overrides.

## Test commands

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Architecture

Clipper is a standalone PyQt6/OpenCV video clip editor, extracted from the fun_time project. Key relationships:

- **Config**: `clipper/config.py` reads `fun_time_config.json` from the sibling fun_time project for VLC prefill (HTTP ports, search roots). This is a read-only dependency; clipper never writes to fun_time's config.
- **Output dirs**: Clips export to `<suite-root>/videos/genau/clips/`, audio to `<suite-root>/videos/genau/audio/`. These are shared with fun_time's Genau listener.
- **Entry point**: `python -m clipper` -> `__main__.py` -> `app.py:main()` -> launcher dialog -> UI.
- **Launcher chain**: `Clipper.lnk` -> `wscript.exe` -> `launch_clipper.vbs` -> `python -m clipper`.
- **Shared scaffolding**: logging setup, exception hooks and `hidden_subprocess_kwargs` come from the sibling `../app_support`, which every app in this family installs editable — fix those there, not here. Install it with `--config-settings editable_mode=compat`; its README says why, and its `tests/test_install.py` goes red without it.

## Fetching RIFE

The frame interpolator the loop-fix pipeline defaults to is **not in the repo**.
A fresh checkout has no `tools/rife-ncnn-vulkan-20221029-windows/`; fetch it once:

```powershell
.\.venv\Scripts\python.exe tools\fetch_rife.py
```

That pulls upstream's 432 MB release, keeps the six files clipper uses (17 MB),
puts them where `clip_postprocess_transforms._find_rife_exe` looks, and deletes
the zip. The directory is git-ignored. `--require` additionally exits non-zero
unless the binary actually *runs*, which is what the merge gate uses.

Same shape as `player_core/vendor/libmpv-2.dll`, with one difference worth
knowing: player_core deliberately does *not* give CI its DLL, because fun_time's
hidden-desktop suite covers the real player. Clipper has no second suite, and
windows-latest is the only place a Windows PE can execute — so clipper's gate
does fetch it, and fails rather than skipping the four tests that drive the seam
bridge. Everywhere else those four skip; without the binary the postprocess falls
back to its geometric seam, which is also what happens in production.

## Communication rules

- **Answer questions before doing work.** When the user asks questions or raises concerns, respond to each one. Do not silently go off and do a batch of work instead of engaging with the conversation.
- **Don't assume the next step.** Wait for the user to confirm direction before starting work, especially after a check-in or review.

## Testing principles

- **Test through realistic inputs, not mocked internals.** When a function integrates multiple subsystems (HTTP fetch → XML parse → path resolution → filesystem lookup), at least one test must feed realistic data through the actual function with only the network/OS boundary mocked. A test that mocks `_detect_from_http` to return a finished result does not test `_detect_from_http`.
- **Test each resolution path independently.** If a function has a primary path and a fallback, write separate tests proving each path works — and that the fallback is only reached when the primary fails. Use `mock.assert_not_called()` to verify the fallback was not touched when the primary succeeds.
- **Mock at the boundary, not in the middle.** Patch the I/O functions (`_fetch_http_status`, `_fetch_playlist_xml`) and the external-state functions (`search_roots`), not the intermediate logic that stitches them together. If you mock the intermediate logic, you're testing your mocks, not your code.

## Repo-specific gotchas

- The test environment is the project `.venv`, not system Python or Conda.
- `clipper/config.py` has a hardcoded path to the fun_time project for config resolution. If fun_time moves, this path needs updating.
- `sessions/` and `raw_clips/` are at the project root (not inside `clipper/`). They are gitignored runtime data.

## Test fixtures must be fabricated, never copied from the real library

Every fixture value that stands in for library data — a video title, a filename,
a performer or studio name, prompt text — must be **invented**. Never paste a
real one out of the media library to make a test feel realistic.

This is not a style note. It is the single thing that has actually leaked private
data into these repos: an agent writing a test reached for a real filename or
performer name because it was handy, and it rode into a public commit. Nothing in
the app's *design* pulls library text into source — the library lives outside
every repo, read at runtime through the git-ignored overlays — so this habit is
the only remaining path for a real name to get committed, and the only thing
stopping it is you following this rule.

Do not lean on the sanitize guard to catch it. `tools/sanitize_guard.py` fails
the suite when a **known** blocked term appears in the tracked tree, but a brand-
new performer name it has never seen passes every check and lands. The guard is a
backstop for names already known; it cannot see the next one.

So fabricate fully. Use `Jane Doe`, `Example Studio`, `scene one`, the
`alpha`/`beta`/`gamma` act placeholders the committed `content.example.json`
already uses. The near miss that still counts: taking a real filename and
changing a character or two — it is still that clip, still that performer. Make
it up from scratch, don't lightly edit a real one.

## Landing — GitHub merge queue, not local ff-merge

This repo is public at `github.com/haglio/clipper` with a merge-queue ruleset on
`main`, so the global "ff-merge into the primary checkout under
`.git/agent-merge.lock`" flow does NOT apply here:

- **Land through a pull request.** From your worktree: commit, `git fetch origin
  && git rebase origin/main`, `git push -u origin <branch>`, then
  `gh pr create --fill`. Auto-merge arms itself; the queue rebases your PR onto
  `main`, runs the required check, and merges it when green. Don't ff-merge into
  the primary checkout, don't push `main` directly, and never force-push `main`.
- **The `.git/agent-merge.lock` is retired here** — the GitHub queue serializes.
- **Sync local checkouts by pulling.** `main` advances only on origin (via the
  queue), so the primary checkout and worktrees update with
  `git pull --ff-only origin main`; the running app self-updates the same way.
  The primary is only ever fast-forwarded — never reset or merged-into.
- **A red required check** (`.github/workflows/merge-gate.yml`) can't land.

Everything else in the global CLAUDE.md — work in a worktree, green tests before
you push, clean handoff — still applies.
