"""Virtual-device matching without PortAudio."""

from __future__ import annotations

from soundboard.audio.devices import AudioDevice, display_name, find_by_hints, resolve_device


def _device(index: int, name: str, inputs: int, outputs: int) -> AudioDevice:
    return AudioDevice(index, name, inputs, outputs, 48000.0)


def test_blackhole_hint_prefers_the_specific_name() -> None:
    speakers = _device(0, "MacBook Speakers", 0, 2)
    blackhole = _device(1, "BlackHole 2ch", 0, 2)
    devices = [speakers, blackhole]
    found = find_by_hints(devices, ("BlackHole 2ch", "BlackHole"), output=True)
    assert found is blackhole


def test_resolve_display_name_and_duplicates() -> None:
    first = _device(1, "Microphone", 1, 0)
    second = _device(2, "Microphone", 2, 0)
    devices = [first, second]
    assert display_name(second, devices) == "Microphone (2)"
    assert resolve_device(devices, "Microphone (2)", want_input=True) is second
    assert resolve_device(devices, "Missing", want_input=True) is None
