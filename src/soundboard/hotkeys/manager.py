"""Global hotkeys.

The listener thread only pushes a sound id onto a queue. The UI thread drains
that queue. pynput is imported when the listener actually starts.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable

from soundboard.errors import HotkeyError
from soundboard.hotkeys.parser import Hotkey, find_conflict, format_hotkey, parse_hotkey, to_pynput

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Bind sounds to system-wide shortcuts and report conflicts."""

    def __init__(self, accessibility: Callable[[], bool | None] | None = None) -> None:
        self._accessibility = accessibility
        self._bindings: dict[str, Hotkey] = {}
        self._listener = None
        self._events: queue.SimpleQueue[str] = queue.SimpleQueue()
        self.permission_blocked = False

    def bindings(self) -> dict[str, str]:
        """Sound id to canonical hotkey text."""
        return {sound_id: format_hotkey(hotkey) for sound_id, hotkey in self._bindings.items()}

    def binding_for(self, sound_id: str) -> str | None:
        hotkey = self._bindings.get(sound_id)
        if hotkey is None:
            return None
        return format_hotkey(hotkey)

    def set_binding(self, sound_id: str, combo: str | None) -> None:
        """Replace the binding for one sound.

        An empty combo clears it. A combination already used by another sound
        raises :class:`HotkeyError` and leaves the previous binding in place.
        """
        if combo is None or not combo.strip():
            self._bindings.pop(sound_id, None)
            logger.info("Cleared hotkey for %s", sound_id)
            return
        hotkey = parse_hotkey(combo)
        conflict = find_conflict(self._bindings, sound_id, hotkey)
        if conflict is not None:
            label = format_hotkey(hotkey)
            raise HotkeyError(f"{label} is already used by another sound.")
        self._bindings[sound_id] = hotkey
        logger.info("Bound %s to %s", format_hotkey(hotkey), sound_id)

    def clear(self, sound_id: str) -> None:
        self._bindings.pop(sound_id, None)

    def apply(self) -> bool:
        """Restart the system listener from the current bindings.

        Returns False when Accessibility permission is missing. The bindings
        stay saved so they can start working after the user grants access.
        """
        self.shutdown()
        self.permission_blocked = False
        if not self._bindings:
            return True
        if self._accessibility is not None:
            granted = self._accessibility()
            if granted is False:
                self.permission_blocked = True
                logger.warning("Global hotkeys need Accessibility permission")
                return False
        try:
            from pynput import keyboard
        except Exception:
            logger.exception("pynput is not available")
            return False

        mapping = {
            to_pynput(hotkey): self._callback(sound_id)
            for sound_id, hotkey in self._bindings.items()
        }
        try:
            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.start()
        except Exception:
            logger.exception("Could not start global hotkeys")
            self._listener = None
            return False
        logger.info("Listening for %s global hotkeys", len(mapping))
        return True

    def shutdown(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is None:
            return
        try:
            listener.stop()
        except Exception:
            logger.exception("Could not stop the hotkey listener")

    def poll(self) -> list[str]:
        """Sound ids triggered since the last poll. Called on the UI thread."""
        triggered: list[str] = []
        while True:
            try:
                triggered.append(self._events.get_nowait())
            except queue.Empty:
                return triggered

    def _callback(self, sound_id: str):
        def _fire() -> None:
            self._events.put(sound_id)

        return _fire
