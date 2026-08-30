"""The similarity walk behind the suggested in and out points."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from .frame_store import signature_for_index, structural_similarity_score

if TYPE_CHECKING:
    from .state import VideoState


@dataclass(frozen=True)
class SimilarityDip:
    """Where the similarity curve falls away, and what the walk needs after it.

    These six traveled as a positional tuple, unpacked by position at both
    call sites -- one of which discarded four of them under underscore names.
    Which end of `candidates` is nearest the reference is the thing backlog
    bug 14 got wrong, so connascence of position across this boundary is not a
    theoretical worry.
    """

    candidates: list[int]
    smoothed: np.ndarray
    dip_idx: int
    baseline: float
    slope: np.ndarray
    run: int


def smooth_1d(values: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0 or len(values) == 0:
        return values.copy()
    kernel = np.ones(radius * 2 + 1, dtype=np.float64)
    kernel /= kernel.sum()
    padded = np.pad(values, (radius, radius), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def candidate_similarity_curve(
    state: VideoState,
    ref_idx: int,
    *,
    direction: int,
) -> tuple[list[int], np.ndarray] | None:
    min_gap = 10
    # Both directions run outwards from the reference, so index 0 is always its
    # nearest candidate. The dip and peak walks below skip a fixed head of this
    # list and take their baseline from it; when the backward list ran the other
    # way, that head was the far end of the loaded range instead.
    if direction > 0:
        candidates = list(range(ref_idx + min_gap, state.loaded_end + 1))
    else:
        candidates = list(range(ref_idx - min_gap, state.loaded_start - 1, -1))
    if not candidates:
        return None

    ref_signature = signature_for_index(state, ref_idx)
    scores = np.asarray(
        [structural_similarity_score(ref_signature, signature_for_index(state, idx)) for idx in candidates],
        dtype=np.float64,
    )
    if len(scores) < 5:
        return None

    smooth_radius = max(1, int(round(state.fps * 0.03)))
    smoothed = smooth_1d(scores, smooth_radius)
    return candidates, smoothed


def find_similarity_dip(
    state: VideoState,
    ref_idx: int,
    *,
    direction: int,
) -> SimilarityDip | None:
    curve = candidate_similarity_curve(state, ref_idx, direction=direction)
    if curve is None:
        return None
    candidates, smoothed = curve
    skip = min(len(smoothed) - 1, max(1, int(round(state.fps * 0.12))))
    baseline_end = min(len(smoothed), max(skip + 1, int(round(state.fps * 0.18))))
    baseline = float(np.max(smoothed[:baseline_end]))
    slope = np.diff(smoothed)
    run = max(2, int(round(state.fps * 0.05)))
    dip_idx: int | None = None

    for i in range(max(skip + run, run), len(smoothed) - run - 1):
        if baseline - smoothed[i] < 0.02:
            continue
        pre = float(np.mean(slope[i - run:i]))
        post = float(np.mean(slope[i:i + run]))
        if pre < -0.0005 and post > 0.0005:
            dip_idx = i
            break

    if dip_idx is None:
        return None
    return SimilarityDip(candidates, smoothed, dip_idx, baseline, slope, run)


def best_duplicate_match_index(
    state: VideoState,
    ref_idx: int,
    *,
    direction: int,
) -> int | None:
    dip = find_similarity_dip(state, ref_idx, direction=direction)
    if dip is None:
        return None
    smoothed, dip_idx, run = dip.smoothed, dip.dip_idx, dip.run

    peak_idx: int | None = None
    min_rebound = max(0.004, (dip.baseline - smoothed[dip_idx]) * 0.10)
    for i in range(dip_idx + run + 1, len(smoothed) - run - 1):
        rebound = smoothed[i] - smoothed[dip_idx]
        if rebound < min_rebound:
            continue
        pre = float(np.mean(dip.slope[i - run:i]))
        post = float(np.mean(dip.slope[i:i + run]))
        if pre > 0.0002 and post < -0.0002:
            peak_idx = i
            break

    if peak_idx is None:
        return None

    viable = np.where(smoothed[dip_idx + 1:] >= (smoothed[dip_idx] + min_rebound))[0]
    if len(viable) == 0:
        return None
    lo = dip_idx + 1 + int(viable[0])
    ref_signature = signature_for_index(state, ref_idx)
    raw_scores = np.asarray(
        [structural_similarity_score(ref_signature, signature_for_index(state, idx))
         for idx in dip.candidates],
        dtype=np.float64,
    )
    refined = lo + int(np.argmax(raw_scores[lo:]))
    return dip.candidates[refined]


def best_turning_point_index(
    state: VideoState,
    ref_idx: int,
    *,
    direction: int,
) -> int | None:
    dip = find_similarity_dip(state, ref_idx, direction=direction)
    if dip is None:
        return None
    return dip.candidates[dip.dip_idx]


def pair_transition_score(
    state: VideoState,
    active_start: int,
    active_end: int,
) -> float:
    scores: list[float] = []
    if active_end + 1 <= state.loaded_end:
        scores.append(
            structural_similarity_score(
                signature_for_index(state, active_start),
                signature_for_index(state, active_end + 1),
            )
        )
    if active_start - 1 >= state.loaded_start:
        scores.append(
            structural_similarity_score(
                signature_for_index(state, active_start - 1),
                signature_for_index(state, active_end),
            )
        )
    if not scores:
        return float("-inf")
    return float(sum(scores) / len(scores))
