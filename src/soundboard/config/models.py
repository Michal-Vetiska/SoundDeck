"""Configuration models.

The JSON shape is versioned so a later SQLite storage can read the same
fields without the rest of the app knowing where they live.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def clamp_volume(value: object, default: float = 1.0) -> float:
    """Return a volume in the inclusive range 0..1."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number


@dataclass
class AudioSettings:
    """Selected devices and mix levels.

    Device fields store the display name, not a PortAudio index. Indexes
    change when devices are plugged in.
    """

    input_device: str | None = None
    output_device: str | None = None
    mic_volume: float = 1.0
    master_volume: float = 1.0


@dataclass
class SoundEntry:
    """One soundboard item persisted in config.

    ``file`` is relative to the application support directory, for example
    ``sounds/abc.f32``.
    """

    id: str
    name: str
    file: str
    hotkey: str | None = None
    volume: float = 0.8
    duration_seconds: float = 0.0


@dataclass
class AppConfig:
    """The whole user configuration."""

    audio: AudioSettings = field(default_factory=AudioSettings)
    sounds: list[SoundEntry] = field(default_factory=list)
    onboarding_complete: bool = False
    version: int = 1


def config_to_dict(config: AppConfig) -> dict[str, object]:
    """Serialize config to a JSON-ready dictionary."""
    return {
        "version": config.version,
        "onboarding_complete": config.onboarding_complete,
        "audio": {
            "input_device": config.audio.input_device,
            "output_device": config.audio.output_device,
            "mic_volume": config.audio.mic_volume,
            "master_volume": config.audio.master_volume,
        },
        "sounds": [
            {
                "id": sound.id,
                "name": sound.name,
                "file": sound.file,
                "hotkey": sound.hotkey,
                "volume": sound.volume,
                "duration_seconds": sound.duration_seconds,
            }
            for sound in config.sounds
        ],
    }


def config_from_dict(payload: object) -> AppConfig:
    """Build an ``AppConfig`` from decoded JSON.

    Missing fields fall back to defaults. Sounds without an id or file are
    skipped so one bad entry does not drop the rest of the library.
    """
    if not isinstance(payload, dict):
        return AppConfig()

    audio_raw = payload.get("audio", {})
    if not isinstance(audio_raw, dict):
        audio_raw = {}

    audio = AudioSettings(
        input_device=_optional_str(audio_raw.get("input_device")),
        output_device=_optional_str(audio_raw.get("output_device")),
        mic_volume=clamp_volume(audio_raw.get("mic_volume"), 1.0),
        master_volume=clamp_volume(audio_raw.get("master_volume"), 1.0),
    )

    sounds: list[SoundEntry] = []
    raw_sounds = payload.get("sounds", [])
    if isinstance(raw_sounds, list):
        for item in raw_sounds:
            entry = _sound_from_dict(item)
            if entry is not None:
                sounds.append(entry)

    version = payload.get("version", 1)
    try:
        version_int = int(version)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        version_int = 1

    return AppConfig(
        audio=audio,
        sounds=sounds,
        onboarding_complete=bool(payload.get("onboarding_complete", False)),
        version=version_int,
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sound_from_dict(item: object) -> SoundEntry | None:
    if not isinstance(item, dict):
        return None
    sound_id = _optional_str(item.get("id"))
    name = _optional_str(item.get("name"))
    file_name = _optional_str(item.get("file"))
    if sound_id is None or name is None or file_name is None:
        return None
    if ".." in file_name.replace("\\", "/").split("/"):
        return None
    duration = item.get("duration_seconds", 0.0)
    try:
        duration_value = float(duration)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        duration_value = 0.0
    if duration_value < 0:
        duration_value = 0.0
    return SoundEntry(
        id=sound_id,
        name=name,
        file=file_name.replace("\\", "/"),
        hotkey=_optional_str(item.get("hotkey")),
        volume=clamp_volume(item.get("volume"), 0.8),
        duration_seconds=duration_value,
    )
