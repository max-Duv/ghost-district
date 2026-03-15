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

The generated district can support:

- SIGINT environment generation
- collection planning sandboxes
- deception and anomaly testing

## Project Layout

- `run_ghost_district.py`: command-line entry point
- `ghost_district/model.py`: district geometry, actors, temporal behavior, and RF synthesis
- `ghost_district/render.py`: plots and export helpers
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

## Model Notes

The simulator uses a synthetic city block with residential towers, storefront corridors, road traffic lanes, and urban canyon GPS degradation bands. Hourly activity is driven by actor routines, weather assumptions, density scaling, and seeded randomness so the environment is repeatable but still behavior-rich.

The extended model also synthesizes a trajectory layer:

- residents move between towers, work-like anchors, and nightlife nodes
- couriers loop through a delivery route during active service windows
- vehicles carry hotspot signatures on recurring roadway patterns
- pop-up interferers appear, dwell, and relocate based on event timing

The collection layer places fixed and mobile receivers into the district and scores whether each actor is observed based on range, geometry, and local interference conditions.
