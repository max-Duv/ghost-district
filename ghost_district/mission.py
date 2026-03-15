from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Any

import numpy as np


@dataclass
class EmitterProfile:
    mission_relevance: float
    ambiguity: float
    deception: float
    resilience: float


BASE_EMITTER_PROFILES: dict[str, EmitterProfile] = {
    "ble": EmitterProfile(0.38, 0.30, 0.08, 0.44),
    "trackers": EmitterProfile(0.78, 0.52, 0.14, 0.78),
    "vehicle": EmitterProfile(0.66, 0.62, 0.26, 0.72),
    "interference": EmitterProfile(0.90, 0.76, 0.94, 0.82),
}


class MissionLogicEngine:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.summary = result["summary"]
        self.config = self.summary["config"]
        self.width_m = float(self.config["width_m"])
        self.height_m = float(self.config["height_m"])
        self.grid_size = int(self.config["grid_size"])
        self.trajectories = result["trajectories"]
        self.sensor_observations = result["sensor_observations"]
        self.total_energy = result["total_energy"]
        self.interference = result["interference"]
        self.gps_quality = result["gps_quality"]

        self.agent_profiles = self._build_agent_profiles()
        self.candidate_sites = self._build_candidate_sites()
        self.route_library = self._build_routes()
        self.action_sites = self._build_action_sites()

    def analyze(self) -> dict[str, Any]:
        emitters = self._classify_emitters()
        placements = self._score_collector_placements()
        routes = self._score_routes()
        states = self._infer_mission_states()
        actions = self._score_interference_actions()
        collection_windows = self._identify_collection_windows(states, routes)

        return {
            "title": "Ghost District Mission Logic Layer",
            "collector_placements": placements,
            "route_assessment": routes,
            "emitter_assessment": emitters,
            "state_timeline": states,
            "interference_actions": actions,
            "collection_windows": collection_windows,
        }

    def _build_agent_profiles(self) -> dict[str, EmitterProfile]:
        profiles: dict[str, EmitterProfile] = {}
        for agent in self.summary["agents"]:
            base = BASE_EMITTER_PROFILES[agent["signature"]]
            relevance = base.mission_relevance
            ambiguity = base.ambiguity
            deception = base.deception
            resilience = base.resilience
            role = agent["role"].lower()

            if "night" in role or "rideshare" in role:
                ambiguity += 0.08
                relevance += 0.08
            if "courier" in role:
                relevance += 0.05
                resilience += 0.06
            if "resident" in role:
                ambiguity += 0.04
            if "popup" in role:
                deception += 0.04
                ambiguity += 0.03

            profiles[agent["id"]] = EmitterProfile(
                mission_relevance=float(np.clip(relevance, 0.0, 1.0)),
                ambiguity=float(np.clip(ambiguity, 0.0, 1.0)),
                deception=float(np.clip(deception, 0.0, 1.0)),
                resilience=float(np.clip(resilience, 0.0, 1.0)),
            )
        return profiles

    def _build_candidate_sites(self) -> list[dict[str, Any]]:
        return [
            {"label": "Roof West", "x": 78.0, "y": 304.0},
            {"label": "North Corridor", "x": 210.0, "y": 338.0},
            {"label": "Market Corner", "x": 218.0, "y": 214.0},
            {"label": "South Lobby", "x": 314.0, "y": 118.0},
            {"label": "East Arcade", "x": 350.0, "y": 210.0},
            {"label": "Southwest Gate", "x": 76.0, "y": 110.0},
            {"label": "Center Spine", "x": 210.0, "y": 208.0},
            {"label": "Northeast Overwatch", "x": 324.0, "y": 320.0},
        ]

    def _build_routes(self) -> list[dict[str, Any]]:
        return [
            {"label": "Perimeter Sweep", "points": [(32.0, 90.0), (380.0, 92.0), (384.0, 334.0), (38.0, 334.0)]},
            {"label": "Market Spine", "points": [(38.0, 208.0), (140.0, 208.0), (210.0, 214.0), (384.0, 210.0)]},
            {"label": "North Arc", "points": [(70.0, 332.0), (210.0, 354.0), (350.0, 320.0)]},
            {"label": "South Service Loop", "points": [(68.0, 112.0), (210.0, 60.0), (346.0, 96.0)]},
            {"label": "Diagonal Courier Tail", "points": [(82.0, 112.0), (210.0, 208.0), (360.0, 260.0)]},
            {"label": "Arcade Crosscut", "points": [(110.0, 320.0), (145.0, 208.0), (320.0, 115.0)]},
        ]

    def _build_action_sites(self) -> list[dict[str, Any]]:
        popup_sites = [
            {"label": event["label"].title(), "x": float(event["x"]), "y": float(event["y"])}
            for event in self.summary["popup_events"]
        ]
        return popup_sites + [
            {"label": "Center Spine", "x": 210.0, "y": 208.0},
            {"label": "Market Corner", "x": 218.0, "y": 214.0},
            {"label": "Southwest Gate", "x": 82.0, "y": 112.0},
        ]

    def _classify_emitters(self) -> list[dict[str, Any]]:
        assessments = []
        observation_counts = {agent["id"]: 0 for agent in self.summary["agents"]}
        for observation in self.sensor_observations:
            observation_counts[observation["agent_id"]] += 1

        for agent in self.summary["agents"]:
            profile = self.agent_profiles[agent["id"]]
            tags = []
            if profile.mission_relevance >= 0.65:
                tags.append("mission-relevant")
            if profile.ambiguity >= 0.55:
                tags.append("ambiguous")
            if profile.deception >= 0.60:
                tags.append("deceptive")
            if not tags:
                tags.append("background")

            assessments.append(
                {
                    "id": agent["id"],
                    "label": agent["label"],
                    "role": agent["role"],
                    "emitter_type": agent["emitter_type"],
                    "mission_relevance": round(profile.mission_relevance, 3),
                    "ambiguity": round(profile.ambiguity, 3),
                    "deception": round(profile.deception, 3),
                    "resilience": round(profile.resilience, 3),
                    "observation_count": observation_counts.get(agent["id"], 0),
                    "tags": tags,
                }
            )
        return sorted(assessments, key=lambda item: item["mission_relevance"], reverse=True)

    def _score_collector_placements(self) -> list[dict[str, Any]]:
        placements = []
        for site in self.candidate_sites:
            opportunity, exposure, ambiguity_penalty = self._score_point(site["x"], site["y"])
            placement_score = 100.0 * opportunity / (1.0 + 0.65 * exposure + 0.50 * ambiguity_penalty)
            placements.append(
                {
                    "label": site["label"],
                    "x": site["x"],
                    "y": site["y"],
                    "collection_opportunity": round(opportunity, 3),
                    "exposure": round(exposure, 3),
                    "ambiguity_penalty": round(ambiguity_penalty, 3),
                    "placement_score": round(placement_score, 3),
                }
            )
        return sorted(placements, key=lambda item: item["placement_score"], reverse=True)

    def _score_routes(self) -> list[dict[str, Any]]:
        scored_routes = []
        for route in self.route_library:
            samples = self._sample_route(route["points"], 24)
            opportunity = 0.0
            exposure = 0.0
            ambiguity = 0.0
            for x, y in samples:
                point_opportunity, point_exposure, point_ambiguity = self._score_point(x, y)
                opportunity += point_opportunity
                exposure += point_exposure
                ambiguity += point_ambiguity

            step_count = len(samples)
            mean_opportunity = opportunity / step_count
            mean_exposure = exposure / step_count
            mean_ambiguity = ambiguity / step_count
            route_score = 100.0 * mean_opportunity / (1.0 + 0.70 * mean_exposure + 0.55 * mean_ambiguity)

            scored_routes.append(
                {
                    "label": route["label"],
                    "collection_opportunity": round(mean_opportunity, 3),
                    "exposure": round(mean_exposure, 3),
                    "ambiguity": round(mean_ambiguity, 3),
                    "route_score": round(route_score, 3),
                }
            )
        return sorted(scored_routes, key=lambda item: item["route_score"], reverse=True)

    def _infer_mission_states(self) -> list[dict[str, Any]]:
        hours = self.summary["hours"]
        ble_values = [entry["component_means"]["ble"] for entry in hours]
        wifi_values = [entry["component_means"]["wifi"] for entry in hours]
        tracker_values = [entry["component_means"]["trackers"] for entry in hours]
        vehicle_values = [entry["component_means"]["vehicle"] for entry in hours]
        interference_values = [entry["component_means"]["interference"] for entry in hours]
        gps_degradation = [entry["gps_degradation_mean"] for entry in hours]
        energy_values = [entry["district_energy_mean"] for entry in hours]

        thresholds = {
            "ble": np.percentile(ble_values, 70),
            "wifi": np.percentile(wifi_values, 60),
            "trackers": np.percentile(tracker_values, 70),
            "vehicle": np.percentile(vehicle_values, 70),
            "interference": np.percentile(interference_values, 70),
            "gps": np.percentile(gps_degradation, 70),
            "energy": np.percentile(energy_values, 70),
        }

        timeline = []
        for idx, entry in enumerate(hours):
            signal = "routine"
            confidence = 0.32
            reasons: list[str] = []

            energy_jump = energy_values[idx] - (energy_values[idx - 1] if idx > 0 else median(energy_values))
            if (
                entry["component_means"]["interference"] >= thresholds["interference"]
                and entry["gps_degradation_mean"] >= thresholds["gps"]
            ):
                signal = "disruption"
                confidence = 0.55 + 0.35 * min(1.0, entry["component_means"]["interference"] / max(thresholds["interference"], 1e-6))
                reasons.append("interference and GPS degradation rose together")

            if (
                entry["component_means"]["trackers"] >= thresholds["trackers"]
                and entry["component_means"]["vehicle"] >= thresholds["vehicle"]
                and entry["component_means"]["wifi"] >= thresholds["wifi"]
            ):
                staging_confidence = 0.50 + 0.28 * min(1.0, entry["component_means"]["trackers"] / max(thresholds["trackers"], 1e-6))
                if staging_confidence > confidence:
                    signal = "staging"
                    confidence = staging_confidence
                    reasons = ["logistics, vehicle, and retail signatures aligned"]

            if (
                entry["component_means"]["trackers"] >= thresholds["trackers"]
                and entry["component_means"]["vehicle"] >= thresholds["vehicle"]
                and entry["component_means"]["wifi"] < median(wifi_values)
            ):
                covert_confidence = 0.48 + 0.30 * min(1.0, entry["component_means"]["vehicle"] / max(thresholds["vehicle"], 1e-6))
                if covert_confidence > confidence:
                    signal = "covert movement"
                    confidence = covert_confidence
                    reasons = ["mobility rose while ambient retail noise thinned"]

            if (
                entry["component_means"]["ble"] >= thresholds["ble"]
                and entry["component_means"]["vehicle"] >= thresholds["vehicle"]
                and energy_jump > 0
            ):
                panic_confidence = 0.42 + 0.25 * min(1.0, energy_jump / max(thresholds["energy"], 1e-6))
                if panic_confidence > confidence:
                    signal = "panic"
                    confidence = panic_confidence
                    reasons = ["residential and vehicular activity surged abruptly"]

            if not reasons:
                reasons = ["baseline district behavior"]

            timeline.append(
                {
                    "hour": entry["hour"],
                    "state": signal,
                    "confidence": round(float(np.clip(confidence, 0.0, 0.99)), 3),
                    "reasons": reasons,
                }
            )
        return timeline

    def _score_interference_actions(self) -> list[dict[str, Any]]:
        scored_actions = []
        for site in self.action_sites:
            impact = 0.0
            affected = 0
            for observation in self.sensor_observations:
                distance = math.hypot(site["x"] - observation["agent_x"], site["y"] - observation["agent_y"])
                if distance > 36.0:
                    continue

                agent_profile = self.agent_profiles[observation["agent_id"]]
                attenuation = math.exp(-(distance**2) / (2.0 * 18.0**2))
                degraded_score = observation["score"] * (1.0 - 0.72 * attenuation)
                threshold = 0.14
                if degraded_score < threshold <= observation["score"]:
                    impact += agent_profile.mission_relevance * (1.0 + 0.35 * agent_profile.deception)
                    affected += 1
                else:
                    impact += max(observation["score"] - degraded_score, 0.0) * agent_profile.mission_relevance * 0.55

            scored_actions.append(
                {
                    "label": site["label"],
                    "x": site["x"],
                    "y": site["y"],
                    "impact_score": round(impact, 3),
                    "affected_observations": affected,
                }
            )
        return sorted(scored_actions, key=lambda item: item["impact_score"], reverse=True)

    def _identify_collection_windows(self, states: list[dict[str, Any]], routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        preferred_route = routes[0]["label"] if routes else "No route"
        windows = []
        for state in states:
            hour = state["hour"]
            hour_entry = self.summary["hours"][hour]
            opportunity = (
                hour_entry["component_means"]["trackers"]
                + hour_entry["component_means"]["vehicle"]
                + 0.6 * hour_entry["component_means"]["ble"]
            )
            exposure = hour_entry["component_means"]["interference"] + hour_entry["gps_degradation_mean"]
            mission_window = 100.0 * opportunity / (1.0 + 1.15 * exposure)
            windows.append(
                {
                    "hour": hour,
                    "state": state["state"],
                    "window_score": round(mission_window, 3),
                    "preferred_route": preferred_route,
                }
            )
        return sorted(windows, key=lambda item: item["window_score"], reverse=True)[:6]

    def _score_point(self, x: float, y: float) -> tuple[float, float, float]:
        opportunity = 0.0
        exposure = 0.0
        ambiguity = 0.0

        for agent in self.summary["agents"]:
            profile = self.agent_profiles[agent["id"]]
            points = self.trajectories[agent["id"]]
            for point in points:
                if not point["active"]:
                    continue
                distance = math.hypot(x - point["x"], y - point["y"])
                visibility = profile.mission_relevance * point["activity"] / (1.0 + (distance / 92.0) ** 2)
                opportunity += visibility
                ambiguity += visibility * profile.ambiguity * 0.34
                if profile.deception > 0.6:
                    exposure += visibility * 0.18

        exposure += 2.2 * self._sample_grid(self.interference.mean(axis=0), x, y)
        exposure += 1.6 * (1.0 - self._sample_grid(self.gps_quality.mean(axis=0), x, y))
        exposure += 0.8 * self._sample_grid(self.total_energy.mean(axis=0), x, y)
        return opportunity / 144.0, exposure, ambiguity / 144.0

    def _sample_route(self, points: list[tuple[float, float]], sample_count: int) -> list[tuple[float, float]]:
        segments = []
        total_length = 0.0
        for idx in range(len(points) - 1):
            left = points[idx]
            right = points[idx + 1]
            length = math.hypot(right[0] - left[0], right[1] - left[1])
            segments.append((left, right, length))
            total_length += length

        if total_length <= 0.0:
            return [points[0]]

        samples = []
        for step in range(sample_count):
            target = total_length * (step / max(sample_count - 1, 1))
            traversed = 0.0
            for left, right, length in segments:
                if traversed + length >= target:
                    local = (target - traversed) / max(length, 1e-9)
                    x = (1.0 - local) * left[0] + local * right[0]
                    y = (1.0 - local) * left[1] + local * right[1]
                    samples.append((x, y))
                    break
                traversed += length
        return samples

    def _sample_grid(self, field: np.ndarray, x: float, y: float) -> float:
        ix = int(np.clip(round((x / self.width_m) * (self.grid_size - 1)), 0, self.grid_size - 1))
        iy = int(np.clip(round((y / self.height_m) * (self.grid_size - 1)), 0, self.grid_size - 1))
        return float(field[iy, ix])
