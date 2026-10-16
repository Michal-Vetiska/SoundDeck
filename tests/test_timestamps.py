"""Timestamp parsing for the clip dialog."""

from __future__ import annotations

import pytest

from soundboard.errors import YouTubeError
from soundboard.youtube.timestamps import format_timestamp, parse_timestamp


def test_parse_seconds_minutes_and_hours() -> None:
    assert parse_timestamp("12.5") == pytest.approx(12.5)
    assert parse_timestamp("1:23") == pytest.approx(83)
    assert parse_timestamp("1:23.5") == pytest.approx(83.5)
    assert parse_timestamp("00:01:23.500") == pytest.approx(83.5)


def test_format_round_trip() -> None:
    text = format_timestamp(83.5)
    assert text == "00:01:23.500"
    assert parse_timestamp(text) == pytest.approx(83.5)


def test_invalid_timestamps() -> None:
    with pytest.raises(YouTubeError):
        parse_timestamp("nope")
    with pytest.raises(YouTubeError):
        parse_timestamp("-1")
    with pytest.raises(YouTubeError):
        parse_timestamp("")
