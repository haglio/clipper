# clipper — Project-Specific Instructions

Shared rules are in the global `~/.claude/CLAUDE.md`. This file contains only clipper-specific overrides.

## Test commands

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Architecture

Clipper is a standalone Pygame/OpenCV video clip editor, extracted from the fun_time project. Key relationships:

- **Config**: `clipper/config.py` reads `fun_time_config.json` from the sibling fun_time project for VLC prefill (HTTP ports, search roots). This is a read-only dependency; clipper never writes to fun_time's config.
- **Output dirs**: Clips export to `C:/path/to/suite-root/videos/robot_hand/clips/`, audio to `C:/path/to/suite-root/videos/robot_hand/audio/`. These are shared with fun_time's Robot Hand listener.
- **Entry point**: `python -m clipper` -> `__main__.py` -> `app.py:main()` -> launcher dialog -> UI.
- **Launcher chain**: `Clipper.lnk` -> `wscript.exe` -> `launch_clipper.vbs` -> `python -m clipper`.

## Communication rules

- **Answer questions before doing work.** When the user asks questions or raises concerns, respond to each one. Do not silently go off and do a batch of work instead of engaging with the conversation.
- **Don't assume the next step.** Wait for the user to confirm direction before starting work, especially after a check-in or review.

## Repo-specific gotchas

- The test environment is the project `.venv`, not system Python or Conda.
- `clipper/config.py` has a hardcoded path to the fun_time project for config resolution. If fun_time moves, this path needs updating.
- `sessions/` and `raw_clips/` are at the project root (not inside `clipper/`). They are gitignored runtime data.
