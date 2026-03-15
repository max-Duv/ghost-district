# Ghost District

**Ghost District: Behavioral RF Terrain Synthesis for Urban Collection Environments**

Ghost District builds a synthetic urban block where RF activity reflects habits, routines, and disruption instead of only link budgets. The simulator synthesizes a 24-hour district story with:

- apartment BLE chatter
- storefront Wi-Fi bursts
- delivery tracker movement
- vehicle hotspot traffic
- GPS degradation corridors
- pop-up interference zones
- daytime versus nighttime RF personality shifts
- explicit agent trajectories for representative actors
- fixed and mobile collection sensors with observation logs
- modular OTA capture backends with a PyQt6 operations GUI

The generated district can support:

- SIGINT environment generation
- collection planning sandboxes
- deception and anomaly testing

## Project Layout

- `run_ghost_district.py`: command-line entry point
- `launch_capture_gui.py`: PyQt6 OTA capture console
  - includes a mission dashboard tab for reviewing placement, route, emitter, window, and interference outputs
- `ghost_district/model.py`: district geometry, actors, temporal behavior, and RF synthesis
- `ghost_district/capture.py`: OTA capture backends and event logging
- `ghost_district/capture_render.py`: OTA capture plot generation
- `ghost_district/gui.py`: PyQt6 GUI for live/replay capture control
- `ghost_district/mission.py`: mission logic scoring and inference
- `ghost_district/mission_render.py`: mission output plots and reports
- `ghost_district/render.py`: plots and export helpers
- `captures/`: saved OTA capture logs
- `outputs/`: generated data products

## Quick Start

From `C:\Users\maxfd\OneDrive\Documents\MATLAB\PERSONAL-SP-26\GhostDistrict`:

```bash
python run_ghost_district.py
```

Optional parameters:

```bash
python run_ghost_district.py --weather rain --density 1.25 --seed 77 --snapshots 7 12 18 23
```

Launch the capture GUI:

```bash
python launch_capture_gui.py
```

Typical combined workflow:

```bash
python run_ghost_district.py --weather rain --density 1.15 --seed 41 --snapshots 7 12 18 22
python launch_capture_gui.py
```

The GUI now has two primary views:

- `Capture`: live/replay OTA collection, waveform monitoring, event feed, and capture plot generation
- `Mission`: collector rankings, route tradeoffs, emitter assessment, collection windows, interference actions, and embedded mission plots loaded from `outputs/`

## Outputs

Each run writes into `outputs/`:

- `ghost_district_summary.json`: scenario metadata and hourly narrative summaries
- `ghost_district_hourly_fields.npz`: raster fields for RF energy, interference, GPS quality, and sensor coverage
- `ghost_district_trajectories.json`: per-actor and per-sensor sampled tracks
- `ghost_district_sensor_observations.json`: sensor detections across the day
- `rf_timeline.png`: district-level temporal behavior
- `collection_layout.png`: trajectory and sensor placement view
- `sensor_observation_timeline.png`: hourly collection volume by sensor
- `district_snapshot_XX.png`: selected hour snapshots
- `rf_personality_report.md`: compact narrative report
- `mission_logic_summary.json`: collector placement, route, emitter, and disruption analysis
- `mission_logic_report.md`: human-readable mission recommendations
- `mission_collector_placements.png`: top placement recommendations
- `mission_route_tradeoff.png`: route opportunity versus exposure
- `mission_state_timeline.png`: disruption, staging, panic, and covert movement inference
- `mission_interference_actions.png`: small interference actions ranked by impact

Saved capture sessions write into `captures/` as JSON logs with session metadata plus captured events. Each saved session also writes a sibling `*_plots/` bundle with capture graphics.

## OTA Capture Backends

The GUI exposes multiple capture choices:

- `Ghost District Playback`: replays `outputs/ghost_district_sensor_observations.json` as a simulated OTA feed
- `BLE Adapter`: performs live BLE advertisement capture through `bleak`
- `RTL-SDR Sweep`: performs a passive power sweep across a configured RF range when `pyrtlsdr` and hardware are available
- `JSON Replay`: replays any prior capture log or raw observation JSON

The GUI lets you choose the backend, set duration, filter to a specific simulated sensor, configure SDR sweep ranges, and save the resulting event log to disk.

Saved OTA sessions automatically render:

- `capture_overview.png`: event cadence and signal-strength distribution
- `capture_mix.png`: top sources and protocol mix
- `ble_analysis.png`: BLE RSSI scatter and top service UUIDs, when BLE traffic is present
- `rf_sweep_heatmap.png`: time-frequency power map, when SDR sweep data is present

The live GUI also includes a mode-aware waveform panel:

- `Ghost District Playback`: scrolling simulated collection envelope
- `BLE Adapter`: live BLE RSSI waveform
- `RTL-SDR Sweep`: live frequency-power sweep profile
- `JSON Replay`: scrolling replay signal envelope

The `Mission` tab reads:

- `outputs/mission_logic_summary.json`
- `outputs/mission_collector_placements.png`
- `outputs/mission_route_tradeoff.png`
- `outputs/mission_state_timeline.png`
- `outputs/mission_interference_actions.png`

## Model Notes

The simulator uses a synthetic city block with residential towers, storefront corridors, road traffic lanes, and urban canyon GPS degradation bands. Hourly activity is driven by actor routines, weather assumptions, density scaling, and seeded randomness so the environment is repeatable but still behavior-rich.

The extended model also synthesizes a trajectory layer:

- residents move between towers, work-like anchors, and nightlife nodes
- couriers loop through a delivery route during active service windows
- vehicles carry hotspot signatures on recurring roadway patterns
- pop-up interferers appear, dwell, and relocate based on event timing

The collection layer places fixed and mobile receivers into the district and scores whether each actor is observed based on range, geometry, and local interference conditions.
