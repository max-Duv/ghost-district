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
        sensor_coverage=result["sensor_coverage"],
    )
    return field_path


def export_dynamic_state(result: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    trajectory_path = output_dir / "ghost_district_trajectories.json"
    observation_path = output_dir / "ghost_district_sensor_observations.json"

    with trajectory_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "trajectories": result["trajectories"],
                "sensor_tracks": result["sensor_tracks"],
            },
            handle,
            indent=2,
        )

    with observation_path.open("w", encoding="utf-8") as handle:
        json.dump(result["sensor_observations"], handle, indent=2)

    return {
        "trajectories": trajectory_path,
        "observations": observation_path,
    }


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


def render_collection_layout(result: dict[str, Any], summary: dict[str, Any], output_dir: Path) -> Path:
    coverage = np.max(result["sensor_coverage"], axis=0)
    energy = result["total_energy"][18]
    width_m = float(summary["config"]["width_m"])
    height_m = float(summary["config"]["height_m"])
    colors = {
        "Apartment BLE": "#3b82f6",
        "Delivery trackers": "#059669",
        "Vehicle hotspots": "#dc2626",
        "Interference": "#111827",
    }

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    coverage_image = axes[0].imshow(coverage, origin="lower", cmap="cividis")
    axes[0].set_title("Aggregate Sensor Coverage")
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    fig.colorbar(coverage_image, ax=axes[0], fraction=0.046, pad=0.04)

    for sensor in summary["sensors"]:
        track = result["sensor_tracks"][sensor["id"]]
        xs = [point["x"] for point in track]
        ys = [point["y"] for point in track]
        x_scale = coverage.shape[1] - 1
        y_scale = coverage.shape[0] - 1
        plot_x = [x / width_m * x_scale for x in xs]
        plot_y = [y / height_m * y_scale for y in ys]
        if sensor["kind"] == "mobile":
            axes[0].plot(plot_x, plot_y, color="white", linewidth=1.2, linestyle="--", alpha=0.9)
        axes[0].scatter(plot_x[0], plot_y[0], color="white", edgecolor="black", s=60, zorder=5)
        axes[0].text(plot_x[0] + 1.5, plot_y[0] + 1.5, sensor["label"], color="white", fontsize=8)

    energy_image = axes[1].imshow(energy, origin="lower", cmap="magma")
    axes[1].set_title("Agent Trajectories on Evening RF Field")
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    fig.colorbar(energy_image, ax=axes[1], fraction=0.046, pad=0.04)

    for agent in summary["agents"]:
        points = result["trajectories"][agent["id"]]
        xs = [point["x"] / width_m * (energy.shape[1] - 1) for point in points if point["active"]]
        ys = [point["y"] / height_m * (energy.shape[0] - 1) for point in points if point["active"]]
        if not xs:
            continue
        axes[1].plot(xs, ys, linewidth=1.4, color=colors.get(agent["emitter_type"], "#f8fafc"), alpha=0.92)

    for sensor in summary["sensors"]:
        first = result["sensor_tracks"][sensor["id"]][0]
        axes[1].scatter(
            first["x"] / width_m * (energy.shape[1] - 1),
            first["y"] / height_m * (energy.shape[0] - 1),
            color="white",
            edgecolor="black",
            s=60,
            zorder=6,
        )

    fig.tight_layout()
    layout_path = output_dir / "collection_layout.png"
    fig.savefig(layout_path, dpi=180)
    plt.close(fig)
    return layout_path


def render_sensor_timeline(summary: dict[str, Any], output_dir: Path) -> Path:
    hours = list(range(24))
    fig, axis = plt.subplots(figsize=(12, 4.6))

    for sensor in summary["sensors"]:
        counts = summary["sensor_hourly_observations"][sensor["id"]]
        axis.plot(hours, counts, linewidth=2.0, label=sensor["label"])

    axis.set_title("Hourly Collection Volume by Sensor")
    axis.set_xlabel("Hour")
    axis.set_ylabel("Observation count")
    axis.set_xticks(range(0, 24, 2))
    axis.grid(alpha=0.25)
    axis.legend(ncol=2)

    fig.tight_layout()
    timeline_path = output_dir / "sensor_observation_timeline.png"
    fig.savefig(timeline_path, dpi=180)
    plt.close(fig)
    return timeline_path


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

    lines.extend(["", "## Collection Layer", ""])
    for sensor in summary["sensors"]:
        total = summary["sensor_total_observations"][sensor["id"]]
        lines.append(f"- `{sensor['label']}` ({sensor['kind']}) captured {total} observations")

    report_path = output_dir / "rf_personality_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
