"""Background workers.

YouTube downloads and FFmpeg run here so the Qt event loop stays responsive.
Results go back to the UI thread through signals.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from soundboard.audio.loader import ffmpeg_to_pcm, save_pcm, validate_audio_file
from soundboard.errors import SoundDeckError, public_message
from soundboard.youtube.cutter import cut_to_pcm
from soundboard.youtube.downloader import download_audio
from soundboard.youtube.metadata import VideoMetadata, fetch_metadata

logger = logging.getLogger(__name__)


class MetadataWorker(QThread):
    """Load YouTube title and duration without downloading media."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, url: str, parent=None) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            metadata: VideoMetadata = fetch_metadata(self._url)
        except Exception as exc:
            logger.exception("YouTube metadata worker failed")
            self.failed.emit(public_message(exc))
        else:
            self.succeeded.emit(metadata)


class DownloadWorker(QThread):
    """Download temporary audio and report progress from 0 to 1."""

    succeeded = Signal(str)
    failed = Signal(str)
    progress = Signal(float)

    def __init__(self, url: str, directory: Path, parent=None) -> None:
        super().__init__(parent)
        self._url = url
        self._directory = directory

    def run(self) -> None:
        try:
            path = download_audio(self._url, self._directory, on_progress=self.progress.emit)
        except Exception as exc:
            logger.exception("YouTube download worker failed")
            self.failed.emit(public_message(exc))
        else:
            self.succeeded.emit(str(path))


class DecodeWorker(QThread):
    """Decode a local file, or a slice of one, into a PCM file."""

    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        source: Path,
        destination: Path,
        start: float | None = None,
        end: float | None = None,
        duration: float | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._destination = destination
        self._start = start
        self._end = end
        self._duration = duration

    def run(self) -> None:
        try:
            if self._start is None and self._end is None:
                validate_audio_file(self._source)
                samples = ffmpeg_to_pcm(self._source)
                save_pcm(self._destination, samples)
            else:
                cut_to_pcm(
                    self._source,
                    self._destination,
                    self._start or 0.0,
                    self._end if self._end is not None else 0.0,
                    self._duration,
                )
        except SoundDeckError as exc:
            logger.exception("Decode worker failed")
            self.failed.emit(public_message(exc))
        except Exception as exc:
            logger.exception("Decode worker failed unexpectedly")
            self.failed.emit(public_message(exc))
        else:
            self.succeeded.emit(str(self._destination))
