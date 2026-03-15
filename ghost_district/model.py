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

        summary = {
            "title": "Ghost District: Behavioral RF Terrain Synthesis for Urban Collection Environments",
            "config": asdict(self.config),
            "weather_profile": asdict(self.weather),
            "popup_events": self.popup_events,
            "hours": hourly_metrics,
            "field_shape": [24, self.config.grid_size, self.config.grid_size],
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
            "total_energy": np.stack(total_energy_stack, axis=0),
            "interference": np.stack(interference_stack, axis=0),
            "gps_quality": np.stack(gps_quality_stack, axis=0),
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
