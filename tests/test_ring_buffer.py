"""Ring buffer overflow, wrap, and underrun."""

from __future__ import annotations

import numpy as np

from soundboard.audio.ring_buffer import RingBuffer


def test_read_returns_written_frames_and_pads_silence() -> None:
    ring = RingBuffer(8, 2)
    frames = np.arange(6, dtype=np.float32).reshape(3, 2)
    ring.write(frames)
    out = np.ones((4, 2), dtype=np.float32)
    got = ring.read(4, out)
    assert got == 3
    assert np.allclose(out[:3], frames)
    assert np.all(out[3] == 0)


def test_overflow_drops_the_oldest_frames() -> None:
    ring = RingBuffer(4, 2)
    first = np.ones((3, 2), dtype=np.float32)
    second = np.full((3, 2), 2, dtype=np.float32)
    ring.write(first)
    ring.write(second)
    out = np.zeros((4, 2), dtype=np.float32)
    got = ring.read(4, out)
    assert got == 4
    assert np.allclose(out[0], 1)
    assert np.allclose(out[1:], 2)
