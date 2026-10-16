"""Parse and format hotkey strings such as ``F1`` or ``cmd+shift+v``."""

from __future__ import annotations

from dataclasses import dataclass

from soundboard.errors import HotkeyError

_MODIFIER_ALIASES = {
    "cmd": "cmd",
    "command": "cmd",
    "meta": "cmd",
    "super": "cmd",
    "win": "cmd",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "opt": "alt",
    "shift": "shift",
}

_MODIFIER_ORDER = ("ctrl", "alt", "shift", "cmd")

_SPECIAL_KEYS = {
    "space": "space",
    "tab": "tab",
    "return": "enter",
    "enter": "enter",
    "esc": "esc",
    "escape": "esc",
    "left": "left",
    "right": "right",
    "up": "up",
    "down": "down",
    "minus": "minus",
    "dash": "minus",
    "-": "minus",
    "equals": "equals",
    "equal": "equals",
    "=": "equals",
}


@dataclass(frozen=True)
class Hotkey:
    """A single non-modifier key plus any modifiers."""

    key: str
    modifiers: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.key in _MODIFIER_ALIASES:
            raise HotkeyError("A hotkey needs a key, not only modifiers.")


def parse_hotkey(text: str) -> Hotkey:
    """Parse a hotkey written by the user or stored in config."""
    raw = text.strip().lower().replace(" ", "")
    if not raw:
        raise HotkeyError("Enter a hotkey.")
    parts = [part for part in raw.split("+") if part]
    if not parts:
        raise HotkeyError("Enter a hotkey.")
    modifiers: set[str] = set()
    key: str | None = None
    for part in parts:
        if part in _MODIFIER_ALIASES:
            modifiers.add(_MODIFIER_ALIASES[part])
            continue
        if key is not None:
            raise HotkeyError(f"Could not understand the hotkey “{text.strip()}”.")
        key = _normalize_key(part)
    if key is None:
        raise HotkeyError("A hotkey needs a key, not only modifiers.")
    return Hotkey(key=key, modifiers=frozenset(modifiers))


def format_hotkey(hotkey: Hotkey) -> str:
    """Canonical spelling stored in config and shown on a card."""
    names = [name.capitalize() if name != "cmd" else "Cmd" for name in _MODIFIER_ORDER if name in hotkey.modifiers]
    names.append(_display_key(hotkey.key))
    return "+".join(names)


def to_pynput(hotkey: Hotkey) -> str:
    """Convert a hotkey to the string ``pynput`` GlobalHotKeys expects."""
    pieces = [f"<{name}>" for name in _MODIFIER_ORDER if name in hotkey.modifiers]
    special = {
        "space": "<space>",
        "tab": "<tab>",
        "enter": "<enter>",
        "esc": "<esc>",
        "left": "<left>",
        "right": "<right>",
        "up": "<up>",
        "down": "<down>",
        "minus": "-",
        "equals": "=",
    }
    key = hotkey.key
    if key in special:
        token = special[key]
    elif len(key) == 1:
        token = key
    else:
        token = f"<{key}>"
    pieces.append(token)
    return "+".join(pieces)


def hotkeys_conflict(left: Hotkey, right: Hotkey) -> bool:
    """Two bindings conflict when they are the same combination."""
    return left == right


def find_conflict(
    bindings: dict[str, Hotkey],
    sound_id: str,
    hotkey: Hotkey,
) -> str | None:
    """Return the other sound id that already uses ``hotkey``."""
    for other_id, other in bindings.items():
        if other_id != sound_id and hotkeys_conflict(other, hotkey):
            return other_id
    return None


def _normalize_key(part: str) -> str:
    if part in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[part]
    if len(part) == 1 and (part.isalpha() or part.isdigit()):
        return part
    if part.startswith("f") and part[1:].isdigit():
        number = int(part[1:])
        if 1 <= number <= 24:
            return part
    raise HotkeyError(f"The key “{part}” is not supported.")


def _display_key(key: str) -> str:
    if key.startswith("f") and key[1:].isdigit():
        return key.upper()
    if len(key) == 1 and key.isalpha():
        return key.upper()
    if key == "minus":
        return "-"
    if key == "equals":
        return "="
    return key.capitalize()
