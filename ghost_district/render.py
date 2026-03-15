from __future__ import annotations

from pathlib import Path
from typing import Any

import json

import matplotlib.pyplot as plt
import numpy as np


def export_summary(summary: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "ghost_district_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    return summary_path


def export_fields(result: dict[str, Any], output_dir: Path) -> Path:
    field_path = output_dir / "ghost_district_hourly_fields.npz"
    np.savez_compressed(
        field_path,
        total_energy=result["total_energy"],
        interference=result["interference"],
        gps_quality=result["gps_quality"],
    )
    return field_path


def render_timeline(summary: dict[str, Any], output_dir: Path) -> Path:
    hours = [entry["hour"] for entry in summary["hours"]]
    ble = [entry["component_means"]["ble"] for entry in summary["hours"]]
    wifi = [entry["component_means"]["wifi"] for entry in summary["hours"]]
    trackers = [entry["component_means"]["trackers"] for entry in summary["hours"]]
    vehicle = [entry["component_means"]["vehicle"] for entry in summary["hours"]]
    interference = [entry["component_means"]["interference"] for entry in summary["hours"]]
    gps_quality = [entry["gps_quality_mean"] for entry in summary["hours"]]

    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)

    axes[0].plot(hours, ble, label="Apartment BLE", linewidth=2.0)
    axes[0].plot(hours, wifi, label="Storefront Wi-Fi", linewidth=2.0)
    axes[0].plot(hours, trackers, label="Delivery trackers", linewidth=2.0)
    axes[0].plot(hours, vehicle, label="Vehicle hotspots", linewidth=2.0)
    axes[0].plot(hours, interference, label="Interference", linewidth=2.0, linestyle="--")
    axes[0].set_ylabel("Mean RF intensity")
    axes[0].set_title("Ghost District Hourly RF Behavior")
    axes[0].grid(alpha=0.25)
    axes[0].legend(ncol=3)

    axes[1].plot(hours, gps_quality, color="#202020", linewidth=2.2)
    axes[1].fill_between(hours, gps_quality, 1.0, color="#cc5c32", alpha=0.16)
    axes[1].set_ylim(0.0, 1.02)
    axes[1].set_ylabel("GPS quality")
    axes[1].set_xlabel("Hour")
    axes[1].grid(alpha=0.25)

    for axis in axes:
        axis.set_xticks(range(0, 24, 2))

    fig.tight_layout()
    timeline_path = output_dir / "rf_timeline.png"
    fig.savefig(timeline_path, dpi=180)
    plt.close(fig)
    return timeline_path


def render_snapshots(result: dict[str, Any], hours: list[int], output_dir: Path) -> list[Path]:
    image_paths: list[Path] = []

    for hour in hours:
        total_energy = result["total_energy"][hour]
        interference = result["interference"][hour]
        gps_quality = result["gps_quality"][hour]

        fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
        panels = [
            (total_energy, "Total RF energy", "magma"),
            (interference, "Interference zones", "inferno"),
            (gps_quality, "GPS quality", "viridis"),
        ]

        for axis, (field, title, cmap) in zip(axes, panels, strict=True):
            image = axis.imshow(field, origin="lower", cmap=cmap)
            axis.set_title(title)
            axis.set_xticks([])
            axis.set_yticks([])
            fig.colorbar(image, ax=axis, fraction=0.046, pad=0.04)

        fig.suptitle(f"Ghost District Snapshot Hour {hour:02d}")
        fig.tight_layout()
        image_path = output_dir / f"district_snapshot_{hour:02d}.png"
        fig.savefig(image_path, dpi=180)
        plt.close(fig)
        image_paths.append(image_path)

    return image_paths


def export_report(summary: dict[str, Any], output_dir: Path) -> Path:
    lines = [
        "# Ghost District RF Personality Report",
        "",
        summary["title"],
        "",
        f"Weather assumption: `{summary['config']['weather']}`",
        f"Density scale: `{summary['config']['density_scale']}`",
        f"Seed: `{summary['config']['seed']}`",
        "",
        "## Pop-up Interference Events",
        "",
    ]

    for event in summary["popup_events"]:
        lines.append(
            f"- `{event['label']}` at ({event['x']:.0f}, {event['y']:.0f}) from hour {event['start_hour']:02d} to {event['end_hour']:02d}"
        )

    lines.extend(["", "## Hourly Personalities", ""])
    for entry in summary["hours"]:
        lines.append(
            f"- `{entry['hour']:02d}:00` {entry['personality']} | dominant: {entry['dominant_emitter']} | GPS quality {entry['gps_quality_mean']:.2f}"
        )
        lines.append(f"  {entry['narrative']}")

    report_path = output_dir / "rf_personality_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
