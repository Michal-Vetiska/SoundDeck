"""Realtime audio engine.

Two PortAudio streams are required because the microphone and the virtual
output are different devices. The input callback only copies samples into a
ring buffer. The output callback mixes that microphone audio with sounds that
were decoded ahead of time.

Nothing in either callback touches disk, the network, FFmpeg, or the GUI.
Status for the UI is a snapshot the GUI thread reads.
"""

from __future__ import annotations

import logging
import queue
import time
from dataclasses import dataclass

import numpy as np

from soundboard.audio.devices import AudioDevice, list_devices, resolve_device
from soundboard.audio.formats import (
    BLOCK_SIZE,
    CHANNELS,
    DTYPE,
    FADE_FRAMES,
    MAX_BLOCK_SIZE,
    RING_CAPACITY_FRAMES,
    SAMPLE_RATE,
)
from soundboard.audio.mixer import PlaybackVoice, ensure_stereo_f32, mix_into, voice_ratio
from soundboard.audio.ring_buffer import RingBuffer
from soundboard.errors import AudioEngineError

logger = logging.getLogger(__name__)

Command = tuple[object, ...]


@dataclass(frozen=True)
class PlaybackState:
    """Progress of one sound, copied out for the UI thread."""

    sound_id: str
    playing: bool
    ratio: float


