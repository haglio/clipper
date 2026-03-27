# Agent Working Notes

Read this file before making changes in this repo.

## Mandatory Preflight

1. Confirm the repo is clean enough to work in:
   `git status --short`
2. Run the full test suite before and after substantive changes.

Preferred command in this Windows repo:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Change Workflow

1. Start with tests.
   When fixing regressions or changing behavior, add or update characterization coverage first so the failure is visible in the suite before changing production code.
2. Use a red-green-refactor loop.
   Make the test fail for the right reason, implement the smallest targeted fix to get green, then refactor against the green suite to keep the codebase cleaner than you found it.
3. Aim for solid regression coverage, not minimal box-checking.
   Prefer tests that lock down the user-visible contract or module seam that actually broke, especially around export pipeline, session persistence, and VLC prefill behavior.
4. Run the full suite after substantive changes:
   `.\.venv\Scripts\python.exe -m pytest`
5. Keep commits small and single-purpose.
   Independent fixes or refactors should land as separate commits so they are easy to review, reason about, and revert. Commit after each logical step — do not accumulate an entire session of changes into one giant commit.
6. Clean dead code as you go.
   When a refactor makes code unreachable — unused globals, orphaned functions, stale constants, obsolete imports — delete it in the same pass. Do not leave dead code behind for a future cleanup. After each extraction or simplification, actively search for newly-dead references (grep for the thing you just stopped calling) and remove them. This applies to tests too: update or delete contract tests whose assertions describe the old architecture.
7. Leave a clean handoff.
   Before finishing, make sure the worktree is clean, the tests are green, temporary exploration artifacts are removed, and the repo is in a good state for the next feature or fix. Explain what you think the best next step is — what's now unblocked, what's the highest-leverage remaining work, and whether the project is ready to return to feature work or still needs structural cleanup.

## Architecture

Clipper is a standalone Pygame/OpenCV video clip editor, extracted from the fun_time project. Key relationships:

- **Config**: `clipper/config.py` reads `fun_time_config.json` from the sibling fun_time project for VLC prefill (HTTP ports, search roots). This is a read-only dependency; clipper never writes to fun_time's config.
- **Output dirs**: Clips export to `C:/path/to/suite-root/videos/robot_hand/clips/`, audio to `C:/path/to/suite-root/videos/robot_hand/audio/`. These are shared with fun_time's Robot Hand listener.
- **Entry point**: `python -m clipper` → `__main__.py` → `app.py:main()` → launcher dialog → UI.
- **Launcher chain**: `Clipper.lnk` → `wscript.exe` → `launch_clipper.vbs` → `python -m clipper`.

## Current Repo-Specific Gotchas

- The canonical test environment is the project `.venv`, not the system Python or Conda Python.
- `clipper/config.py` has a hardcoded path to the fun_time project for config resolution. If fun_time moves, this path needs updating.
- `sessions/` and `raw_clips/` are at the project root (not inside `clipper/`). They are gitignored runtime data.
