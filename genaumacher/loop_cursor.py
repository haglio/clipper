"""Where the loop preview has got to, and how fast it is running."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoopCursor:
    """Owns the pause pair and the anchor the running position is read from.

    `paused_pos` and `paused_idx` are one fact in two spellings -- a position in
    the preview sequence and the frame at it -- and they were kept in step by
    hand at six call sites.  Takes the clock as an argument rather than reading
    one, so the arithmetic can be checked without patching time.
    """

    anchor: float
    speed: float = 1.0
    paused: bool = False
    paused_idx: int | None = None
    paused_pos: int | None = None

    def frame_in(self, sequence: list[int], fps: float, now: float) -> int:
        """Which frame of `sequence` the preview is on, remembered as it goes."""
        count = len(sequence)
        if count == 1:
            return self._settle(sequence, 0)
        if self.paused:
            return self._settle(sequence, self._resting_pos(sequence, count))
        elapsed = now - self.anchor
        return self._settle(sequence, int(elapsed * fps * self.speed) % count)

    def toggle_pause(self, sequence: list[int], fps: float, now: float) -> None:
        """Hold the preview where it is, or set it running from there."""
        frame = self.frame_in(sequence, fps, now)
        pos = self.paused_pos if self.paused_pos is not None else 0
        if self.paused:
            self.paused = False
            self.paused_idx = None
            self.paused_pos = None
            self.anchor = now - (pos / max(1e-9, fps * self.speed))
        else:
            self.paused = True
            self.paused_idx = frame
            self.paused_pos = pos

    def change_speed(self, delta: float, sequence: list[int], fps: float, now: float) -> bool:
        """Nudge the speed, re-anchored so the preview does not jump.

        Returns whether it moved -- at either end of the range it does not, and
        the caller has nothing to save.
        """
        was = self.speed
        self.frame_in(sequence, fps, now)
        speed = max(0.25, min(2.0, round((self.speed + delta) * 4) / 4))
        if speed == was:
            return False
        pos = self.paused_pos if self.paused_pos is not None else 0
        self.speed = speed
        self.anchor = now - (pos / max(1e-9, fps * self.speed))
        if not self.paused:
            self.paused_idx = None
            self.paused_pos = None
        return True

    def restart_at(self, when: float) -> None:
        """Send the preview back to the top of the sequence."""
        self.anchor = when

    def _resting_pos(self, sequence: list[int], count: int) -> int:
        pos = self.paused_pos
        if pos is None:
            frame = self.paused_idx if self.paused_idx is not None else sequence[0]
            pos = sequence.index(frame) if frame in sequence else 0
        return max(0, min(count - 1, pos))

    def _settle(self, sequence: list[int], pos: int) -> int:
        self.paused_pos = pos
        self.paused_idx = sequence[pos]
        return self.paused_idx
