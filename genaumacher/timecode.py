"""Seconds to and from the hh:mm:ss.sss the user types and the labels show."""

from __future__ import annotations


def parse_timestamp(ts: str) -> float:
    parts = ts.strip().split(":")
    if len(parts) != 3:
        raise ValueError("Timestamp must be hh:mm:ss or hh:mm:ss.sss")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def format_seconds(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{remaining:06.3f}"
