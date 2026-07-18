# clipper — Project-Specific Instructions

Shared rules are in the global `~/.claude/CLAUDE.md`. This file contains only clipper-specific overrides.

## Test commands

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Architecture

Clipper is a standalone Pygame/OpenCV video clip editor, extracted from the fun_time project. Key relationships:

- **Config**: `clipper/config.py` reads `fun_time_config.json` from the sibling fun_time project for VLC prefill (HTTP ports, search roots). This is a read-only dependency; clipper never writes to fun_time's config.
- **Output dirs**: Clips export to `C:/path/to/suite-root/videos/genau/clips/`, audio to `C:/path/to/suite-root/videos/genau/audio/`. These are shared with fun_time's Genau listener.
- **Entry point**: `python -m clipper` -> `__main__.py` -> `app.py:main()` -> launcher dialog -> UI.
- **Launcher chain**: `Clipper.lnk` -> `wscript.exe` -> `launch_clipper.vbs` -> `python -m clipper`.
- **Shared scaffolding**: logging setup, exception hooks and `hidden_subprocess_kwargs` come from the sibling `../app_support`, which every app in this family installs editable — fix those there, not here. Install it with `--config-settings editable_mode=compat`; its README says why, and its `tests/test_install.py` goes red without it.

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
