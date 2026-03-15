from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


def export_mission_summary(mission_summary: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "mission_logic_summary.json"
    path.write_text(json.dumps(mission_summary, indent=2), encoding="utf-8")
    return path


def render_collector_placements(mission_summary: dict[str, Any], output_dir: Path) -> Path:
    placements = mission_summary["collector_placements"][:6]
    fig, axis = plt.subplots(figsize=(7.5, 7.0))
    xs = [item["x"] for item in placements]
    ys = [item["y"] for item in placements]
    scores = [item["placement_score"] for item in placements]
    scatter = axis.scatter(xs, ys, c=scores, s=240, cmap="plasma", edgecolors="black")
    for item in placements:
        axis.text(item["x"] + 6.0, item["y"] + 6.0, item["label"], fontsize=9)
    axis.set_xlim(0, 420)
    axis.set_ylim(0, 420)
    axis.set_title("Collector Placement Recommendations")
    axis.set_xlabel("X (m)")
    axis.set_ylabel("Y (m)")
    axis.grid(alpha=0.25)
    fig.colorbar(scatter, ax=axis, label="Placement score")
    fig.tight_layout()
    path = output_dir / "mission_collector_placements.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def render_route_tradeoff(mission_summary: dict[str, Any], output_dir: Path) -> Path:
    routes = mission_summary["route_assessment"]
    fig, axis = plt.subplots(figsize=(8.4, 6.0))
    for route in routes:
        axis.scatter(route["exposure"], route["collection_opportunity"], s=120, color="#3b82f6")
        axis.text(route["exposure"] + 0.02, route["collection_opportunity"] + 0.02, route["label"], fontsize=9)
    axis.set_title("Route Opportunity vs Exposure")
    axis.set_xlabel("Exposure")
    axis.set_ylabel("Collection opportunity")
    axis.grid(alpha=0.25)
    fig.tight_layout()
    path = output_dir / "mission_route_tradeoff.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def render_state_timeline(mission_summary: dict[str, Any], output_dir: Path) -> Path:
    states = mission_summary["state_timeline"]
    colors = {
        "routine": "#94a3b8",
        "disruption": "#ef4444",
        "panic": "#f97316",
        "staging": "#3b82f6",
        "covert movement": "#8b5cf6",
    }
    hours = [item["hour"] for item in states]
    confidence = [item["confidence"] for item in states]
    color_values = [colors[item["state"]] for item in states]

    fig, axis = plt.subplots(figsize=(11.5, 4.6))
    axis.bar(hours, confidence, color=color_values, width=0.82)
    for item in states:
        axis.text(item["hour"], item["confidence"] + 0.015, item["state"], rotation=90, ha="center", va="bottom", fontsize=8)
    axis.set_ylim(0.0, 1.0)
    axis.set_xticks(range(24))
    axis.set_title("Mission State Timeline")
    axis.set_xlabel("Hour")
    axis.set_ylabel("Confidence")
    axis.grid(alpha=0.2, axis="y")
    fig.tight_layout()
    path = output_dir / "mission_state_timeline.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def render_interference_actions(mission_summary: dict[str, Any], output_dir: Path) -> Path:
    actions = mission_summary["interference_actions"][:6]
    labels = [item["label"] for item in actions]
    scores = [item["impact_score"] for item in actions]
    fig, axis = plt.subplots(figsize=(9.0, 5.2))
    axis.barh(labels[::-1], scores[::-1], color="#ef4444")
    axis.set_title("Small Interference Actions with Outsized Impact")
    axis.set_xlabel("Impact score")
    axis.grid(alpha=0.25, axis="x")
    fig.tight_layout()
    path = output_dir / "mission_interference_actions.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def export_mission_report(mission_summary: dict[str, Any], output_dir: Path) -> Path:
    lines = [
        "# Ghost District Mission Logic Report",
        "",
        "## Top Collector Placements",
        "",
    ]
    for item in mission_summary["collector_placements"][:5]:
        lines.append(
            f"- `{item['label']}` score {item['placement_score']:.2f} | opportunity {item['collection_opportunity']:.2f} | exposure {item['exposure']:.2f}"
        )

    lines.extend(["", "## Best Routes", ""])
    for item in mission_summary["route_assessment"][:4]:
        lines.append(
            f"- `{item['label']}` route score {item['route_score']:.2f} | opportunity {item['collection_opportunity']:.2f} | exposure {item['exposure']:.2f}"
        )

    lines.extend(["", "## Mission-Relevant Emitters", ""])
    for item in mission_summary["emitter_assessment"][:5]:
        lines.append(
            f"- `{item['label']}` relevance {item['mission_relevance']:.2f} | ambiguity {item['ambiguity']:.2f} | deception {item['deception']:.2f} | tags: {', '.join(item['tags'])}"
        )

    lines.extend(["", "## Collection Windows", ""])
    for item in mission_summary["collection_windows"]:
        lines.append(
            f"- `{item['hour']:02d}:00` window score {item['window_score']:.2f} | state {item['state']} | route {item['preferred_route']}"
        )

    path = output_dir / "mission_logic_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
