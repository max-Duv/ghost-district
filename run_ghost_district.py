from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from ghost_district import DistrictConfig, GhostDistrictSimulator
from ghost_district.mission import MissionLogicEngine
from ghost_district.mission_render import (
    export_mission_report,
    export_mission_summary,
    render_collector_placements,
    render_interference_actions,
    render_route_tradeoff,
    render_state_timeline,
)
from ghost_district.render import (
    export_dynamic_state,
    export_fields,
    export_report,
    export_summary,
    render_collection_layout,
    render_sensor_timeline,
    render_snapshots,
    render_timeline,
)


def parse_args() -> ArgumentParser:
    parser = ArgumentParser(
        description="Generate a behavioral RF city block with hourly routines, hotspots, and contested spectrum."
    )
    parser.add_argument("--weather", default="clear", choices=["clear", "rain", "fog", "storm"])
    parser.add_argument("--density", default=1.0, type=float, help="Actor density multiplier.")
    parser.add_argument("--seed", default=26, type=int, help="Random seed for repeatable scenario synthesis.")
    parser.add_argument(
        "--snapshots",
        nargs="*",
        type=int,
        default=[6, 12, 18, 23],
        help="Hours to render as PNG district snapshots.",
    )
    return parser


def main() -> None:
    parser = parse_args()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    output_dir = project_root / "outputs"

    config = DistrictConfig(
        weather=args.weather,
        density_scale=max(0.2, args.density),
        seed=args.seed,
    )
    simulator = GhostDistrictSimulator(config)
    result = simulator.run_day()
    summary = result["summary"]

    summary_path = export_summary(summary, output_dir)
    field_path = export_fields(result, output_dir)
    dynamic_paths = export_dynamic_state(result, output_dir)
    timeline_path = render_timeline(summary, output_dir)
    collection_layout_path = render_collection_layout(result, summary, output_dir)
    sensor_timeline_path = render_sensor_timeline(summary, output_dir)
    snapshot_hours = [hour for hour in args.snapshots if 0 <= hour <= 23]
    snapshot_paths = render_snapshots(result, snapshot_hours, output_dir)
    report_path = export_report(summary, output_dir)

    mission_summary = MissionLogicEngine(result).analyze()
    mission_summary_path = export_mission_summary(mission_summary, output_dir)
    mission_report_path = export_mission_report(mission_summary, output_dir)
    placement_plot_path = render_collector_placements(mission_summary, output_dir)
    route_plot_path = render_route_tradeoff(mission_summary, output_dir)
    state_plot_path = render_state_timeline(mission_summary, output_dir)
    action_plot_path = render_interference_actions(mission_summary, output_dir)

    print(summary["title"])
    print(f"Summary: {summary_path}")
    print(f"Fields: {field_path}")
    print(f"Trajectories: {dynamic_paths['trajectories']}")
    print(f"Observations: {dynamic_paths['observations']}")
    print(f"Timeline: {timeline_path}")
    print(f"Collection layout: {collection_layout_path}")
    print(f"Sensor timeline: {sensor_timeline_path}")
    print(f"Report: {report_path}")
    print(f"Mission summary: {mission_summary_path}")
    print(f"Mission report: {mission_report_path}")
    print(f"Placement plot: {placement_plot_path}")
    print(f"Route tradeoff plot: {route_plot_path}")
    print(f"State timeline plot: {state_plot_path}")
    print(f"Interference impact plot: {action_plot_path}")
    if snapshot_paths:
        print("Snapshots:")
        for path in snapshot_paths:
            print(f"  - {path}")


if __name__ == "__main__":
    main()
