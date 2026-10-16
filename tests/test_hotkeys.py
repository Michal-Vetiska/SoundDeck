"""Hotkey parsing and conflict detection. No system listener is started."""

from __future__ import annotations

import pytest

from soundboard.errors import HotkeyError
from soundboard.hotkeys.manager import HotkeyManager
from soundboard.hotkeys.parser import (
    find_conflict,
    format_hotkey,
    hotkeys_conflict,
    parse_hotkey,
    to_pynput,
)


def test_parse_function_key_and_chord() -> None:
    f1 = parse_hotkey("F1")
    assert format_hotkey(f1) == "F1"
    assert to_pynput(f1) == "<f1>"

    chord = parse_hotkey("Cmd + Shift + V")
    assert format_hotkey(chord) == "Shift+Cmd+V"
    assert to_pynput(chord) == "<shift>+<cmd>+v"

    other = parse_hotkey("ctrl+shift+1")
    assert format_hotkey(other) == "Ctrl+Shift+1"
    assert hotkeys_conflict(chord, parse_hotkey("command+shift+v"))
    assert not hotkeys_conflict(f1, chord)


def test_parse_rejects_modifiers_only_and_unknown_keys() -> None:
    with pytest.raises(HotkeyError):
        parse_hotkey("cmd+shift")
    with pytest.raises(HotkeyError):
        parse_hotkey("F99")
    with pytest.raises(HotkeyError):
        parse_hotkey("")


def test_conflict_reports_the_other_sound() -> None:
    bindings = {"boom": parse_hotkey("F1"), "applause": parse_hotkey("F2")}
    assert find_conflict(bindings, "new", parse_hotkey("f1")) == "boom"
    assert find_conflict(bindings, "boom", parse_hotkey("F1")) is None
    assert find_conflict(bindings, "new", parse_hotkey("F3")) is None


def test_manager_rejects_duplicate_binding_without_replacing_it() -> None:
    manager = HotkeyManager()
    manager.set_binding("boom", "F1")
    with pytest.raises(HotkeyError):
        manager.set_binding("applause", "f1")
    assert manager.binding_for("boom") == "F1"
    assert manager.binding_for("applause") is None
    manager.set_binding("boom", None)
    assert manager.binding_for("boom") is None
