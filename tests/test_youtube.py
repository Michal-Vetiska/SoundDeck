"""Clip rules and URL checks. Nothing is downloaded."""

from __future__ import annotations

import pytest

from soundboard.errors import YouTubeError
from soundboard.youtube.metadata import normalize_youtube_url
from soundboard.youtube.validation import MAX_CLIP_SECONDS, validate_clip


def test_clip_length_is_returned() -> None:
    assert validate_clip(83.5, 88.2, 120) == pytest.approx(4.7)


def test_clip_must_move_forward_and_stay_inside_the_video() -> None:
    with pytest.raises(YouTubeError):
        validate_clip(10, 10, 20)
    with pytest.raises(YouTubeError):
        validate_clip(8, 3, 20)
    with pytest.raises(YouTubeError):
        validate_clip(0, 10, 5)
    with pytest.raises(YouTubeError):
        validate_clip(0, MAX_CLIP_SECONDS + 1, None)


def test_youtube_url_hosts() -> None:
    assert "watch" in normalize_youtube_url("https://www.youtube.com/watch?v=abc")
    assert normalize_youtube_url("https://youtu.be/abc").endswith("abc")
    with pytest.raises(YouTubeError):
        normalize_youtube_url("https://example.com/video")
    with pytest.raises(YouTubeError):
        normalize_youtube_url("")
