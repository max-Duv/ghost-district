from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .capture import CaptureBackend, CaptureConfig, build_backend_catalog, save_capture_log
from .capture_render import render_capture_bundle


class CaptureWorker(QObject):
    event_emitted = Signal(dict)
    status_changed = Signal(str)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, backend: CaptureBackend, config: CaptureConfig) -> None:
        super().__init__()
        self.backend = backend
        self.config = config
        self._stop_requested = False
        self._events: list[dict[str, Any]] = []

    def request_stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        try:
            summary = self.backend.capture(
                self.config,
                self._handle_event,
                self.status_changed.emit,
                lambda: self._stop_requested,
            )
            if self.config.output_path:
                output_path = Path(self.config.output_path)
                save_capture_log(self._events, summary, output_path)
                plot_paths = render_capture_bundle(self._events, summary, output_path)
            else:
                plot_paths = {}
            result = asdict(summary)
            result["events"] = len(self._events)
            result["plot_paths"] = plot_paths
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _handle_event(self, event: dict[str, Any]) -> None:
        self._events.append(event)
        self.event_emitted.emit(event)


class GhostDistrictCaptureWindow(QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.backends = build_backend_catalog(project_root)
        self.backend_map = {backend.backend_id: backend for backend in self.backends}
        self.worker_thread: QThread | None = None
        self.worker: CaptureWorker | None = None
        self.event_count = 0

        self.setWindowTitle("Ghost District OTA Capture Console")
        self.resize(1220, 760)

        self.backend_combo = QComboBox()
        for backend in self.backends:
            self.backend_combo.addItem(backend.display_name, backend.backend_id)
        self.backend_combo.currentIndexChanged.connect(self._refresh_backend_state)

        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("font-weight: 600;")
        self.start_button = QPushButton("Start Capture")
        self.start_button.clicked.connect(self.start_capture)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_capture)
        self.stop_button.setEnabled(False)

        self.source_path_edit = QLineEdit(str(project_root / "outputs" / "ghost_district_sensor_observations.json"))
        self.source_browse_button = QPushButton("Browse")
        self.source_browse_button.clicked.connect(self._choose_source_file)

        self.output_path_edit = QLineEdit(str(project_root / "captures" / "latest_capture.json"))
        self.output_browse_button = QPushButton("Save As")
        self.output_browse_button.clicked.connect(self._choose_output_file)

        self.sensor_combo = QComboBox()
        self.sensor_combo.addItem("All sensors", "")
        summary_path = project_root / "outputs" / "ghost_district_summary.json"
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                for sensor in summary.get("sensors", []):
                    self.sensor_combo.addItem(sensor["label"], sensor["id"])
            except Exception:
                pass

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(1.0, 3600.0)
        self.duration_spin.setDecimals(1)
        self.duration_spin.setValue(20.0)

        self.replay_speed_spin = QDoubleSpinBox()
        self.replay_speed_spin.setRange(1.0, 3600.0)
        self.replay_speed_spin.setDecimals(1)
        self.replay_speed_spin.setValue(120.0)

        self.device_edit = QLineEdit("")
        self.start_freq_spin = QDoubleSpinBox()
        self.start_freq_spin.setRange(1.0, 6000.0)
        self.start_freq_spin.setValue(2402.0)
        self.stop_freq_spin = QDoubleSpinBox()
        self.stop_freq_spin.setRange(1.0, 6000.0)
        self.stop_freq_spin.setValue(2480.0)
        self.step_freq_spin = QDoubleSpinBox()
        self.step_freq_spin.setRange(0.1, 1000.0)
        self.step_freq_spin.setValue(2.0)
        self.sample_rate_spin = QDoubleSpinBox()
        self.sample_rate_spin.setRange(100000.0, 10000000.0)
        self.sample_rate_spin.setDecimals(0)
        self.sample_rate_spin.setSingleStep(100000.0)
        self.sample_rate_spin.setValue(2400000.0)
        self.gain_spin = QDoubleSpinBox()
        self.gain_spin.setRange(0.0, 60.0)
        self.gain_spin.setValue(20.0)
        self.dwell_spin = QSpinBox()
        self.dwell_spin.setRange(50, 5000)
        self.dwell_spin.setValue(250)

        self.events_table = QTableWidget(0, 6)
        self.events_table.setHorizontalHeaderLabels(["Time", "Backend", "Source", "Protocol", "RSSI", "Summary"])
        self.events_table.horizontalHeader().setStretchLastSection(True)
        self.events_table.verticalHeader().setVisible(False)
        self.events_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.events_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)

        self.metrics_label = QLabel("Events: 0 | Backend: none")
        self.description_label = QLabel("")
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.addLayout(self._build_header())
        root.addLayout(self._build_body())

        self._refresh_backend_state()

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel("Backend"))
        layout.addWidget(self.backend_combo, 1)
        layout.addWidget(self.status_label, 1)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        return layout

    def _build_body(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(self._build_config_group())
        left.addWidget(self._build_status_group())

        right = QVBoxLayout()
        right.addWidget(self.events_table, 4)
        right.addWidget(self.log_view, 2)

        layout.addLayout(left, 2)
        layout.addLayout(right, 3)
        return layout

    def _build_config_group(self) -> QGroupBox:
        group = QGroupBox("Capture Configuration")
        layout = QFormLayout(group)

        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_path_edit)
        source_layout.addWidget(self.source_browse_button)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(self.output_browse_button)

        sdr_grid = QWidget()
        sdr_layout = QGridLayout(sdr_grid)
        sdr_layout.setContentsMargins(0, 0, 0, 0)
        sdr_layout.addWidget(QLabel("Start MHz"), 0, 0)
        sdr_layout.addWidget(self.start_freq_spin, 0, 1)
        sdr_layout.addWidget(QLabel("Stop MHz"), 0, 2)
        sdr_layout.addWidget(self.stop_freq_spin, 0, 3)
        sdr_layout.addWidget(QLabel("Step MHz"), 1, 0)
        sdr_layout.addWidget(self.step_freq_spin, 1, 1)
        sdr_layout.addWidget(QLabel("Sample Rate"), 1, 2)
        sdr_layout.addWidget(self.sample_rate_spin, 1, 3)
        sdr_layout.addWidget(QLabel("Gain dB"), 2, 0)
        sdr_layout.addWidget(self.gain_spin, 2, 1)
        sdr_layout.addWidget(QLabel("Dwell ms"), 2, 2)
        sdr_layout.addWidget(self.dwell_spin, 2, 3)

        layout.addRow("Source File", source_row)
        layout.addRow("Output Log", output_row)
        layout.addRow("Sensor Filter", self.sensor_combo)
        layout.addRow("Duration (s)", self.duration_spin)
        layout.addRow("Replay Speed", self.replay_speed_spin)
        layout.addRow("Device / Adapter", self.device_edit)
        layout.addRow("RF Sweep", sdr_grid)
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Session State")
        layout = QVBoxLayout(group)
        layout.addWidget(self.metrics_label)
        layout.addWidget(self.description_label)
        return group

    def _refresh_backend_state(self) -> None:
        backend = self._selected_backend()
        available, detail = backend.availability()
        self.status_label.setText(detail)
        self.description_label.setText(backend.description)
        self.start_button.setEnabled(available and self.worker_thread is None)

        is_replay = backend.backend_id in {"ghost_playback", "json_replay"}
        is_ble = backend.backend_id == "ble_live"
        is_sdr = backend.backend_id == "rtl_sdr"

        self.source_path_edit.setEnabled(is_replay)
        self.source_browse_button.setEnabled(is_replay)
        self.sensor_combo.setEnabled(backend.backend_id == "ghost_playback")
        self.replay_speed_spin.setEnabled(is_replay)
        self.device_edit.setEnabled(is_ble or is_sdr)
        self.start_freq_spin.setEnabled(is_sdr)
        self.stop_freq_spin.setEnabled(is_sdr)
        self.step_freq_spin.setEnabled(is_sdr)
        self.sample_rate_spin.setEnabled(is_sdr)
        self.gain_spin.setEnabled(is_sdr)
        self.dwell_spin.setEnabled(is_sdr)

    def _selected_backend(self) -> CaptureBackend:
        backend_id = self.backend_combo.currentData()
        return self.backend_map[str(backend_id)]

    def _build_config(self) -> CaptureConfig:
        return CaptureConfig(
            backend_id=self._selected_backend().backend_id,
            duration_seconds=float(self.duration_spin.value()),
            replay_speed=float(self.replay_speed_spin.value()),
            source_path=self.source_path_edit.text().strip(),
            sensor_id=str(self.sensor_combo.currentData() or ""),
            output_path=self.output_path_edit.text().strip(),
            device_selector=self.device_edit.text().strip(),
            start_freq_mhz=float(self.start_freq_spin.value()),
            stop_freq_mhz=float(self.stop_freq_spin.value()),
            step_freq_mhz=float(self.step_freq_spin.value()),
            sample_rate_hz=float(self.sample_rate_spin.value()),
            gain_db=float(self.gain_spin.value()),
            dwell_ms=int(self.dwell_spin.value()),
        )

    def start_capture(self) -> None:
        if self.worker_thread is not None:
            return

        backend = self._selected_backend()
        config = self._build_config()
        self.events_table.setRowCount(0)
        self.log_view.clear()
        self.event_count = 0
        self.metrics_label.setText(f"Events: 0 | Backend: {backend.display_name}")

        self.worker_thread = QThread(self)
        self.worker = CaptureWorker(backend, config)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.event_emitted.connect(self._append_event)
        self.worker.status_changed.connect(self._append_log)
        self.worker.finished.connect(self._capture_finished)
        self.worker.failed.connect(self._capture_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)
        self.worker_thread.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Capture running")

    def stop_capture(self) -> None:
        if self.worker is not None:
            self.worker.request_stop()
            self.status_label.setText("Stopping...")

    def _append_event(self, event: dict[str, Any]) -> None:
        row = self.events_table.rowCount()
        self.events_table.insertRow(row)
        values = [
            event.get("timestamp", ""),
            event.get("backend_id", ""),
            event.get("source_label", ""),
            event.get("protocol", ""),
            "" if event.get("rssi_dbm") is None else str(event.get("rssi_dbm")),
            event.get("summary", ""),
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if column == 4:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.events_table.setItem(row, column, item)

        self.event_count += 1
        self.metrics_label.setText(f"Events: {self.event_count} | Backend: {self._selected_backend().display_name}")
        self.events_table.scrollToBottom()

    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _capture_finished(self, result: dict[str, Any]) -> None:
        self._append_log(f"Capture finished with {result.get('event_count', result.get('events', 0))} events")
        if result.get("output_path"):
            self._append_log(f"Saved capture log to {result['output_path']}")
        for label, path in (result.get("plot_paths") or {}).items():
            self._append_log(f"Saved {label} plot to {path}")
        self.status_label.setText("Capture complete")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _capture_failed(self, message: str) -> None:
        self.status_label.setText("Capture failed")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        QMessageBox.critical(self, "Capture Failed", message)
        self._append_log(f"ERROR: {message}")

    def _cleanup_worker(self) -> None:
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
        if self.worker is not None:
            self.worker.deleteLater()
        self.worker_thread = None
        self.worker = None
        self._refresh_backend_state()

    def _choose_source_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Replay File", self.source_path_edit.text(), "JSON Files (*.json)")
        if path:
            self.source_path_edit.setText(path)

    def _choose_output_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Capture Log Output", self.output_path_edit.text(), "JSON Files (*.json)")
        if path:
            self.output_path_edit.setText(path)


def launch_capture_gui(project_root: Path) -> int:
    app = QApplication.instance() or QApplication([])
    window = GhostDistrictCaptureWindow(project_root)
    window.show()
    return app.exec()
