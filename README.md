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
- modular OTA capture backends with a PySide6 operations GUI

The generated district can support:

- SIGINT environment generation
- collection planning sandboxes
- deception and anomaly testing

## Project Layout

- `run_ghost_district.py`: command-line entry point
- `launch_capture_gui.py`: PySide6 OTA capture console
- `ghost_district/model.py`: district geometry, actors, temporal behavior, and RF synthesis
- `ghost_district/capture.py`: OTA capture backends and event logging
- `ghost_district/capture_render.py`: OTA capture plot generation
- `ghost_district/gui.py`: PySide6 GUI for live/replay capture control
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

## Model Notes

The simulator uses a synthetic city block with residential towers, storefront corridors, road traffic lanes, and urban canyon GPS degradation bands. Hourly activity is driven by actor routines, weather assumptions, density scaling, and seeded randomness so the environment is repeatable but still behavior-rich.

The extended model also synthesizes a trajectory layer:

- residents move between towers, work-like anchors, and nightlife nodes
- couriers loop through a delivery route during active service windows
- vehicles carry hotspot signatures on recurring roadway patterns
- pop-up interferers appear, dwell, and relocate based on event timing

The collection layer places fixed and mobile receivers into the district and scores whether each actor is observed based on range, geometry, and local interference conditions.
