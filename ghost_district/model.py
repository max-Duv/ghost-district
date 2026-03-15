from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import numpy as np


@dataclass
class WeatherProfile:
    name: str
    ble_attenuation: float
    wifi_attenuation: float
    gps_penalty: float
    vehicle_bias: float
    pedestrian_bias: float
    interference_volatility: float


WEATHER_PROFILES: dict[str, WeatherProfile] = {
    "clear": WeatherProfile("clear", 1.00, 1.00, 0.04, 1.00, 1.00, 1.00),
    "rain": WeatherProfile("rain", 0.92, 0.88, 0.10, 0.92, 0.90, 1.10),
    "fog": WeatherProfile("fog", 0.96, 0.94, 0.12, 0.95, 0.95, 1.05),
    "storm": WeatherProfile("storm", 0.86, 0.78, 0.22, 0.82, 0.76, 1.35),
}


@dataclass
class DistrictConfig:
    width_m: float = 420.0
    height_m: float = 420.0
    grid_size: int = 90
    density_scale: float = 1.0
    weather: str = "clear"
    seed: int = 26
    time_step_minutes: int = 10


class GhostDistrictSimulator:
    def __init__(self, config: DistrictConfig) -> None:
        if config.weather not in WEATHER_PROFILES:
            valid = ", ".join(sorted(WEATHER_PROFILES))
            raise ValueError(f"Unsupported weather '{config.weather}'. Valid options: {valid}")

        self.config = config
        self.weather = WEATHER_PROFILES[config.weather]
        self.rng = np.random.default_rng(config.seed)

        self.x = np.linspace(0.0, config.width_m, config.grid_size)
        self.y = np.linspace(0.0, config.height_m, config.grid_size)
        self.xx, self.yy = np.meshgrid(self.x, self.y)

        self.residential_nodes = [
            {"name": "Northwest Lofts", "x": 100.0, "y": 315.0, "residents": 180},
            {"name": "Northeast Lofts", "x": 315.0, "y": 320.0, "residents": 165},
            {"name": "Southwest Tower", "x": 115.0, "y": 120.0, "residents": 210},
            {"name": "Southeast Tower", "x": 320.0, "y": 115.0, "residents": 195},
        ]
        self.storefronts = [
            {"name": "Cafe Row West", "x": 78.0, "y": 210.0, "weight": 1.05},
            {"name": "Arcade Strip", "x": 145.0, "y": 208.0, "weight": 1.10},
            {"name": "Market Corner", "x": 210.0, "y": 215.0, "weight": 1.25},
            {"name": "Pharmacy Plaza", "x": 278.0, "y": 212.0, "weight": 0.90},
            {"name": "Takeout Cluster", "x": 348.0, "y": 205.0, "weight": 1.15},
        ]
        self.vehicle_lane_y = [95.0, 208.0, 332.0]
        self.delivery_route = np.array(
            [
                [42.0, 208.0],
                [96.0, 332.0],
                [210.0, 355.0],
                [360.0, 260.0],
                [342.0, 95.0],
                [205.0, 58.0],
                [82.0, 112.0],
            ]
        )
        self.gps_corridors = [
            {"center_x": 210.0, "width": 46.0, "strength": 0.48},
            {"center_y": 208.0, "width": 36.0, "strength": 0.32},
        ]
        self.popup_events = self._build_popup_events()
        self.sensors = self._build_sensors()
        self.agent_templates = self._build_agent_templates()

    def _build_popup_events(self) -> list[dict[str, Any]]:
        anchors = [(132.0, 210.0), (292.0, 150.0), (260.0, 322.0), (118.0, 96.0)]
        labels = [
            "counter-surveillance sweep",
            "pirate broadcast stall",
            "ad hoc jammer van",
            "festival uplink truck",
        ]
        events: list[dict[str, Any]] = []
        order = self.rng.permutation(len(anchors))
        for idx in order[:3]:
            start = int(self.rng.integers(9, 21))
            duration = int(self.rng.integers(2, 5))
            radius = float(self.rng.uniform(18.0, 34.0))
            amplitude = float(self.rng.uniform(0.9, 1.5)) * self.weather.interference_volatility
            events.append(
                {
                    "label": labels[idx],
                    "x": anchors[idx][0],
                    "y": anchors[idx][1],
                    "start_hour": start,
                    "end_hour": min(23, start + duration),
                    "radius": radius,
                    "amplitude": amplitude,
                }
            )
        return sorted(events, key=lambda event: event["start_hour"])

    def _build_sensors(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "roof-west",
                "label": "Roof West",
                "kind": "fixed",
                "role": "Wide-area rooftop collector",
                "x": 78.0,
                "y": 304.0,
                "height_m": 26.0,
                "range_m": 200.0,
                "gain": 1.28,
                "threshold": 0.17,
            },
            {
                "id": "market-pole",
                "label": "Market Pole",
                "kind": "fixed",
                "role": "Street-level retail corridor collector",
                "x": 218.0,
                "y": 214.0,
                "height_m": 8.0,
                "range_m": 135.0,
                "gain": 1.12,
                "threshold": 0.14,
            },
            {
                "id": "south-lobby",
                "label": "South Lobby",
                "kind": "fixed",
                "role": "Indoor-adjacent residential collector",
                "x": 314.0,
                "y": 118.0,
                "height_m": 5.0,
                "range_m": 110.0,
                "gain": 0.98,
                "threshold": 0.12,
            },
            {
                "id": "mobile-collector",
                "label": "Mobile Collector",
                "kind": "mobile",
                "role": "Patrol vehicle collection node",
                "height_m": 2.5,
                "range_m": 150.0,
                "gain": 1.05,
                "threshold": 0.13,
                "route": [
                    [42.0, 90.0],
                    [378.0, 92.0],
                    [382.0, 208.0],
                    [294.0, 334.0],
                    [76.0, 332.0],
                    [40.0, 208.0],
                ],
                "cycle_minutes": 150,
            },
        ]

    def _build_agent_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "resident-alpha",
                "label": "Resident Alpha",
                "role": "Resident commuter",
                "signature": "ble",
                "emitter_type": "Apartment BLE",
                "tx_power": 0.58,
                "mode": "schedule",
                "schedule": [
                    [0, 100.0, 315.0, 0.55, "sleep"],
                    [390, 100.0, 315.0, 0.78, "wake"],
                    [455, 145.0, 208.0, 0.86, "commute"],
                    [530, 145.0, 208.0, 0.92, "office"],
                    [720, 78.0, 210.0, 1.00, "lunch"],
                    [790, 145.0, 208.0, 0.92, "office"],
                    [1080, 100.0, 315.0, 0.98, "home"],
                    [1430, 100.0, 315.0, 0.58, "sleep"],
                ],
            },
            {
                "id": "resident-bravo",
                "label": "Resident Bravo",
                "role": "Resident-nightlife crossover",
                "signature": "ble",
                "emitter_type": "Apartment BLE",
                "tx_power": 0.62,
                "mode": "schedule",
                "schedule": [
                    [0, 320.0, 115.0, 0.50, "sleep"],
                    [470, 320.0, 115.0, 0.76, "wake"],
                    [560, 278.0, 212.0, 0.88, "day errand"],
                    [700, 210.0, 215.0, 0.94, "retail stop"],
                    [980, 348.0, 205.0, 1.00, "late food pickup"],
                    [1140, 320.0, 115.0, 0.92, "home"],
                    [1260, 145.0, 208.0, 0.97, "night arcade"],
                    [1410, 320.0, 115.0, 0.58, "return"],
                ],
            },
            {
                "id": "courier-one",
                "label": "Courier One",
                "role": "Day courier",
                "signature": "trackers",
                "emitter_type": "Delivery trackers",
                "tx_power": 0.52,
                "mode": "route_loop",
                "route": self.delivery_route.tolist(),
                "start_minute": 480,
                "end_minute": 1320,
                "cycle_minutes": 118,
                "activity": 0.96,
                "idle_point": [84.0, 112.0],
            },
            {
                "id": "courier-two",
                "label": "Courier Two",
                "role": "Midday courier",
                "signature": "trackers",
                "emitter_type": "Delivery trackers",
                "tx_power": 0.48,
                "mode": "route_loop",
                "route": self.delivery_route[::-1].tolist(),
                "start_minute": 630,
                "end_minute": 1260,
                "cycle_minutes": 102,
                "activity": 0.92,
                "idle_point": [342.0, 95.0],
            },
            {
                "id": "commuter-car",
                "label": "Commuter Car",
                "role": "Recurring hotspot vehicle",
                "signature": "vehicle",
                "emitter_type": "Vehicle hotspots",
                "tx_power": 0.68,
                "mode": "route_loop",
                "route": [[0.0, 208.0], [420.0, 208.0]],
                "start_minute": 330,
                "end_minute": 1260,
                "cycle_minutes": 58,
                "activity": 1.00,
                "idle_point": [10.0, 208.0],
            },
            {
                "id": "night-rideshare",
                "label": "Night Rideshare",
                "role": "Evening mobile hotspot",
                "signature": "vehicle",
                "emitter_type": "Vehicle hotspots",
                "tx_power": 0.64,
                "mode": "route_loop",
                "route": [[0.0, 95.0], [420.0, 95.0], [420.0, 332.0], [0.0, 332.0]],
                "start_minute": 1020,
                "end_minute": 1430,
                "cycle_minutes": 70,
                "activity": 0.94,
                "idle_point": [28.0, 95.0],
            },
            {
                "id": "popup-emitter",
                "label": "Popup Emitter",
                "role": "Relocating interference source",
                "signature": "interference",
                "emitter_type": "Interference",
                "tx_power": 0.88,
                "mode": "popup",
            },
        ]

    def run_day(self) -> dict[str, Any]:
        total_energy_stack = []
        interference_stack = []
        gps_quality_stack = []
        hourly_metrics = []

        for hour in range(24):
            snapshot = self._simulate_hour(hour)
            total_energy_stack.append(snapshot["total_energy"])
            interference_stack.append(snapshot["interference"])
            gps_quality_stack.append(snapshot["gps_quality"])
            hourly_metrics.append(snapshot["metrics"])

        total_energy = np.stack(total_energy_stack, axis=0)
        interference = np.stack(interference_stack, axis=0)
        gps_quality = np.stack(gps_quality_stack, axis=0)
        movement = self._simulate_agents_and_sensors(interference)

        summary = {
            "title": "Ghost District: Behavioral RF Terrain Synthesis for Urban Collection Environments",
            "config": asdict(self.config),
            "weather_profile": asdict(self.weather),
            "popup_events": self.popup_events,
            "hours": hourly_metrics,
            "field_shape": [24, self.config.grid_size, self.config.grid_size],
            "trajectory_step_minutes": self.config.time_step_minutes,
            "agents": movement["agent_roster"],
            "sensors": movement["sensor_roster"],
            "sensor_hourly_observations": movement["sensor_hourly_observations"],
            "sensor_total_observations": movement["sensor_total_observations"],
            "component_descriptions": {
                "ble": "Apartment and pedestrian BLE chatter density",
                "wifi": "Storefront and hotspot Wi-Fi burst activity",
                "trackers": "Delivery tracker presence and mobility signatures",
                "vehicle": "Vehicle hotspot intensity on street lanes",
                "interference": "Intentional or incidental RF interference energy",
                "gps_quality": "Normalized GPS quality score after urban canyon and interference penalties",
            },
        }
        return {
            "summary": summary,
            "total_energy": total_energy,
            "interference": interference,
            "gps_quality": gps_quality,
            "trajectories": movement["trajectories"],
            "sensor_observations": movement["sensor_observations"],
            "sensor_tracks": movement["sensor_tracks"],
            "sensor_coverage": movement["sensor_coverage"],
        }

    def _simulate_hour(self, hour: int) -> dict[str, Any]:
        ble = self._apartment_ble(hour)
        wifi = self._storefront_wifi(hour)
        trackers = self._delivery_trackers(hour)
        vehicle = self._vehicle_hotspots(hour)
        interference, active_events = self._interference(hour)
        gps_quality = self._gps_quality(hour, interference)

        total_energy = ble + wifi + trackers + vehicle + 1.25 * interference
        intensity_score = float(np.mean(total_energy))

        metrics = {
            "hour": hour,
            "period_label": self._period_label(hour),
            "personality": self._personality(hour, ble, wifi, trackers, vehicle, interference),
            "narrative": self._narrative(hour, active_events),
            "dominant_emitter": self._dominant_emitter(
                {
                    "Apartment BLE": ble,
                    "Storefront Wi-Fi": wifi,
                    "Delivery trackers": trackers,
                    "Vehicle hotspots": vehicle,
                    "Interference": interference,
                }
            ),
            "district_energy_mean": round(intensity_score, 4),
            "component_means": {
                "ble": round(float(np.mean(ble)), 4),
                "wifi": round(float(np.mean(wifi)), 4),
                "trackers": round(float(np.mean(trackers)), 4),
                "vehicle": round(float(np.mean(vehicle)), 4),
                "interference": round(float(np.mean(interference)), 4),
            },
            "gps_quality_mean": round(float(np.mean(gps_quality)), 4),
            "gps_degradation_mean": round(float(1.0 - np.mean(gps_quality)), 4),
            "active_popup_events": active_events,
        }

        return {
            "total_energy": total_energy,
            "interference": interference,
            "gps_quality": gps_quality,
            "metrics": metrics,
        }

    def _apartment_ble(self, hour: int) -> np.ndarray:
        layer = np.zeros_like(self.xx)
        density = self.config.density_scale * self.weather.pedestrian_bias
        wake = self._gaussian_peak(hour, 7.0, 1.3, 1.05)
        return_home = self._gaussian_peak(hour, 20.0, 2.2, 1.25)
        sleep_tail = self._gaussian_peak(hour, 1.0, 2.8, 0.55)
        activity = 0.18 + wake + return_home + sleep_tail

        for node in self.residential_nodes:
            amplitude = density * activity * (node["residents"] / 180.0)
            amplitude *= float(self.rng.normal(1.0, 0.06))
            layer += self._ellipse(node["x"], node["y"], 28.0, 36.0, amplitude)
        return np.clip(layer * self.weather.ble_attenuation, 0.0, None)

    def _storefront_wifi(self, hour: int) -> np.ndarray:
        layer = np.zeros_like(self.xx)
        density = self.config.density_scale
        open_hours = self._window(hour, 7, 22)
        lunch = self._gaussian_peak(hour, 12.0, 1.0, 1.05)
        after_work = self._gaussian_peak(hour, 18.5, 1.6, 0.92)
        base = 0.08 + 0.65 * open_hours + lunch + after_work

        for storefront in self.storefronts:
            burstiness = float(np.clip(self.rng.normal(1.0, 0.22), 0.5, 1.6))
            amplitude = density * storefront["weight"] * base * burstiness
            layer += self._ellipse(storefront["x"], storefront["y"], 24.0, 18.0, amplitude)
        return np.clip(layer * self.weather.wifi_attenuation, 0.0, None)

    def _delivery_trackers(self, hour: int) -> np.ndarray:
        layer = np.zeros_like(self.xx)
        delivery_peak = (
            self._gaussian_peak(hour, 10.5, 1.5, 0.95)
            + self._gaussian_peak(hour, 13.0, 1.3, 0.8)
            + self._gaussian_peak(hour, 18.0, 1.6, 1.15)
        )
        tracker_count = max(1, int(round((3 + 7 * delivery_peak) * self.config.density_scale)))

        for idx in range(tracker_count):
            phase = (hour + 0.7 * idx) / 24.0
            x, y = self._interpolate_route(phase)
            jitter_x = float(self.rng.normal(0.0, 8.0))
            jitter_y = float(self.rng.normal(0.0, 8.0))
            amplitude = float(self.rng.uniform(0.28, 0.55)) * (1.0 + delivery_peak)
            layer += self._ellipse(x + jitter_x, y + jitter_y, 9.0, 9.0, amplitude)
        return np.clip(layer, 0.0, None)

    def _vehicle_hotspots(self, hour: int) -> np.ndarray:
        layer = np.zeros_like(self.xx)
        commute = self._gaussian_peak(hour, 8.0, 1.4, 1.2) + self._gaussian_peak(hour, 17.5, 1.8, 1.45)
        nightlife = self._gaussian_peak(hour, 22.0, 1.4, 0.75)
        traffic = (0.18 + commute + nightlife) * self.config.density_scale * self.weather.vehicle_bias
        vehicle_count = max(2, int(round(4 + 9 * traffic)))

        for idx in range(vehicle_count):
            lane_y = self.vehicle_lane_y[idx % len(self.vehicle_lane_y)]
            x = ((hour * 23.0) + idx * 31.0) % self.config.width_m
            x += float(self.rng.normal(0.0, 10.0))
            y = lane_y + float(self.rng.normal(0.0, 4.5))
            amplitude = float(self.rng.uniform(0.25, 0.6)) * (1.0 + traffic)
            layer += self._ellipse(x, y, 16.0, 7.0, amplitude)
        return np.clip(layer * self.weather.wifi_attenuation, 0.0, None)

    def _interference(self, hour: int) -> tuple[np.ndarray, list[str]]:
        layer = np.zeros_like(self.xx)
        active_events: list[str] = []

        base_noise = 0.018 * self.weather.interference_volatility
        layer += base_noise

        for event in self.popup_events:
            if event["start_hour"] <= hour <= event["end_hour"]:
                active_events.append(event["label"])
                layer += self._ellipse(
                    event["x"],
                    event["y"],
                    event["radius"],
                    event["radius"] * 0.8,
                    event["amplitude"],
                )
        return np.clip(layer, 0.0, None), active_events

    def _gps_quality(self, hour: int, interference: np.ndarray) -> np.ndarray:
        degradation = np.full_like(self.xx, 0.06 + self.weather.gps_penalty)
        for corridor in self.gps_corridors:
            if "center_x" in corridor:
                dx = np.abs(self.xx - corridor["center_x"])
                degradation += corridor["strength"] * np.exp(-(dx**2) / (2.0 * corridor["width"] ** 2))
            if "center_y" in corridor:
                dy = np.abs(self.yy - corridor["center_y"])
                degradation += corridor["strength"] * np.exp(-(dy**2) / (2.0 * corridor["width"] ** 2))

        rush_penalty = 0.07 * (
            self._gaussian_peak(hour, 8.0, 1.5, 1.0) + self._gaussian_peak(hour, 18.0, 1.8, 0.9)
        )
        degradation += rush_penalty
        degradation += 0.28 * np.tanh(interference)
        quality = 1.0 - degradation
        return np.clip(quality, 0.0, 1.0)

    def _simulate_agents_and_sensors(self, interference_stack: np.ndarray) -> dict[str, Any]:
        minutes = list(range(0, 24 * 60, self.config.time_step_minutes))
        trajectories: dict[str, list[dict[str, Any]]] = {agent["id"]: [] for agent in self.agent_templates}
        sensor_tracks: dict[str, list[dict[str, Any]]] = {sensor["id"]: [] for sensor in self.sensors}
        sensor_observations: list[dict[str, Any]] = []
        sensor_hourly_counts = {sensor["id"]: [0 for _ in range(24)] for sensor in self.sensors}
        sensor_total_counts = {sensor["id"]: 0 for sensor in self.sensors}

        for minute in minutes:
            hour = minute // 60
            agent_states = [self._sample_agent_state(agent, minute) for agent in self.agent_templates]

            for state in agent_states:
                trajectories[state["id"]].append(
                    {
                        "minute": minute,
                        "hour": hour,
                        "x": round(state["x"], 3),
                        "y": round(state["y"], 3),
                        "activity": round(state["activity"], 3),
                        "state": state["state"],
                        "active": state["active"],
                    }
                )

            for sensor in self.sensors:
                sensor_x, sensor_y = self._sensor_position(sensor, minute)
                sensor_tracks[sensor["id"]].append(
                    {
                        "minute": minute,
                        "hour": hour,
                        "x": round(sensor_x, 3),
                        "y": round(sensor_y, 3),
                    }
                )

                for state in agent_states:
                    if not state["active"]:
                        continue

                    distance = math.hypot(sensor_x - state["x"], sensor_y - state["y"])
                    if distance > sensor["range_m"]:
                        continue

                    field_penalty = 1.0 + 1.2 * self._sample_field(interference_stack[hour], state["x"], state["y"])
                    geometry = 1.0 + (distance / (0.55 * sensor["range_m"])) ** 2
                    score = state["tx_power"] * sensor["gain"] * state["activity"] / (geometry * field_penalty)

                    if score < sensor["threshold"]:
                        continue

                    observation = {
                        "minute": minute,
                        "hour": hour,
                        "sensor_id": sensor["id"],
                        "sensor_label": sensor["label"],
                        "agent_id": state["id"],
                        "agent_label": state["label"],
                        "emitter_type": state["emitter_type"],
                        "state": state["state"],
                        "distance_m": round(distance, 3),
                        "score": round(score, 4),
                        "sensor_x": round(sensor_x, 3),
                        "sensor_y": round(sensor_y, 3),
                        "agent_x": round(state["x"], 3),
                        "agent_y": round(state["y"], 3),
                    }
                    sensor_observations.append(observation)
                    sensor_hourly_counts[sensor["id"]][hour] += 1
                    sensor_total_counts[sensor["id"]] += 1

        sensor_coverage = np.stack([self._sensor_coverage(sensor) for sensor in self.sensors], axis=0)
        agent_roster = [
            {
                "id": agent["id"],
                "label": agent["label"],
                "role": agent["role"],
                "emitter_type": agent["emitter_type"],
                "signature": agent["signature"],
            }
            for agent in self.agent_templates
        ]
        sensor_roster = [
            {
                "id": sensor["id"],
                "label": sensor["label"],
                "kind": sensor["kind"],
                "role": sensor["role"],
                "range_m": sensor["range_m"],
            }
            for sensor in self.sensors
        ]

        return {
            "trajectories": trajectories,
            "sensor_observations": sensor_observations,
            "sensor_tracks": sensor_tracks,
            "sensor_coverage": sensor_coverage,
            "agent_roster": agent_roster,
            "sensor_roster": sensor_roster,
            "sensor_hourly_observations": sensor_hourly_counts,
            "sensor_total_observations": sensor_total_counts,
        }

    def _sample_agent_state(self, agent: dict[str, Any], minute: int) -> dict[str, Any]:
        if agent["mode"] == "schedule":
            x, y, activity, state = self._interpolate_schedule(agent["schedule"], minute)
        elif agent["mode"] == "route_loop":
            x, y, activity, state = self._route_loop_state(agent, minute)
        elif agent["mode"] == "popup":
            x, y, activity, state = self._popup_state(minute)
        else:
            raise ValueError(f"Unsupported agent mode: {agent['mode']}")

        weather_scale = {
            "ble": self.weather.ble_attenuation,
            "trackers": 0.96 * self.weather.pedestrian_bias,
            "vehicle": self.weather.vehicle_bias * self.weather.wifi_attenuation,
            "interference": self.weather.interference_volatility,
        }.get(agent["signature"], 1.0)

        activity *= self.config.density_scale * weather_scale
        return {
            "id": agent["id"],
            "label": agent["label"],
            "x": float(x),
            "y": float(y),
            "activity": float(max(activity, 0.0)),
            "active": bool(activity > 0.08),
            "state": state,
            "tx_power": agent["tx_power"],
            "emitter_type": agent["emitter_type"],
        }

    @staticmethod
    def _interpolate_schedule(schedule: list[list[Any]], minute: int) -> tuple[float, float, float, str]:
        if minute <= schedule[0][0]:
            return float(schedule[0][1]), float(schedule[0][2]), float(schedule[0][3]), str(schedule[0][4])
        if minute >= schedule[-1][0]:
            return float(schedule[-1][1]), float(schedule[-1][2]), float(schedule[-1][3]), str(schedule[-1][4])

        for idx in range(len(schedule) - 1):
            left = schedule[idx]
            right = schedule[idx + 1]
            if left[0] <= minute <= right[0]:
                span = max(1, right[0] - left[0])
                t = (minute - left[0]) / span
                x = (1.0 - t) * left[1] + t * right[1]
                y = (1.0 - t) * left[2] + t * right[2]
                activity = (1.0 - t) * left[3] + t * right[3]
                state = str(left[4] if t < 0.5 else right[4])
                return float(x), float(y), float(activity), state

        last = schedule[-1]
        return float(last[1]), float(last[2]), float(last[3]), str(last[4])

    def _route_loop_state(self, agent: dict[str, Any], minute: int) -> tuple[float, float, float, str]:
        start = int(agent["start_minute"])
        end = int(agent["end_minute"])
        if minute < start or minute > end:
            idle = agent["idle_point"]
            return float(idle[0]), float(idle[1]), 0.04, "idle"

        phase = ((minute - start) % int(agent["cycle_minutes"])) / float(agent["cycle_minutes"])
        route = np.asarray(agent["route"], dtype=float)
        x, y = self._interpolate_polyline(route, phase)
        return x, y, float(agent["activity"]), "transit"

    def _popup_state(self, minute: int) -> tuple[float, float, float, str]:
        hour = minute // 60
        for event in self.popup_events:
            if event["start_hour"] <= hour <= event["end_hour"]:
                jitter_x = 4.0 * math.sin(minute / 14.0)
                jitter_y = 4.0 * math.cos(minute / 18.0)
                return (
                    float(event["x"] + jitter_x),
                    float(event["y"] + jitter_y),
                    float(0.86 * event["amplitude"]),
                    event["label"],
                )
        return 30.0, 30.0, 0.0, "inactive"

    def _sensor_position(self, sensor: dict[str, Any], minute: int) -> tuple[float, float]:
        if sensor["kind"] == "fixed":
            return float(sensor["x"]), float(sensor["y"])

        phase = (minute % int(sensor["cycle_minutes"])) / float(sensor["cycle_minutes"])
        route = np.asarray(sensor["route"], dtype=float)
        return self._interpolate_polyline(route, phase)

    def _sensor_coverage(self, sensor: dict[str, Any]) -> np.ndarray:
        if sensor["kind"] == "fixed":
            samples = [self._sensor_position(sensor, 0)]
        else:
            samples = [self._sensor_position(sensor, step * 15) for step in range(12)]

        aggregate = np.zeros_like(self.xx)
        for sample_x, sample_y in samples:
            distance = np.sqrt((self.xx - sample_x) ** 2 + (self.yy - sample_y) ** 2)
            aggregate += sensor["gain"] / (1.0 + (distance / (0.55 * sensor["range_m"])) ** 2)

        aggregate /= len(samples)
        return np.clip(aggregate, 0.0, None)

    def _sample_field(self, field: np.ndarray, x: float, y: float) -> float:
        ix = int(np.clip(round((x / self.config.width_m) * (self.config.grid_size - 1)), 0, self.config.grid_size - 1))
        iy = int(np.clip(round((y / self.config.height_m) * (self.config.grid_size - 1)), 0, self.config.grid_size - 1))
        return float(field[iy, ix])

    def _personality(
        self,
        hour: int,
        ble: np.ndarray,
        wifi: np.ndarray,
        trackers: np.ndarray,
        vehicle: np.ndarray,
        interference: np.ndarray,
    ) -> str:
        means = {
            "residential": float(np.mean(ble)),
            "retail": float(np.mean(wifi)),
            "logistics": float(np.mean(trackers)),
            "vehicular": float(np.mean(vehicle)),
            "contested": float(np.mean(interference)),
        }
        dominant = max(means, key=means.get)
        tone = "night" if hour < 6 or hour >= 20 else "day"
        adjectives = {
            "residential": "close-in and domestic",
            "retail": "bursty and transactional",
            "logistics": "restless and routed",
            "vehicular": "mobile and corridor-driven",
            "contested": "noisy and unstable",
        }
        return f"{tone.capitalize()} {adjectives[dominant]}"

    def _narrative(self, hour: int, active_events: list[str]) -> str:
        if hour < 6:
            baseline = "Apartment devices dominate the district while road traffic stays thin."
        elif hour < 10:
            baseline = "Residents wake, commuters push hotspots onto the avenues, and retail infrastructure comes online."
        elif hour < 16:
            baseline = "Storefront Wi-Fi and delivery trackers give the block a busy commercial signature."
        elif hour < 21:
            baseline = "Return-home BLE chatter overlaps with delivery tails and the evening vehicle surge."
        else:
            baseline = "The district contracts into residential chatter, late food orders, and sporadic nightlife traffic."

        if active_events:
            labels = ", ".join(active_events)
            return f"{baseline} Active interference: {labels}."
        return baseline

    @staticmethod
    def _period_label(hour: int) -> str:
        if 5 <= hour < 10:
            return "morning ramp"
        if 10 <= hour < 16:
            return "midday churn"
        if 16 <= hour < 21:
            return "evening surge"
        return "night cycle"

    @staticmethod
    def _dominant_emitter(layers: dict[str, np.ndarray]) -> str:
        return max(layers, key=lambda name: float(np.mean(layers[name])))

    @staticmethod
    def _gaussian_peak(hour: int, center: float, width: float, amplitude: float) -> float:
        return amplitude * math.exp(-((hour - center) ** 2) / (2.0 * width**2))

    @staticmethod
    def _window(hour: int, start: int, end: int) -> float:
        return 1.0 if start <= hour <= end else 0.0

    def _ellipse(self, center_x: float, center_y: float, sigma_x: float, sigma_y: float, amplitude: float) -> np.ndarray:
        dx = self.xx - center_x
        dy = self.yy - center_y
        exponent = (dx**2) / (2.0 * sigma_x**2) + (dy**2) / (2.0 * sigma_y**2)
        return amplitude * np.exp(-exponent)

    @staticmethod
    def _interpolate_polyline(points: np.ndarray, phase: float) -> tuple[float, float]:
        if len(points) == 1:
            return float(points[0, 0]), float(points[0, 1])

        distances = np.sqrt(np.sum(np.diff(points, axis=0) ** 2, axis=1))
        total = float(np.sum(distances))
        if total <= 0.0:
            return float(points[0, 0]), float(points[0, 1])

        target = (phase % 1.0) * total
        traversed = 0.0
        for idx, segment_length in enumerate(distances):
            if traversed + segment_length >= target:
                local = (target - traversed) / max(segment_length, 1e-9)
                x = (1.0 - local) * points[idx, 0] + local * points[idx + 1, 0]
                y = (1.0 - local) * points[idx, 1] + local * points[idx + 1, 1]
                return float(x), float(y)
            traversed += float(segment_length)

        return float(points[-1, 0]), float(points[-1, 1])

    def _interpolate_route(self, phase: float) -> tuple[float, float]:
        points = self.delivery_route
        segment_count = len(points)
        scaled = phase % 1.0 * segment_count
        index = int(math.floor(scaled))
        next_index = (index + 1) % segment_count
        t = scaled - index
        x = (1.0 - t) * points[index, 0] + t * points[next_index, 0]
        y = (1.0 - t) * points[index, 1] + t * points[next_index, 1]
        return float(x), float(y)
