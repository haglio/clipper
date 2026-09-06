"""What the timeline and the legend paint with: purpose names over the family's
hues and tiers.

These lived in ``shared_ui.colors`` under a section headed with this app's
name, where clipper was the one app reading them; a shared palette's job is the
hue and the tier ladder, and an app's mapping of "loop frame" onto red belongs
beside the widget that draws it.  Every one is an alias, so the timeline stays
on the family's colors and nothing here can drift a shade away from them.
"""

from __future__ import annotations

from shared_ui.colors import (
    AMBER,
    BLUE,
    BLUE_LIGHT,
    BORDER_DEFAULT,
    GREEN,
    RED,
    TEXT_MUTED,
    TEXT_SECONDARY,
    WHITE,
)

# The legend's two tiers are the body tiers: a label reads as body text and the
# " or " between items reads as muted.
TEXT_LEGEND_LABEL = TEXT_SECONDARY
TEXT_LEGEND_JOIN = TEXT_MUTED

# A timeline's outline and its ticks are the standard border.
BORDER_TIMELINE = BORDER_DEFAULT
BORDER_TICK = BORDER_DEFAULT

# There is one blue in the family: the loaded range is it, and the range in
# play is it tinted lighter.
TIMELINE_LOADED = BLUE
TIMELINE_ACTIVE = BLUE_LIGHT
TIMELINE_CURSOR = WHITE
TIMELINE_LOOP = RED
# The two suggested points are marks that can land on either range, so each is
# a hue neither range wears.
TIMELINE_SUGGESTED_IN = AMBER
TIMELINE_SUGGESTED_OUT = GREEN
