"""Import a clip from a YouTube video the user is allowed to use.

Download and FFmpeg run on worker threads. The dialog never calls sounddevice.
Preview and Add hand a PCM file back to the controller.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from soundboard.errors import YouTubeError
from soundboard.services.controller import SoundboardController
from soundboard.services.workers import DecodeWorker, DownloadWorker, MetadataWorker
from soundboard.ui.components.glass import GlassButton, GlassDialog
from soundboard.youtube.metadata import VideoMetadata, normalize_youtube_url
from soundboard.youtube.timestamps import format_timestamp, parse_timestamp
from soundboard.youtube.validation import validate_clip
from soundboard.youtube.waveform import NullWaveformProvider

_LEGAL = (
    "Only download and clip content you own or have the right to use. "
    "SoundDeck does not bypass DRM or other technical protection."
)


class _ThumbnailWorker(QThread):
    """Fetch a thumbnail without blocking the window."""

    finished_bytes = Signal(object)

    def __init__(self, url: str, parent=None) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            from urllib.request import urlopen

            with urlopen(self._url, timeout=8) as response:
                data = response.read(1_500_000)
        except Exception:
            data = b""
        self.finished_bytes.emit(data)


class YouTubeDialog(GlassDialog):
    """URL, timeline, preview, and add."""

    def __init__(self, controller: SoundboardController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Import from YouTube")
        self.setMinimumWidth(640)
        self._metadata: VideoMetadata | None = None
        self._source: Path | None = None
        self._start = 0.0
        self._end = 0.0
        self._duration = 0.0
        self._workers: list[QThread] = []
        self._temp = controller.make_temp_dir(uuid.uuid4().hex)
        self._waveform = NullWaveformProvider()

        title = QLabel("Import from YouTube")
        title.setObjectName("SectionTitle")
        legal = QLabel(_LEGAL)
        legal.setWordWrap(True)
        legal.setObjectName("WarningBanner")
        self._content.addWidget(title)
        self._content.addWidget(legal)

        url_row = QHBoxLayout()
        self._url = QLineEdit()
        self._url.setPlaceholderText("YouTube URL")
        load = GlassButton("Load", "PrimaryButton")
        load.clicked.connect(self._load)
        url_row.addWidget(self._url, 1)
        url_row.addWidget(load)
        self._content.addLayout(url_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.hide()
        self._content.addWidget(self._progress)
        self._status = QLabel("")
        self._status.setObjectName("MutedLabel")
        self._content.addWidget(self._status)

        self._thumb = QLabel("")
        self._thumb.setFixedHeight(120)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.hide()
        self._content.addWidget(self._thumb)
        self._info = QLabel("")
        self._info.setWordWrap(True)
        self._info.hide()
        self._content.addWidget(self._info)

        self._start_slider = QSlider(Qt.Orientation.Horizontal)
        self._end_slider = QSlider(Qt.Orientation.Horizontal)
        self._start_edit = QLineEdit("00:00:00.000")
        self._end_edit = QLineEdit("00:00:00.000")
        self._length = QLabel("Duration: 0.0 sec")
        self._editor = QWidget()
        editor_layout = QVBoxLayout(self._editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(QLabel("Start"))
        editor_layout.addWidget(self._start_slider)
        editor_layout.addWidget(self._start_edit)
        editor_layout.addWidget(QLabel("End"))
        editor_layout.addWidget(self._end_slider)
        editor_layout.addWidget(self._end_edit)
        editor_layout.addWidget(self._length)
        self._editor.hide()
        self._content.addWidget(self._editor)

        actions = QHBoxLayout()
        self._preview = GlassButton("Preview clip")
        self._preview.clicked.connect(self._preview_clip)
        self._preview.setEnabled(False)
        self._add = GlassButton("Add to soundboard", "PrimaryButton")
        self._add.clicked.connect(self._add_clip)
        self._add.setEnabled(False)
        close = GlassButton("Close")
        close.clicked.connect(self.reject)
        actions.addWidget(self._preview)
        actions.addWidget(self._add)
        actions.addStretch(1)
        actions.addWidget(close)
        self._content.addLayout(actions)

        self._start_slider.valueChanged.connect(lambda value: self._set_start(value / 1000, "slider"))
        self._end_slider.valueChanged.connect(lambda value: self._set_end(value / 1000, "slider"))
        self._start_edit.editingFinished.connect(lambda: self._set_start_from_text())
        self._end_edit.editingFinished.connect(lambda: self._set_end_from_text())

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._controller.stop_preview()
        for worker in self._workers:
            worker.requestInterruption()
            worker.wait(1500)
        shutil.rmtree(self._temp, ignore_errors=True)
        super().closeEvent(event)

    def _load(self) -> None:
        try:
            url = normalize_youtube_url(self._url.text())
        except YouTubeError as exc:
            self._status.setText(str(exc))
            return
        self._set_busy(True, "Loading video information…")
        worker = MetadataWorker(url, self)
        worker.succeeded.connect(self._metadata_ready)
        worker.failed.connect(self._failed)
        self._track(worker)
        worker.start()

    def _metadata_ready(self, metadata: object) -> None:
        if not isinstance(metadata, VideoMetadata):
            self._failed("YouTube did not return information about this video.")
            return
        self._metadata = metadata
        self._duration = metadata.duration_seconds
        self._source = None
        self._info.setText(f"{metadata.title}\nDuration: {format_timestamp(metadata.duration_seconds)}")
        self._info.show()
        self._editor.show()
        span = int(self._duration * 1000)
        for slider in (self._start_slider, self._end_slider):
            slider.setRange(0, max(span, 1))
        self._set_start(0.0, "code")
        self._set_end(min(self._duration, 5.0), "code")
        self._preview.setEnabled(True)
        self._add.setEnabled(True)
        self._set_busy(False, "")
        if metadata.thumbnail_url:
            thumb = _ThumbnailWorker(metadata.thumbnail_url, self)
            thumb.finished_bytes.connect(self._show_thumbnail)
            self._track(thumb)
            thumb.start()

    def _show_thumbnail(self, data: object) -> None:
        if not isinstance(data, (bytes, bytearray)) or not data:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self._thumb.setPixmap(
                pixmap.scaled(
                    320,
                    120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self._thumb.show()

    def _preview_clip(self) -> None:
        self._prepare_clip(self._controller.preview_pcm)

    def _add_clip(self) -> None:
        if self._metadata is None:
            return

        def _add(path: Path) -> None:
            self._controller.add_pcm_file(self._metadata.title if self._metadata else "YouTube clip", path)
            self._status.setText("Added to the soundboard.")

        self._prepare_clip(_add)

    def _prepare_clip(self, done) -> None:
        if self._metadata is None:
            return
        try:
            validate_clip(self._start, self._end, self._duration)
        except YouTubeError as exc:
            self._status.setText(str(exc))
            return
        if self._source is None:
            self._set_busy(True, "Downloading audio…")
            worker = DownloadWorker(self._metadata.webpage_url, self._temp, self)
            worker.progress.connect(self._on_progress)
            worker.succeeded.connect(lambda path: self._downloaded(path, done))
            worker.failed.connect(self._failed)
            self._track(worker)
            worker.start()
            return
        self._cut(self._source, done)

    def _downloaded(self, path: str, done) -> None:
        self._source = Path(path)
        self._cut(self._source, done)

    def _cut(self, source: Path, done) -> None:
        destination = self._temp / f"clip-{uuid.uuid4().hex}.f32"
        self._set_busy(True, "Cutting clip…")
        self._progress.setRange(0, 0)
        self._progress.show()
        worker = DecodeWorker(source, destination, self._start, self._end, self._duration, self)
        worker.succeeded.connect(lambda path: self._cut_ready(path, done))
        worker.failed.connect(self._failed)
        self._track(worker)
        worker.start()

    def _cut_ready(self, path: str, done) -> None:
        self._set_busy(False, "")
        done(Path(path))

    def _on_progress(self, value: float) -> None:
        self._progress.setRange(0, 1000)
        self._progress.setValue(int(value * 1000))
        self._progress.show()

    def _failed(self, message: str) -> None:
        self._set_busy(False, message)

    def _set_busy(self, busy: bool, message: str) -> None:
        self._preview.setEnabled(not busy and self._metadata is not None)
        self._add.setEnabled(not busy and self._metadata is not None)
        self._status.setText(message)
        if not busy:
            self._progress.hide()
            self._progress.setRange(0, 1000)

    def _set_start_from_text(self) -> None:
        try:
            self._set_start(parse_timestamp(self._start_edit.text()), "text")
        except YouTubeError as exc:
            self._status.setText(str(exc))

    def _set_end_from_text(self) -> None:
        try:
            self._set_end(parse_timestamp(self._end_edit.text()), "text")
        except YouTubeError as exc:
            self._status.setText(str(exc))

    def _set_start(self, seconds: float, source: str) -> None:
        seconds = min(max(0.0, seconds), self._duration)
        if self._end and seconds >= self._end:
            seconds = max(0.0, self._end - 0.05)
        self._start = seconds
        self._write_slider(self._start_slider, seconds)
        if source != "text":
            self._write_edit(self._start_edit, seconds)
        self._update_length()

    def _set_end(self, seconds: float, source: str) -> None:
        seconds = min(max(0.0, seconds), self._duration)
        if seconds <= self._start:
            seconds = min(self._duration, self._start + 0.05)
        self._end = seconds
        self._write_slider(self._end_slider, seconds)
        if source != "text":
            self._write_edit(self._end_edit, seconds)
        self._update_length()

    def _write_slider(self, slider: QSlider, seconds: float) -> None:
        slider.blockSignals(True)
        slider.setValue(int(seconds * 1000))
        slider.blockSignals(False)

    def _write_edit(self, edit: QLineEdit, seconds: float) -> None:
        edit.blockSignals(True)
        edit.setText(format_timestamp(seconds))
        edit.blockSignals(False)

    def _update_length(self) -> None:
        length = max(0.0, self._end - self._start)
        self._length.setText(f"Duration: {length:.1f} sec")

    def _track(self, worker: QThread) -> None:
        self._workers.append(worker)
        worker.finished.connect(lambda worker=worker: self._workers.remove(worker) if worker in self._workers else None)
