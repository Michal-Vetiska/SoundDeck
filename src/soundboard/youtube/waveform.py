"""Seam for a future waveform view.

The first version edits a clip with sliders and timestamps. A later editor
can implement :class:`WaveformProvider` without changing the download pipeline.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class WaveformProvider(Protocol):
    """Build peak buckets for a PCM buffer."""

    def peaks(self, samples: np.ndarray, buckets: int) -> np.ndarray | None:
        """Return ``buckets`` peak values, or None when no waveform is drawn."""


class NullWaveformProvider:
    """The v1 provider. The dialog keeps the slider timeline."""

    def peaks(self, samples: np.ndarray, buckets: int) -> np.ndarray | None:
        return None
