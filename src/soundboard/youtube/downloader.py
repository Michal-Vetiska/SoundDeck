"""Download the temporary audio for a clip the user is allowed to use.

The full download lives in a temporary directory and is deleted when the
dialog closes. Only the cut PCM file is copied into the sound library.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from soundboard.errors import YouTubeError
from soundboard.youtube.metadata import normalize_youtube_url

logger = logging.getLogger(__name__)


def download_audio(
    url: str,
    directory: Path,
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    """Download the best audio stream into ``directory`` and return its path."""
    normalized = normalize_youtube_url(url)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        logger.exception("yt-dlp is not installed")
        raise YouTubeError("YouTube import is unavailable because yt-dlp is missing.") from exc

    def _hook(status: dict) -> None:
        if on_progress is None:
            return
        if status.get("status") == "finished":
            on_progress(1.0)
            return
        if status.get("status") != "downloading":
            return
        total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
        done = status.get("downloaded_bytes") or 0
        if total:
            on_progress(max(0.0, min(1.0, float(done) / float(total))))

    options = {
        "format": "bestaudio/best",
        "outtmpl": str(directory / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "progress_hooks": [_hook],
    }
    logger.info("Downloading temporary YouTube audio")
    try:
        with YoutubeDL(options) as downloader:
            downloader.extract_info(normalized, download=True)
    except Exception as exc:
        logger.exception("YouTube download failed")
        raise YouTubeError(
            "Could not download audio from this video. "
            "Use a video you are allowed to download."
        ) from exc

    files = [
        path
        for path in directory.glob("source.*")
        if path.is_file() and not path.name.endswith(".part")
    ]
    if not files:
        raise YouTubeError("The download finished without an audio file.")
    files.sort(key=lambda path: path.stat().st_size, reverse=True)
    logger.info("Temporary audio saved as %s", files[0].name)
    return files[0]
