"""Internal audio format.

Every sound is converted to this format before it can be played. The realtime
callback never resamples and never decodes compressed files.
"""

from __future__ import annotations

import numpy as np

SAMPLE_RATE = 48_000
CHANNELS = 2
DTYPE = np.float32
BLOCK_SIZE = 512
MAX_BLOCK_SIZE = 2048
# About 250 ms of stereo audio. Absorbs clock drift between two devices.
RING_CAPACITY_FRAMES = SAMPLE_RATE // 4
FADE_FRAMES = 64
