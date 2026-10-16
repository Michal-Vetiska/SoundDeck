"""Device selection, levels, and engine controls."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
)

from soundboard.audio.devices import DeviceSnapshot, display_name
from soundboard.services.controller import SoundboardController
from soundboard.ui.components.glass import GlassButton, GlassDialog, GlassSlider


class SettingsDialog(GlassDialog):
    """Choose the microphone and the virtual output."""

    def __init__(self, controller: SoundboardController, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self._snapshot: DeviceSnapshot | None = None

        title = QLabel("Settings")
        title.setObjectName("SectionTitle")
        self._content.addWidget(title)

        self._mic = QComboBox()
        self._output = QComboBox()
        self._content.addWidget(QLabel("Microphone"))
        self._content.addWidget(self._mic)
        self._content.addWidget(QLabel("Virtual output"))
        self._content.addWidget(self._output)

        self._warning = QLabel("")
        self._warning.setObjectName("WarningBanner")
        self._warning.setWordWrap(True)
        self._warning.hide()
        self._content.addWidget(self._warning)

        self._mic_volume = self._volume_row("Microphone volume", controller.config.audio.mic_volume)
        self._master_volume = self._volume_row("Master volume", controller.config.audio.master_volume)
        self._mic_volume.valueChanged.connect(
            lambda value: controller.set_mic_volume(value / 100, persist=False)
        )
        self._mic_volume.sliderReleased.connect(
            lambda: controller.set_mic_volume(self._mic_volume.value() / 100, persist=True)
        )
        self._master_volume.valueChanged.connect(
            lambda value: controller.set_master_volume(value / 100, persist=False)
        )
        self._master_volume.sliderReleased.connect(
            lambda: controller.set_master_volume(self._master_volume.value() / 100, persist=True)
        )

        engine_row = QHBoxLayout()
        for label, slot in (
            ("Start", controller.start_engine),
            ("Stop", controller.stop_engine),
            ("Restart", controller.restart_engine),
        ):
            button = GlassButton(label)
            button.clicked.connect(slot)
            engine_row.addWidget(button)
        self._content.addLayout(engine_row)

        apply_row = QHBoxLayout()
        refresh = GlassButton("Refresh devices")
        refresh.clicked.connect(self._refresh)
        apply = GlassButton("Use these devices", "PrimaryButton")
        apply.clicked.connect(self._apply_devices)
        apply_row.addWidget(refresh)
        apply_row.addWidget(apply)
        self._content.addLayout(apply_row)

        self._monitor = QCheckBox("Monitor output locally")
        self._monitor.setEnabled(controller.engine.monitor_available())
        self._monitor.setToolTip(
            "Not available in this version. Monitoring can create a feedback loop "
            "and will be added later."
        )
        self._content.addWidget(self._monitor)

        privacy = QHBoxLayout()
        accessibility = GlassButton("Accessibility settings")
        accessibility.clicked.connect(
            lambda: controller.platform.open_privacy_settings("accessibility")
        )
        microphone = GlassButton("Microphone settings")
        microphone.clicked.connect(lambda: controller.platform.open_privacy_settings("microphone"))
        wizard = GlassButton("Setup wizard")
        wizard.clicked.connect(self._reopen_wizard)
        privacy.addWidget(accessibility)
        privacy.addWidget(microphone)
        privacy.addWidget(wizard)
        self._content.addLayout(privacy)

        close = GlassButton("Close")
        close.clicked.connect(self.accept)
        self._content.addWidget(close)
        self._output.currentIndexChanged.connect(lambda _index: self._update_warning(self._snapshot))
        self._refresh()

    def _volume_row(self, label: str, value: float) -> GlassSlider:
        self._content.addWidget(QLabel(label))
        slider = GlassSlider()
        slider.setRange(0, 100)
        slider.setValue(int(round(value * 100)))
        self._content.addWidget(slider)
        return slider

    def _refresh(self) -> None:
        self._snapshot = self._controller.refresh_devices()
        self._fill(self._snapshot)

    def _fill(self, snapshot: DeviceSnapshot) -> None:
        self._fill_combo(self._mic, list(snapshot.inputs), self._controller.config.audio.input_device)
        self._fill_combo(
            self._output,
            list(snapshot.outputs),
            self._controller.config.audio.output_device,
        )
        self._update_warning(snapshot)

    def _fill_combo(self, combo: QComboBox, devices, selected: str | None) -> None:
        combo.blockSignals(True)
        combo.clear()
        labels = [display_name(device, devices) for device in devices]
        combo.addItems(labels)
        if selected:
            index = combo.findText(selected)
            if index < 0:
                combo.addItem(selected)
                index = combo.findText(selected)
            if index >= 0:
                combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _update_warning(self, snapshot: DeviceSnapshot | None) -> None:
        if snapshot is None:
            return
        messages: list[str] = []
        if snapshot.error:
            messages.append(snapshot.error)
        if snapshot.virtual_output is None:
            messages.append(self._controller.platform.install_instructions())
        elif not self._output_looks_virtual():
            messages.append(
                "This output does not look like a virtual device. "
                "Playing through speakers while the microphone is live can cause feedback."
            )
        if messages:
            self._warning.setText("\n\n".join(messages))
            self._warning.show()
        else:
            self._warning.hide()

    def _output_looks_virtual(self) -> bool:
        label = self._output.currentText().lower()
        return any(hint.lower() in label for hint in self._controller.platform.virtual_output_hints())

    def _apply_devices(self) -> None:
        self._controller.set_devices(self._mic.currentText() or None, self._output.currentText() or None)

    def _reopen_wizard(self) -> None:
        self.accept()
        parent = self.parent()
        opener = getattr(parent, "open_onboarding", None)
        if opener is not None:
            opener()
