from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import math
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from .capture import CaptureSummary


def render_capture_bundle(
    events: list[dict[str, Any]],
    summary: CaptureSummary,
    output_path: Path,
) -> dict[str, str]:
    output_dir = output_path.parent / f"{output_path.stem}_plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_paths: dict[str, str] = {}
    if not events:
        return plot_paths

    plot_paths["overview"] = str(_render_overview(events, summary, output_dir))
    plot_paths["source_mix"] = str(_render_source_mix(events, output_dir))

    protocols = {str(event.get("protocol", "")) for event in events}
    if any("BLE" in protocol for protocol in protocols):
        plot_paths["ble_analysis"] = str(_render_ble_analysis(events, output_dir))
    if any("Spectrum Power" == protocol for protocol in protocols):
        heatmap_path = _render_sdr_heatmap(events, output_dir)
        if heatmap_path is not None:
            plot_paths["rf_sweep"] = str(heatmap_path)

    return plot_paths


def _render_overview(events: list[dict[str, Any]], summary: CaptureSummary, output_dir: Path) -> Path:
    timestamps = [_parse_timestamp(event.get("timestamp")) for event in events]
    event_times = [timestamp for timestamp in timestamps if timestamp is not None]
    rssi_values = [event.get("rssi_dbm") for event in events if isinstance(event.get("rssi_dbm"), (int, float))]

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle(f"{summary.backend_name} Session Overview")

    if event_times:
        time_bins = mdates.date2num(event_times)
        bin_count = min(24, max(6, int(math.sqrt(len(time_bins)))))
        axes[0].hist(time_bins, bins=bin_count, color="#2563eb", alpha=0.85)
        axes[0].xaxis_date()
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        axes[0].set_ylabel("Event count")
        axes[0].set_title("Arrival cadence")
    else:
        axes[0].text(0.5, 0.5, "No timestamped events", ha="center", va="center", transform=axes[0].transAxes)
    axes[0].grid(alpha=0.25)

    if rssi_values:
        axes[1].hist(rssi_values, bins=min(20, max(6, len(rssi_values) // 3)), color="#ea580c", alpha=0.85)
        axes[1].set_xlabel("RSSI / power (dB)")
        axes[1].set_ylabel("Count")
        axes[1].set_title("Signal strength distribution")
    else:
        axes[1].text(0.5, 0.5, "No RSSI values available", ha="center", va="center", transform=axes[1].transAxes)
    axes[1].grid(alpha=0.25)

    fig.tight_layout()
    path = output_dir / "capture_overview.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _render_source_mix(events: list[dict[str, Any]], output_dir: Path) -> Path:
    top_sources = Counter(str(event.get("source_label", "Unknown")) for event in events).most_common(10)
    top_protocols = Counter(str(event.get("protocol", "Unknown")) for event in events).most_common(8)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    if top_sources:
        labels = [item[0] for item in reversed(top_sources)]
        values = [item[1] for item in reversed(top_sources)]
        axes[0].barh(labels, values, color="#0f766e")
        axes[0].set_title("Top emitting sources")
        axes[0].set_xlabel("Events")
    else:
        axes[0].text(0.5, 0.5, "No sources", ha="center", va="center", transform=axes[0].transAxes)

    if top_protocols:
        labels = [item[0] for item in top_protocols]
        values = [item[1] for item in top_protocols]
        axes[1].pie(values, labels=labels, autopct="%1.0f%%", startangle=110)
        axes[1].set_title("Protocol mix")
    else:
        axes[1].text(0.5, 0.5, "No protocols", ha="center", va="center", transform=axes[1].transAxes)

    fig.tight_layout()
    path = output_dir / "capture_mix.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _render_ble_analysis(events: list[dict[str, Any]], output_dir: Path) -> Path:
    ble_events = [event for event in events if "BLE" in str(event.get("protocol", ""))]
    timestamps = [_parse_timestamp(event.get("timestamp")) for event in ble_events]
    source_rssi: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    service_counter: Counter[str] = Counter()

    for event, timestamp in zip(ble_events, timestamps, strict=True):
        if timestamp is not None and isinstance(event.get("rssi_dbm"), (int, float)):
            source_rssi[str(event.get("source_label", "Unknown"))].append((timestamp, float(event["rssi_dbm"])))
        metadata = event.get("metadata", {})
        for service in metadata.get("service_uuids", []) or []:
            service_counter[str(service)] += 1

    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    for source, readings in sorted(source_rssi.items(), key=lambda item: len(item[1]), reverse=True)[:8]:
        xs = [reading[0] for reading in readings]
        ys = [reading[1] for reading in readings]
        axes[0].scatter(xs, ys, s=18, alpha=0.75, label=source)
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    axes[0].set_ylabel("RSSI (dBm)")
    axes[0].set_title("BLE device RSSI over time")
    axes[0].grid(alpha=0.25)
    if source_rssi:
        axes[0].legend(fontsize=8, ncol=2)

    top_services = service_counter.most_common(10)
    if top_services:
        labels = [item[0] for item in reversed(top_services)]
        values = [item[1] for item in reversed(top_services)]
        axes[1].barh(labels, values, color="#7c3aed")
        axes[1].set_xlabel("Advertisements")
        axes[1].set_title("Top BLE service UUIDs")
    else:
        axes[1].text(0.5, 0.5, "No service UUIDs observed", ha="center", va="center", transform=axes[1].transAxes)
    axes[1].grid(alpha=0.25)

    fig.tight_layout()
    path = output_dir / "ble_analysis.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _render_sdr_heatmap(events: list[dict[str, Any]], output_dir: Path) -> Path | None:
    sweep_events = [event for event in events if str(event.get("protocol", "")) == "Spectrum Power"]
    if not sweep_events:
        return None

    parsed: list[tuple[datetime, float, float]] = []
    for event in sweep_events:
        timestamp = _parse_timestamp(event.get("timestamp"))
        frequency = _parse_mhz_channel(event.get("channel"))
        power = event.get("rssi_dbm")
        if timestamp is None or frequency is None or not isinstance(power, (int, float)):
            continue
        parsed.append((timestamp, frequency, float(power)))

    if not parsed:
        return None

    time_keys = sorted({item[0] for item in parsed})
    freq_keys = sorted({item[1] for item in parsed})
    time_index = {time_key: idx for idx, time_key in enumerate(time_keys)}
    freq_index = {freq_key: idx for idx, freq_key in enumerate(freq_keys)}

    matrix = np.full((len(time_keys), len(freq_keys)), np.nan, dtype=float)
    for timestamp, frequency, power in parsed:
        matrix[time_index[timestamp], freq_index[frequency]] = power

    fig, ax = plt.subplots(figsize=(12, 6))
    image = ax.imshow(matrix, aspect="auto", origin="lower", cmap="viridis")
    ax.set_title("RF sweep heatmap")
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Capture step")
    ax.set_xticks(range(len(freq_keys)))
    ax.set_xticklabels([f"{freq:.1f}" for freq in freq_keys], rotation=45, ha="right")
    fig.colorbar(image, ax=ax, label="Power (dB)")
    fig.tight_layout()

    path = output_dir / "rf_sweep_heatmap.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_mhz_channel(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    text = value.lower().replace("mhz", "").strip()
    try:
        return float(text)
    except ValueError:
        return None
