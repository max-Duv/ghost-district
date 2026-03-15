from __future__ import annotations

from collections import deque
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np
from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPixmap, QRadialGradient
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .capture import CaptureBackend, CaptureConfig, build_backend_catalog, save_capture_log
from .capture_render import render_capture_bundle


class CaptureWorker(QObject):
    event_emitted = pyqtSignal(dict)
    status_changed = pyqtSignal(str)
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

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


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, accent: str) -> None:
        super().__init__()
        self.setObjectName("MetricCard")
        self.setProperty("accent", accent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class NebulaBackground(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._noise_tile = self._build_noise_tile()

    def _build_noise_tile(self) -> QPixmap:
        rng = np.random.default_rng(26)
        tile = np.zeros((192, 192, 4), dtype=np.uint8)
        tile[..., 0] = 164
        tile[..., 1] = 150
        tile[..., 2] = 255
        tile[..., 3] = rng.integers(0, 38, size=(192, 192), dtype=np.uint8)
        image = QImage(tile.data, tile.shape[1], tile.shape[0], tile.strides[0], QImage.Format.Format_RGBA8888)
        self._noise_array = tile
        return QPixmap.fromImage(image.copy())

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        base = QLinearGradient(0, 0, self.width(), self.height())
        base.setColorAt(0.0, QColor("#040816"))
        base.setColorAt(0.35, QColor("#0a1130"))
        base.setColorAt(0.7, QColor("#12144a"))
        base.setColorAt(1.0, QColor("#070b1f"))
        painter.fillRect(self.rect(), base)

        glows = [
            ((0.18, 0.16), 0.42, QColor(92, 70, 216, 150)),
            ((0.82, 0.12), 0.38, QColor(67, 99, 255, 120)),
            ((0.62, 0.74), 0.44, QColor(111, 58, 174, 140)),
            ((0.14, 0.84), 0.34, QColor(32, 112, 204, 95)),
        ]
        for (x_ratio, y_ratio), radius_ratio, color in glows:
            gradient = QRadialGradient(
                self.width() * x_ratio,
                self.height() * y_ratio,
                max(self.width(), self.height()) * radius_ratio,
            )
            edge = QColor(color)
            edge.setAlpha(0)
            gradient.setColorAt(0.0, color)
            gradient.setColorAt(1.0, edge)
            painter.fillRect(self.rect(), gradient)

        painter.fillRect(self.rect(), QBrush(self._noise_tile))

        vignette = QLinearGradient(0, 0, 0, self.height())
        vignette.setColorAt(0.0, QColor(4, 6, 18, 10))
        vignette.setColorAt(0.5, QColor(4, 6, 18, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 55))
        painter.fillRect(self.rect(), vignette)


class LiveWaveformPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Panel")

        self.backend_id = "ghost_playback"
        self.sample_index = 0
        self.history_x: deque[int] = deque(maxlen=180)
        self.history_y: deque[float] = deque(maxlen=180)
        self.sweep_points: dict[float, float] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.title_label = QLabel("Live Waveform")
        self.title_label.setStyleSheet("font-weight: 700; color: #d7e0ff;")
        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color: #8f9ad0;")
        self.subtitle_label.setWordWrap(True)

        self.figure = Figure(figsize=(6, 3.1), facecolor="#0a0f26")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setStyleSheet("background: transparent;")
        self.axis = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.10, right=0.98, top=0.88, bottom=0.20)

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addWidget(self.canvas, 1)

        self.set_backend("ghost_playback")

    def set_backend(self, backend_id: str) -> None:
        self.backend_id = backend_id
        self.reset()
        self._render_idle()

    def reset(self) -> None:
        self.sample_index = 0
        self.history_x.clear()
        self.history_y.clear()
        self.sweep_points.clear()

    def ingest_event(self, event: dict[str, Any]) -> None:
        self.sample_index += 1
        if self.backend_id == "rtl_sdr":
            frequency = _parse_frequency_mhz(event.get("channel"))
            power = _event_strength(event)
            if frequency is not None and power is not None:
                self.sweep_points[frequency] = power
                self._render_sdr()
            return

        amplitude = _event_strength(event)
        if amplitude is None:
            amplitude = -92.0 + 4.0 * np.sin(self.sample_index / 6.0)
        self.history_x.append(self.sample_index)
        self.history_y.append(float(amplitude))
        self._render_series()

    def _render_idle(self) -> None:
        self.axis.clear()
        self._style_axis()

        if self.backend_id == "ble_live":
            self.title_label.setText("BLE Live Waveform")
            self.subtitle_label.setText("Recent BLE advertisement power samples will scroll here as a live RSSI waveform.")
            self.axis.set_title("BLE RSSI timeline", color="#74f0d4", fontsize=11, pad=10)
            self.axis.set_xlabel("Event index", color="#b9c2ff")
            self.axis.set_ylabel("RSSI (dBm)", color="#b9c2ff")
            self.axis.set_ylim(-105, -20)
        elif self.backend_id == "rtl_sdr":
            self.title_label.setText("RF Sweep Waveform")
            self.subtitle_label.setText("Latest passive sweep profile across configured SDR frequencies will update in place.")
            self.axis.set_title("Spectrum power profile", color="#ff9ad9", fontsize=11, pad=10)
            self.axis.set_xlabel("Frequency (MHz)", color="#b9c2ff")
            self.axis.set_ylabel("Power (dB)", color="#b9c2ff")
        elif self.backend_id == "json_replay":
            self.title_label.setText("Replay Waveform")
            self.subtitle_label.setText("Replay sessions render a scrolling envelope from saved capture amplitudes.")
            self.axis.set_title("Replay signal envelope", color="#c294ff", fontsize=11, pad=10)
            self.axis.set_xlabel("Event index", color="#b9c2ff")
            self.axis.set_ylabel("Signal (dB)", color="#b9c2ff")
            self.axis.set_ylim(-105, -20)
        else:
            self.title_label.setText("Playback Waveform")
            self.subtitle_label.setText("Simulated Ghost District sessions render a live collection envelope from replayed observations.")
            self.axis.set_title("Playback collection envelope", color="#7db6ff", fontsize=11, pad=10)
            self.axis.set_xlabel("Event index", color="#b9c2ff")
            self.axis.set_ylabel("Signal (dB)", color="#b9c2ff")
            self.axis.set_ylim(-105, -20)

        self.axis.text(
            0.5,
            0.5,
            "Awaiting capture data",
            ha="center",
            va="center",
            transform=self.axis.transAxes,
            color="#7e89c7",
            fontsize=11,
        )
        self.canvas.draw_idle()

    def _render_series(self) -> None:
        self.axis.clear()
        self._style_axis()

        xs = np.array(self.history_x, dtype=float)
        ys = np.array(self.history_y, dtype=float)
        if xs.size == 0:
            self._render_idle()
            return

        if self.backend_id == "ble_live":
            color = "#52e0c4"
            title = "BLE RSSI timeline"
        elif self.backend_id == "json_replay":
            color = "#c294ff"
            title = "Replay signal envelope"
        else:
            color = "#7db6ff"
            title = "Playback collection envelope"

        if ys.size >= 5:
            kernel = np.ones(5) / 5.0
            smooth = np.convolve(ys, kernel, mode="same")
        else:
            smooth = ys

        self.axis.plot(xs, ys, color=color, alpha=0.28, linewidth=1.2)
        self.axis.plot(xs, smooth, color=color, linewidth=2.2)
        self.axis.fill_between(xs, smooth, np.min([smooth.min() - 4.0, -110.0]), color=color, alpha=0.12)
        self.axis.scatter(xs[-1:], smooth[-1:], color="#ff9ad9", s=30, zorder=5)
        self.axis.set_title(title, color=color, fontsize=11, pad=10)
        self.axis.set_xlabel("Event index", color="#b9c2ff")
        self.axis.set_ylabel("Signal (dB)", color="#b9c2ff")
        self.axis.set_xlim(max(0.0, xs.min() - 2.0), xs.max() + 2.0)
        lower = min(-105.0, float(ys.min()) - 6.0)
        upper = max(-25.0, float(ys.max()) + 6.0)
        self.axis.set_ylim(lower, upper)
        self.canvas.draw_idle()

    def _render_sdr(self) -> None:
        self.axis.clear()
        self._style_axis()

        if not self.sweep_points:
            self._render_idle()
            return

        freqs = np.array(sorted(self.sweep_points), dtype=float)
        powers = np.array([self.sweep_points[freq] for freq in freqs], dtype=float)
        self.axis.plot(freqs, powers, color="#ff9ad9", linewidth=2.2)
        self.axis.fill_between(freqs, powers, np.min([powers.min() - 3.0, -120.0]), color="#8d6dff", alpha=0.20)
        peak_idx = int(np.argmax(powers))
        self.axis.scatter([freqs[peak_idx]], [powers[peak_idx]], color="#ffd1f5", s=36, zorder=6)
        self.axis.annotate(
            f"Peak {freqs[peak_idx]:.1f} MHz",
            (freqs[peak_idx], powers[peak_idx]),
            textcoords="offset points",
            xytext=(8, 8),
            fontsize=9,
            color="#ffd1f5",
        )
        self.axis.set_title("Spectrum power profile", color="#ff9ad9", fontsize=11, pad=10)
        self.axis.set_xlabel("Frequency (MHz)", color="#b9c2ff")
        self.axis.set_ylabel("Power (dB)", color="#b9c2ff")
        self.axis.set_xlim(freqs.min() - 0.5, freqs.max() + 0.5)
        self.axis.set_ylim(float(powers.min()) - 6.0, float(powers.max()) + 6.0)
        self.canvas.draw_idle()

    def _style_axis(self) -> None:
        self.figure.set_facecolor("#0a0f26")
        self.axis.set_facecolor("#0f1738")
        self.axis.grid(alpha=0.18, color="#5b5fa8")
        self.axis.tick_params(colors="#c5ccff", labelsize=9)
        for spine in self.axis.spines.values():
            spine.set_color("#3d4b86")


class GhostDistrictCaptureWindow(QMainWindow):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.backends = build_backend_catalog(project_root)
        self.backend_map = {backend.backend_id: backend for backend in self.backends}
        self.worker_thread: QThread | None = None
        self.worker: CaptureWorker | None = None
        self.event_count = 0
        self.latest_output_path = ""

        self.setWindowTitle("Ghost District OTA Capture Console")
        self.resize(1360, 860)
        self._apply_styles()

        self.backend_combo = QComboBox()
        self.backend_combo.setMinimumWidth(260)
        for backend in self.backends:
            self.backend_combo.addItem(backend.display_name, backend.backend_id)
        self.backend_combo.currentIndexChanged.connect(self._refresh_backend_state)

        self.status_badge = QLabel("Idle")
        self.status_badge.setObjectName("StatusBadge")
        self.status_badge.setProperty("state", "idle")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.start_button = QPushButton("Start Capture")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.start_capture)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("SecondaryButton")
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
        self.events_table.setAlternatingRowColors(True)
        self.events_table.setShowGrid(False)
        self.events_table.setObjectName("EventsTable")

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LogView")
        log_font = QFont("Consolas", 10)
        self.log_view.setFont(log_font)

        self.hero_title = QLabel("OTA Capture Operations")
        self.hero_title.setObjectName("HeroTitle")
        self.hero_subtitle = QLabel(
            "Run simulated or live collection sessions, save event logs, and produce analysis plots for BLE and RF capture."
        )
        self.hero_subtitle.setObjectName("HeroSubtitle")
        self.hero_subtitle.setWordWrap(True)

        self.backend_label = QLabel("")
        self.backend_label.setObjectName("SectionTitle")
        self.description_label = QLabel("")
        self.description_label.setObjectName("DescriptionText")
        self.description_label.setWordWrap(True)
        self.waveform_panel = LiveWaveformPanel()

        self.event_card = MetricCard("Captured Events", "0", "blue")
        self.output_card = MetricCard("Output Bundle", "Pending", "orange")
        self.backend_card = MetricCard("Active Backend", "None", "green")

        central = NebulaBackground()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)
        root.addWidget(self._build_hero())
        root.addWidget(self._build_metrics())
        root.addWidget(self._build_main_splitter(), 1)

        self._refresh_backend_state()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #040816;
            }
            QWidget {
                color: #edf2ff;
                font-family: "Segoe UI", "Helvetica Neue", sans-serif;
                font-size: 11pt;
                background: transparent;
            }
            QFrame#HeroPanel, QFrame#Panel, QFrame#MetricCard {
                background: rgba(10, 16, 40, 212);
                border: 1px solid rgba(131, 121, 255, 90);
                border-radius: 18px;
            }
            QLabel#HeroTitle {
                font-size: 24pt;
                font-weight: 700;
                color: #f7f5ff;
            }
            QLabel#HeroSubtitle {
                color: #aab3ea;
                font-size: 11.5pt;
            }
            QLabel#SectionTitle {
                font-size: 14pt;
                font-weight: 700;
                color: #d7b4ff;
            }
            QLabel#DescriptionText {
                color: #9ea7d8;
                line-height: 1.3;
            }
            QLabel#MetricTitle {
                color: #8d99d6;
                font-size: 9.5pt;
                font-weight: 600;
                text-transform: uppercase;
            }
            QLabel#MetricValue {
                color: #f7f5ff;
                font-size: 16pt;
                font-weight: 700;
            }
            QFrame#MetricCard[accent="blue"] {
                border-left: 6px solid #6cb5ff;
            }
            QFrame#MetricCard[accent="orange"] {
                border-left: 6px solid #ff9ad9;
            }
            QFrame#MetricCard[accent="green"] {
                border-left: 6px solid #6ef3da;
            }
            QLabel#StatusBadge {
                padding: 8px 14px;
                border-radius: 13px;
                font-weight: 700;
                min-width: 120px;
            }
            QLabel#StatusBadge[state="idle"] {
                background: rgba(138, 152, 255, 50);
                color: #dfe5ff;
            }
            QLabel#StatusBadge[state="running"] {
                background: rgba(80, 224, 196, 45);
                color: #8fffe8;
            }
            QLabel#StatusBadge[state="stopping"] {
                background: rgba(255, 181, 94, 40);
                color: #ffd7a3;
            }
            QLabel#StatusBadge[state="failed"] {
                background: rgba(255, 97, 132, 45);
                color: #ffb3c5;
            }
            QLabel#StatusBadge[state="complete"] {
                background: rgba(111, 216, 255, 42);
                color: #bcefff;
            }
            QPushButton {
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 700;
                border: 1px solid rgba(143, 128, 255, 90);
                background: rgba(19, 27, 59, 225);
                color: #eef1ff;
            }
            QPushButton:hover {
                background: rgba(30, 39, 84, 235);
            }
            QPushButton#PrimaryButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3d4cff, stop:1 #8b44d6);
                color: #fffdf9;
                border: 1px solid rgba(171, 128, 255, 170);
            }
            QPushButton#PrimaryButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #5066ff, stop:1 #a653ef);
            }
            QPushButton#SecondaryButton {
                background: rgba(52, 27, 79, 220);
                color: #f8d8ff;
                border: 1px solid rgba(255, 154, 217, 110);
            }
            QPushButton:disabled {
                background: rgba(20, 25, 48, 180);
                color: #6c739e;
                border-color: rgba(83, 90, 133, 70);
            }
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QPlainTextEdit, QTableWidget {
                background: rgba(11, 18, 43, 220);
                border: 1px solid rgba(94, 103, 171, 90);
                border-radius: 10px;
                padding: 8px 10px;
                color: #eef1ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 26px;
            }
            QComboBox QAbstractItemView {
                background: rgba(9, 14, 34, 245);
                color: #eef1ff;
                selection-background-color: rgba(81, 100, 255, 150);
            }
            QGroupBox {
                color: #d7b4ff;
                font-weight: 700;
                border: 1px solid rgba(131, 121, 255, 75);
                border-radius: 16px;
                margin-top: 14px;
                padding-top: 14px;
                background: rgba(9, 15, 37, 205);
            }
            QGroupBox::title {
                left: 14px;
                padding: 0 6px;
            }
            QTableWidget {
                gridline-color: transparent;
                selection-background-color: rgba(112, 120, 255, 125);
                selection-color: #f8f9ff;
                alternate-background-color: rgba(18, 24, 56, 235);
            }
            QHeaderView::section {
                background: rgba(19, 26, 63, 235);
                color: #c5ccff;
                border: none;
                border-bottom: 1px solid rgba(94, 103, 171, 90);
                padding: 8px;
                font-weight: 700;
            }
            QPlainTextEdit#LogView {
                background: rgba(8, 13, 33, 232);
                color: #d6dcff;
            }
            """
        )

    def _build_hero(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("HeroPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(self.hero_title)
        left.addWidget(self.hero_subtitle)

        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self._build_backend_picker())
        button_row = QHBoxLayout()
        button_row.addWidget(self.status_badge)
        button_row.addStretch(1)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.start_button)
        right.addLayout(button_row)

        layout.addLayout(left, 3)
        layout.addLayout(right, 2)
        return panel

    def _build_backend_picker(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        label = QLabel("Capture Backend")
        label.setStyleSheet("font-weight: 700; color: #d7b4ff;")
        layout.addWidget(label)
        layout.addWidget(self.backend_combo, 1)
        return widget

    def _build_metrics(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.event_card, 1)
        layout.addWidget(self.output_card, 1)
        layout.addWidget(self.backend_card, 1)
        return widget

    def _build_main_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 860])
        return splitter

    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        backend_panel = QFrame()
        backend_layout = QVBoxLayout(backend_panel)
        backend_layout.setContentsMargins(0, 0, 0, 0)
        backend_layout.setSpacing(6)
        backend_layout.addWidget(self.backend_label)
        backend_layout.addWidget(self.description_label)

        layout.addWidget(backend_panel)
        layout.addWidget(self._build_config_group())
        layout.addWidget(self._build_status_group())
        layout.addStretch(1)
        return panel

    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Live Capture Feed")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        waveform_shell = QWidget()
        waveform_layout = QVBoxLayout(waveform_shell)
        waveform_layout.setContentsMargins(0, 0, 0, 0)
        waveform_layout.setSpacing(0)
        waveform_layout.addWidget(self.waveform_panel)

        table_shell = QWidget()
        table_layout = QVBoxLayout(table_shell)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(8)
        table_label = QLabel("Observed Events")
        table_label.setStyleSheet("font-weight: 700; color: #b9c2ff;")
        table_layout.addWidget(table_label)
        table_layout.addWidget(self.events_table)

        log_shell = QWidget()
        log_layout = QVBoxLayout(log_shell)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(8)
        log_label = QLabel("Operator Log")
        log_label.setStyleSheet("font-weight: 700; color: #b9c2ff;")
        log_layout.addWidget(log_label)
        log_layout.addWidget(self.log_view)

        splitter.addWidget(waveform_shell)
        splitter.addWidget(table_shell)
        splitter.addWidget(log_shell)
        splitter.setSizes([260, 360, 170])
        layout.addWidget(splitter, 1)
        return panel

    def _build_config_group(self) -> QGroupBox:
        group = QGroupBox("Capture Configuration")
        layout = QFormLayout(group)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(12)

        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(8)
        source_layout.addWidget(self.source_path_edit)
        source_layout.addWidget(self.source_browse_button)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(8)
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(self.output_browse_button)

        sdr_grid = QWidget()
        sdr_layout = QGridLayout(sdr_grid)
        sdr_layout.setContentsMargins(0, 0, 0, 0)
        sdr_layout.setHorizontalSpacing(10)
        sdr_layout.setVerticalSpacing(8)
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
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(10)

        self.metrics_label = QLabel("Events: 0")
        self.metrics_label.setStyleSheet("font-weight: 700; color: #eef1ff;")
        self.output_hint = QLabel("Plots and capture logs will be written when a session completes.")
        self.output_hint.setWordWrap(True)
        self.output_hint.setStyleSheet("color: #9ea7d8;")

        layout.addWidget(self.metrics_label)
        layout.addWidget(self.output_hint)
        return group

    def _refresh_backend_state(self) -> None:
        backend = self._selected_backend()
        available, detail = backend.availability()
        self._set_status(detail, "idle")
        self.backend_label.setText(backend.display_name)
        self.description_label.setText(backend.description)
        self.backend_card.set_value(backend.display_name)
        self.waveform_panel.set_backend(backend.backend_id)
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
        self.latest_output_path = config.output_path
        self.metrics_label.setText("Events: 0")
        self.event_card.set_value("0")
        self.output_card.set_value("Writing pending")
        self.backend_card.set_value(backend.display_name)
        self.waveform_panel.set_backend(backend.backend_id)
        self.output_hint.setText("Session is active. Capture logs and plots will be generated on completion.")

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
        self._set_status("Capture running", "running")

    def stop_capture(self) -> None:
        if self.worker is not None:
            self.worker.request_stop()
            self._set_status("Stopping capture", "stopping")

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
        self.metrics_label.setText(f"Events: {self.event_count}")
        self.event_card.set_value(str(self.event_count))
        self.waveform_panel.ingest_event(event)
        self.events_table.scrollToBottom()

    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _capture_finished(self, result: dict[str, Any]) -> None:
        event_total = result.get("event_count", result.get("events", 0))
        self._append_log(f"Capture finished with {event_total} events")
        if result.get("output_path"):
            self._append_log(f"Saved capture log to {result['output_path']}")
            self.output_card.set_value(Path(result["output_path"]).name)
        plot_paths = result.get("plot_paths") or {}
        for label, path in plot_paths.items():
            self._append_log(f"Saved {label} plot to {path}")
        if plot_paths:
            self.output_hint.setText(f"Generated {len(plot_paths)} plots alongside the saved capture log.")
        else:
            self.output_hint.setText("Capture completed without additional plot outputs.")
        self._set_status("Capture complete", "complete")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _capture_failed(self, message: str) -> None:
        self._set_status("Capture failed", "failed")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.output_hint.setText("The session ended with an error before outputs were finalized.")
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

    def _set_status(self, text: str, state: str) -> None:
        self.status_badge.setText(text)
        self.status_badge.setProperty("state", state)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def _choose_source_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Replay File", self.source_path_edit.text(), "JSON Files (*.json)")
        if path:
            self.source_path_edit.setText(path)

    def _choose_output_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Capture Log Output", self.output_path_edit.text(), "JSON Files (*.json)")
        if path:
            self.output_path_edit.setText(path)
            self.output_card.set_value(Path(path).name)


def launch_capture_gui(project_root: Path) -> int:
    app = QApplication.instance() or QApplication([])
    window = GhostDistrictCaptureWindow(project_root)
    window.show()
    return app.exec()


def _event_strength(event: dict[str, Any]) -> float | None:
    rssi = event.get("rssi_dbm")
    if isinstance(rssi, (int, float)):
        return float(rssi)

    metadata = event.get("metadata", {})
    score = metadata.get("score")
    if isinstance(score, (int, float)):
        return -98.0 + 18.0 * np.log10(max(float(score), 1e-4) * 10.0)
    return None


def _parse_frequency_mhz(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    text = value.lower().replace("mhz", "").strip()
    try:
        return float(text)
    except ValueError:
        return None
