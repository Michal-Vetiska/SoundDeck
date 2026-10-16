"""Single-producer, single-consumer ring buffer for microphone frames.

The input callback writes. The output callback reads. A short lock covers only
the copy of one block. Both sides use memory that already exists.
"""

from __future__ import annotations

import threading

import numpy as np

from soundboard.audio.formats import DTYPE


class RingBuffer:
    """Interleaved-frame circular buffer of shape ``(capacity, channels)``."""

    def __init__(self, capacity: int, channels: int) -> None:
        if capacity < 1:
            raise ValueError("Ring buffer capacity must be positive.")
        if channels < 1:
            raise ValueError("Ring buffer needs at least one channel.")
        self.capacity = capacity
        self.channels = channels
        self._data = np.zeros((capacity, channels), dtype=DTYPE)
        self._write = 0
        self._size = 0
        self._lock = threading.Lock()

    def available(self) -> int:
        """Frames waiting to be read."""
        with self._lock:
            return self._size

    def write(self, frames: np.ndarray) -> None:
        """Copy ``frames`` into the buffer.

        If the write does not fit, the oldest frames are dropped. A write
        larger than the whole buffer keeps only its tail.
        """
        if frames.size == 0:
            return
        incoming = frames
        if incoming.ndim != 2 or incoming.shape[1] != self.channels:
            raise ValueError("Unexpected frame shape for the ring buffer.")
        with self._lock:
            count = int(incoming.shape[0])
            if count >= self.capacity:
                incoming = incoming[-self.capacity :]
                count = self.capacity
                self._write = 0
                self._size = 0
            overflow = self._size + count - self.capacity
            if overflow > 0:
                self._size -= overflow
            index = self._write
            end = index + count
            if end <= self.capacity:
                self._data[index:end] = incoming
            else:
                first = self.capacity - index
                self._data[index:] = incoming[:first]
                self._data[: count - first] = incoming[first:]
            self._write = (index + count) % self.capacity
            self._size += count

    def read(self, count: int, out: np.ndarray) -> int:
        """Copy up to ``count`` frames into ``out`` and pad the rest with silence.

        Returns how many real frames were available.
        """
        if count < 0:
            raise ValueError("Frame count cannot be negative.")
        with self._lock:
            have = self._size if self._size < count else count
            if have:
                read_index = (self._write - self._size) % self.capacity
                end = read_index + have
                if end <= self.capacity:
                    out[:have] = self._data[read_index:end]
                else:
                    first = self.capacity - read_index
                    out[:first] = self._data[read_index:]
                    out[first:have] = self._data[: have - first]
                self._size -= have
            if have < count:
                out[have:count] = 0
            return have