class AudioEngine:
    """Mix a microphone with preloaded sounds and write a virtual output.

    Local monitoring is a planned feature. :meth:`monitor_available` stays
    false so the UI can show the control as unavailable instead of faking it.
    """

    def __init__(self) -> None:
        self._ring = RingBuffer(RING_CAPACITY_FRAMES, CHANNELS)
        self._buffers: dict[str, np.ndarray] = {}
        self._volumes: dict[str, float] = {}
        self._voices: list[PlaybackVoice] = []
        self._commands: queue.SimpleQueue[Command] = queue.SimpleQueue()
        self._mic_volume = 1.0
        self._master_volume = 1.0
        self._mic = np.zeros((MAX_BLOCK_SIZE, CHANNELS), dtype=DTYPE)
        self._in_stereo = np.zeros((MAX_BLOCK_SIZE, CHANNELS), dtype=DTYPE)
        self._out = np.zeros((MAX_BLOCK_SIZE, CHANNELS), dtype=DTYPE)
        self._scratch = np.zeros((MAX_BLOCK_SIZE, CHANNELS), dtype=DTYPE)
        self._cube = np.zeros((MAX_BLOCK_SIZE, CHANNELS), dtype=DTYPE)
        self._input = None
        self._output = None
        self._running = False
        self._stopping = False
        self._primed = False
        self._fatal_message: str | None = None
        self._input_overflows = 0
        self._playback_snapshot: tuple[PlaybackState, ...] = ()
        self._tick = 0
        self._input_name: str | None = None
        self._output_name: str | None = None
        self._started_at = 0.0

    @property
    def running(self) -> bool:
        return self._running

    @property
    def input_name(self) -> str | None:
        return self._input_name

    @property
    def output_name(self) -> str | None:
        return self._output_name

    def monitor_available(self) -> bool:
        """Local monitoring is intentionally not active in this version."""
        return False

    def register_buffer(self, sound_id: str, samples: np.ndarray) -> None:
        """Make PCM available for playback.

        Before the stream starts this writes the table directly. While the
        stream is running the audio thread applies the change, so the
        callback never races a dictionary resize.
        """
        array = ensure_stereo_f32(samples)
        if self._running:
            self._commands.put(("register", sound_id, array))
        else:
            self._buffers[sound_id] = array

    def unload(self, sound_id: str) -> None:
        if self._running:
            self._commands.put(("unload", sound_id))
        else:
            self._buffers.pop(sound_id, None)
            self._volumes.pop(sound_id, None)
            self._voices = [voice for voice in self._voices if voice.sound_id != sound_id]

    def play(self, sound_id: str) -> None:
        self._commands.put(("play", sound_id))

    def stop_sound(self, sound_id: str) -> None:
        self._commands.put(("stop", sound_id))

    def set_sound_volume(self, sound_id: str, volume: float) -> None:
        value = float(volume)
        if self._running:
            self._commands.put(("volume", sound_id, value))
        else:
            self._volumes[sound_id] = value

    def set_mic_volume(self, volume: float) -> None:
        self._commands.put(("mic_volume", float(volume)))
        if not self._running:
            self._mic_volume = float(volume)

    def set_master_volume(self, volume: float) -> None:
        self._commands.put(("master_volume", float(volume)))
        if not self._running:
            self._master_volume = float(volume)

    def start(self, input_name: str | None, output_name: str | None) -> None:
        """Open the microphone and the virtual output."""
        self.stop()
        devices = list_devices()
        microphone = resolve_device(devices, input_name, want_input=True)
        output = resolve_device(devices, output_name, want_input=False)
        if microphone is None or output is None:
            raise AudioEngineError("Choose both a microphone and an output device.")
        if microphone.input_channels < 1:
            raise AudioEngineError("The selected microphone has no input channels.")
        if output.output_channels < 2:
            raise AudioEngineError("The output device needs two channels.")

        import sounddevice as sd

        input_channels = 1 if microphone.input_channels == 1 else 2
        self._stopping = False
        self._fatal_message = None
        self._primed = False
        self._process_commands()
        self._ring = RingBuffer(RING_CAPACITY_FRAMES, CHANNELS)
        try:
            self._input = sd.InputStream(
                device=microphone.index,
                channels=input_channels,
                samplerate=SAMPLE_RATE,
                dtype="float32",
                blocksize=BLOCK_SIZE,
                callback=self._input_callback,
                finished_callback=self._on_stream_finished,
                latency="low",
            )
            self._output = sd.OutputStream(
                device=output.index,
                channels=CHANNELS,
                samplerate=SAMPLE_RATE,
                dtype="float32",
                blocksize=BLOCK_SIZE,
                callback=self._output_callback,
                finished_callback=self._on_stream_finished,
                latency="low",
            )
            self._input.start()
            self._output.start()
        except Exception as exc:
            logger.exception("Failed to start audio streams")
            self.stop()
            raise AudioEngineError(self._device_error_message(exc, microphone, output)) from exc

        self._running = True
        self._started_at = time.monotonic()
        self._input_name = input_name
        self._output_name = output_name
        logger.info(
            "Audio engine started input=%s output=%s rate=%s",
            microphone.name,
            output.name,
            SAMPLE_RATE,
        )

    def stop(self) -> None:
        """Close both streams. Safe to call when already stopped."""
        self._stopping = True
        was_running = self._running
        self._running = False
        for stream, label in ((self._input, "input"), (self._output, "output")):
            if stream is None:
                continue
            try:
                stream.stop()
                stream.close()
            except Exception:
                logger.exception("Failed to close %s stream", label)
        self._input = None
        self._output = None
        self._primed = False
        if was_running:
            logger.info("Audio engine stopped")

    def restart(self, input_name: str | None, output_name: str | None) -> None:
        """Stop and start again with the given devices."""
        logger.info("Restarting audio engine")
        self.start(input_name, output_name)

    def poll_health(self) -> str | None:
        """Called on the UI thread. Returns an error message when the device dies."""
        if not self._running:
            return None
        if (
            self._fatal_message is None
            and time.monotonic() - self._started_at > 0.5
            and not self._streams_active()
        ):
            self._fatal_message = (
                "The audio device stopped. It may have been disconnected. "
                "Check the devices in Settings and restart the engine."
            )
        if not self._fatal_message:
            return None
        message = self._fatal_message
        self._fatal_message = None
        logger.error("Audio engine stopped after a device error: %s", message)
        self.stop()
        return message

    def _streams_active(self) -> bool:
        try:
            input_ok = self._input is not None and bool(self._input.active)
            output_ok = self._output is not None and bool(self._output.active)
        except Exception:
            return False
        return input_ok and output_ok

    def playback_snapshot(self) -> tuple[PlaybackState, ...]:
        """Latest progress written by the audio thread."""
        return self._playback_snapshot

    def _device_error_message(
        self,
        exc: Exception,
        microphone: AudioDevice,
        output: AudioDevice,
    ) -> str:
        text = str(exc).strip().splitlines()
        detail = text[0] if text else "The audio device rejected the stream."
        if len(detail) > 180:
            detail = detail[:179] + "…"
        return (
            f"Could not open {microphone.name} and {output.name}. {detail}"
        )

    def _on_stream_finished(self) -> None:
        # Audio thread. Do not log or stop the stream from here.
        if self._stopping or not self._running:
            return
        self._fatal_message = (
            "The audio device stopped. It may have been disconnected. "
            "Check the devices in Settings and restart the engine."
        )

    def _input_callback(self, indata, frames, _time_info, status) -> None:
        if frames > MAX_BLOCK_SIZE:
            self._fatal_message = "The microphone sent an unexpected block size."
            return
        if status:
            # Overflow is not fatal. Count it without doing I/O.
            self._input_overflows += 1
        try:
            view = self._in_stereo[:frames]
            if indata.shape[1] == 1:
                view[:, 0] = indata[:, 0]
                view[:, 1] = indata[:, 0]
            else:
                view[:, 0] = indata[:, 0]
                view[:, 1] = indata[:, 1]
            self._ring.write(view)
        except Exception:
            self._fatal_message = "Microphone capture failed."

    def _output_callback(self, outdata, frames, _time_info, status) -> None:
        if frames > MAX_BLOCK_SIZE:
            outdata.fill(0)
            self._fatal_message = "The output device requested an unexpected block size."
            return
        try:
            self._process_commands()
            if not self._primed and self._ring.available() < BLOCK_SIZE:
                outdata.fill(0)
                return
            self._primed = True
            self._ring.read(frames, self._mic[:frames])
            mix_into(
                self._mic[:frames],
                self._voices,
                self._mic_volume,
                self._master_volume,
                self._out[:frames],
                self._scratch[:frames],
                self._cube[:frames],
            )
            channel_count = outdata.shape[1]
            outdata[:, :channel_count] = self._out[:frames, :channel_count]
            self._publish_playback()
        except Exception:
            outdata.fill(0)
            self._fatal_message = "The mixer failed and the engine stopped."

    def _process_commands(self) -> None:
        for _ in range(32):
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            self._handle_command(command)

    def _handle_command(self, command: Command) -> None:
        kind = command[0]
        if kind == "register":
            self._buffers[str(command[1])] = command[2]  # type: ignore[assignment]
        elif kind == "unload":
            sound_id = str(command[1])
            self._buffers.pop(sound_id, None)
            self._volumes.pop(sound_id, None)
            self._voices = [voice for voice in self._voices if voice.sound_id != sound_id]
        elif kind == "play":
            self._start_voice(str(command[1]))
        elif kind == "stop":
            self._fade_out(str(command[1]))
        elif kind == "volume":
            sound_id = str(command[1])
            volume = float(command[2])
            self._volumes[sound_id] = volume
            for voice in self._voices:
                if voice.sound_id == sound_id:
                    voice.volume = volume
        elif kind == "mic_volume":
            self._mic_volume = float(command[1])
        elif kind == "master_volume":
            self._master_volume = float(command[1])

    def _start_voice(self, sound_id: str) -> None:
        samples = self._buffers.get(sound_id)
        if samples is None or samples.shape[0] == 0:
            return
        volume = self._volumes.get(sound_id, 1.0)
        for voice in self._voices:
            if voice.sound_id == sound_id:
                voice.samples = samples
                voice.position = 0
                voice.volume = volume
                voice.active = True
                voice.fade_in = min(FADE_FRAMES, int(samples.shape[0]))
                voice.fading_out = False
                voice.fade_out_left = 0
                return
        self._voices.append(
            PlaybackVoice(
                sound_id=sound_id,
                samples=samples,
                volume=volume,
                fade_in=min(FADE_FRAMES, int(samples.shape[0])),
            )
        )

    def _fade_out(self, sound_id: str) -> None:
        for voice in self._voices:
            if voice.sound_id == sound_id and voice.active and not voice.fading_out:
                voice.fading_out = True
                voice.fade_out_left = min(FADE_FRAMES, int(voice.samples.shape[0] - voice.position))
                if voice.fade_out_left <= 0:
                    voice.active = False

    def _publish_playback(self) -> None:
        self._tick += 1
        if self._tick % 4 != 0:
            return
        if self._tick % 32 == 0:
            self._voices = [voice for voice in self._voices if voice.active]
        self._playback_snapshot = tuple(
            PlaybackState(voice.sound_id, voice.active, voice_ratio(voice))
            for voice in self._voices
        )
