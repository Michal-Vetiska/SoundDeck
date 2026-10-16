"""Audio device enumeration.

``sounddevice`` is imported inside :func:`list_devices` so unit tests of the
pure helpers do not need a working PortAudio device.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioDevice:
    """One PortAudio device, reduced to the fields the UI needs."""

    index: int
    name: str
    input_channels: int
    output_channels: int
    default_samplerate: float

    @property
    def is_input(self) -> bool:
        return self.input_channels > 0

    @property
    def is_output(self) -> bool:
        return self.output_channels > 0


@dataclass(frozen=True)
class DeviceSnapshot:
    """Devices observed during one refresh."""

    inputs: tuple[AudioDevice, ...]
    outputs: tuple[AudioDevice, ...]
    virtual_output: AudioDevice | None
    error: str | None = None


def list_devices() -> list[AudioDevice]:
    """Query PortAudio. An empty list means the query failed or nothing is present."""
    try:
        import sounddevice as sd
    except Exception as exc:
        logger.exception("Could not import sounddevice")
        raise RuntimeError("The audio library could not be loaded.") from exc

    try:
        raw_devices = sd.query_devices()
    except Exception:
        logger.exception("Could not query audio devices")
        return []

    devices: list[AudioDevice] = []
    for index, raw in enumerate(raw_devices):
        devices.append(
            AudioDevice(
                index=index,
                name=str(raw["name"]),
                input_channels=int(raw["max_input_channels"]),
                output_channels=int(raw["max_output_channels"]),
                default_samplerate=float(raw["default_samplerate"]),
            )
        )
    logger.info("Found %s audio devices", len(devices))
    return devices


def input_devices(devices: list[AudioDevice]) -> list[AudioDevice]:
    return [device for device in devices if device.is_input]


def output_devices(devices: list[AudioDevice]) -> list[AudioDevice]:
    return [device for device in devices if device.is_output]


def display_name(device: AudioDevice, devices: list[AudioDevice]) -> str:
    """Disambiguate two devices that share a name by appending the index."""
    duplicates = any(
        other.name == device.name and other.index != device.index for other in devices
    )
    if duplicates:
        return f"{device.name} ({device.index})"
    return device.name


def find_by_hints(
    devices: list[AudioDevice],
    hints: tuple[str, ...] | list[str],
    *,
    output: bool,
) -> AudioDevice | None:
    """Return the first device whose name contains a hint, in hint order."""
    pool = output_devices(devices) if output else input_devices(devices)
    for hint in hints:
        needle = hint.lower()
        for device in pool:
            if needle in device.name.lower():
                return device
    return None


def resolve_device(
    devices: list[AudioDevice],
    label: str | None,
    *,
    want_input: bool,
) -> AudioDevice | None:
    """Match a saved label back to a live device."""
    if not label:
        return None
    pool = input_devices(devices) if want_input else output_devices(devices)
    for device in pool:
        if display_name(device, devices) == label or device.name == label:
            return device
    for device in pool:
        if label == f"{device.name} ({device.index})":
            return device
    return None


def snapshot_devices(hints: tuple[str, ...]) -> DeviceSnapshot:
    """Build the snapshot the settings window renders."""
    try:
        devices = list_devices()
    except RuntimeError as exc:
        return DeviceSnapshot((), (), None, str(exc))
    return DeviceSnapshot(
        inputs=tuple(input_devices(devices)),
        outputs=tuple(output_devices(devices)),
        virtual_output=find_by_hints(devices, hints, output=True),
    )
