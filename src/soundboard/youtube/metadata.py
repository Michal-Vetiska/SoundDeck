"""Read YouTube metadata with yt-dlp. This does not download the media."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from soundboard.errors import YouTubeError

logger = logging.getLogger(__name__)

_ALLOWED_HOSTS = {
    "youtube.com",
    "youtu.be",
    "m.youtube.com",
    "music.youtube.com",
}


@dataclass(frozen=True)
class VideoMetadata:
    """The fields the clip dialog shows."""

    video_id: str
    title: str
    duration_seconds: float
    thumbnail_url: str | None
    webpage_url: str


def normalize_youtube_url(url: str) -> str:
    """Accept a normal YouTube link and reject other hosts.

    This is not a DRM bypass. yt-dlp still has to be able to read the video
    with its ordinary settings.
    """
    text = url.strip()
    if not text:
        raise YouTubeError("Enter a YouTube URL.")
    from urllib.parse import urlparse

    parsed = urlparse(text if "://" in text else f"https://{text}")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in _ALLOWED_HOSTS:
        raise YouTubeError("Enter a link to a YouTube video.")
    if not parsed.path or parsed.path == "/":
        raise YouTubeError("Enter a link to a YouTube video.")
    return text


def fetch_metadata(url: str) -> VideoMetadata:
    """Load title, duration, and thumbnail URL without saving the video."""
    normalized = normalize_youtube_url(url)
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        logger.exception("yt-dlp is not installed")
        raise YouTubeError("YouTube import is unavailable because yt-dlp is missing.") from exc

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
    }
    logger.info("Loading YouTube metadata")
    try:
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(normalized, download=False)
    except Exception as exc:
        logger.exception("YouTube metadata failed")
        raise YouTubeError(
            "Could not read this YouTube link. Check the URL and your connection."
        ) from exc
    if not isinstance(info, dict):
        raise YouTubeError("YouTube did not return information about this video.")
    title = str(info.get("title") or "Untitled")
    duration = info.get("duration")
    try:
        duration_seconds = float(duration) if duration is not None else 0.0
    except (TypeError, ValueError):
        duration_seconds = 0.0
    if duration_seconds <= 0:
        raise YouTubeError("This video has no duration SoundDeck can clip.")
    thumbnail = info.get("thumbnail")
    return VideoMetadata(
        video_id=str(info.get("id") or ""),
        title=title,
        duration_seconds=duration_seconds,
        thumbnail_url=str(thumbnail) if thumbnail else None,
        webpage_url=str(info.get("webpage_url") or normalized),
    )
