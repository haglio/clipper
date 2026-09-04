"""Vulture whitelist -- false positives that are not dead code.

Each entry tells vulture the name is used, suppressing the report. vulture
matches by bare name, so tests/test_dead_code.py asserts every entry here still
answers a report, and an entry may only be added with the reason it answers one.
"""

# ruff: noqa: F821, B018 -- a whitelist is names, not statements
# --- Qt method overrides, called by the event loop, not by us ---
_.paintEvent  # legend_widget, main_window, timeline_widget, video_pane
_.closeEvent  # main_window
_.mousePressEvent  # timeline_widget

# --- Written by production code through setattr on dynamic state, read where vulture cannot follow ---
_._export_worker  # main_window
_.original_session_payload  # session_launch writes it; the discard-on-exit compares against it
_.last_saved_payload  # session_persistence and state_factory write it; a failed write leaves it, which is how the warning path proves the good copy survived
_.render_rev  # bumped by every edit that changes what is drawn; the edit tables read it to prove an edit happened

# --- Read from outside vulture's scan ---
RIFE_EXE  # tools/fetch_rife's statement of where the exe lands; tests/test_fetch_rife.py holds the app to it
