from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import asyncio
import importlib.util
import json
import math
from pathlib import Path
import time
from typing import Any, Callable

import numpy as np


EventCallback = Callable[[dict[str, Any]], None]
StatusCallback = Callable[[str], None]
StopCallback = Callable[[], bool]


@dataclass
class CaptureConfig:
    backend_id: str
    duration_seconds: float = 15.0
    replay_speed: float = 60.0
    source_path: str = ""
    sensor_id: str = ""
    output_path: str = ""
    device_selector: str = ""
    start_freq_mhz: float = 2402.0
    stop_freq_mhz: float = 2480.0
    step_freq_mhz: float = 2.0
    sample_rate_hz: float = 2.4e6
    gain_db: float = 20.0
    dwell_ms: int = 250


@dataclass
class CaptureSummary:
    backend_id: str
    backend_name: str
    event_count: int
    started_at: str
    ended_at: str
    output_path: str
    notes: list[str]


class CaptureBackend:
    backend_id = "base"
    display_name = "Base"
    description = ""

    def availability(self) -> tuple[bool, str]:
        return True, "Ready"

    def capture(
        self,
        config: CaptureConfig,
        on_event: EventCallback,
        on_status: StatusCallback,
        should_stop: StopCallback,
    ) -> CaptureSummary:
        raise NotImplementedError


def build_backend_catalog(project_root: Path) -> list[CaptureBackend]:
    return [
        GhostDistrictPlaybackBackend(project_root),
        BLEAdapterCaptureBackend(),
        RTLSDRCaptureBackend(),
        JSONReplayCaptureBackend(),
    ]


def save_capture_log(events: list[dict[str, Any]], summary: CaptureSummary, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": asdict(summary),
        "events": events,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class GhostDistrictPlaybackBackend(CaptureBackend):
    backend_id = "ghost_playback"
    display_name = "Ghost District Playback"
    description = "Replay simulated sensor observations from Ghost District outputs as if they were live OTA captures."

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def availability(self) -> tuple[bool, str]:
        default_path = self._default_source_path()
        if default_path.exists():
            return True, f"Found {default_path.name}"
        return True, "Select a Ghost District observation file or generate outputs first."

    def capture(
        self,
        config: CaptureConfig,
        on_event: EventCallback,
        on_status: StatusCallback,
        should_stop: StopCallback,
    ) -> CaptureSummary:
        started_at = self._now()
        source_path = Path(config.source_path) if config.source_path else self._default_source_path()
        observations = _load_observation_list(source_path)
        if config.sensor_id:
            observations = [item for item in observations if item.get("sensor_id") == config.sensor_id]

        observations.sort(key=lambda item: (item.get("minute", 0), item.get("score", 0.0)))
        emitted_events = 0
        notes = [f"Source file: {source_path}"]
        if config.sensor_id:
            notes.append(f"Sensor filter: {config.sensor_id}")

        if not observations:
            raise ValueError("No playback observations were found for the selected file/filter.")

        playback_start = time.monotonic()
        previous_minute = observations[0].get("minute", 0)
        on_status(f"Playback loaded with {len(observations)} candidate events.")

        for record in observations:
            if should_stop():
                notes.append("Stopped by operator")
                break

            current_minute = record.get("minute", previous_minute)
            delta_minutes = max(0, current_minute - previous_minute)
            sleep_seconds = delta_minutes * 60.0 / max(config.replay_speed, 1.0)
            deadline = time.monotonic() + sleep_seconds
            while time.monotonic() < deadline:
                if should_stop():
                    notes.append("Stopped by operator")
                    break
                if time.monotonic() - playback_start > config.duration_seconds:
                    notes.append("Duration limit reached")
                    deadline = time.monotonic()
                    break
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            if should_stop() or time.monotonic() - playback_start > config.duration_seconds:
                break

            event = {
                "timestamp": self._now(),
                "backend_id": self.backend_id,
                "source_label": record.get("sensor_label", "Simulated sensor"),
                "protocol": record.get("emitter_type", "RF Event"),
                "channel": f"minute:{record.get('minute', 0)}",
                "rssi_dbm": round(_score_to_rssi(record.get("score", 0.0)), 1),
                "summary": (
                    f"{record.get('agent_label', 'unknown actor')} observed in state "
                    f"{record.get('state', 'unknown')} at {record.get('distance_m', 0):.1f} m"
                ),
                "metadata": {
                    "sensor_id": record.get("sensor_id", ""),
                    "agent_id": record.get("agent_id", ""),
                    "score": record.get("score", 0.0),
                    "distance_m": record.get("distance_m", 0.0),
                    "minute": record.get("minute", 0),
                },
            }
            on_event(event)
            emitted_events += 1
            previous_minute = current_minute

            if emitted_events % 25 == 0:
                on_status(f"Replayed {emitted_events} events")

        ended_at = self._now()
        return CaptureSummary(
            backend_id=self.backend_id,
            backend_name=self.display_name,
            event_count=emitted_events,
            started_at=started_at,
            ended_at=ended_at,
            output_path=config.output_path,
            notes=notes,
        )

    def _default_source_path(self) -> Path:
        return self.project_root / "outputs" / "ghost_district_sensor_observations.json"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


class JSONReplayCaptureBackend(CaptureBackend):
    backend_id = "json_replay"
    display_name = "JSON Replay"
    description = "Replay a previous Ghost District capture log or raw observation JSON file."

    def availability(self) -> tuple[bool, str]:
        return True, "Ready"

    def capture(
        self,
        config: CaptureConfig,
        on_event: EventCallback,
        on_status: StatusCallback,
        should_stop: StopCallback,
    ) -> CaptureSummary:
        started_at = datetime.now(timezone.utc).isoformat()
        if not config.source_path:
            raise ValueError("Select a JSON capture file to replay.")

        path = Path(config.source_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "events" in payload:
            records = payload["events"]
        else:
            records = _load_observation_list(path)

        emitted_events = 0
        on_status(f"Loaded {len(records)} records from {path.name}")
        for record in records:
            if should_stop():
                break
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "backend_id": self.backend_id,
                "source_label": record.get("source_label", record.get("sensor_label", "Replay")),
                "protocol": record.get("protocol", record.get("emitter_type", "Replay Event")),
                "channel": record.get("channel", f"minute:{record.get('minute', 0)}"),
                "rssi_dbm": record.get("rssi_dbm", record.get("score", None)),
                "summary": record.get("summary", f"Replay record from {record.get('agent_label', 'unknown actor')}"),
                "metadata": record.get("metadata", record),
            }
            on_event(event)
            emitted_events += 1
            time.sleep(0.03)
            if emitted_events % 50 == 0:
                on_status(f"Replayed {emitted_events} records")
            if emitted_events * 0.03 >= config.duration_seconds:
                break

        ended_at = datetime.now(timezone.utc).isoformat()
        return CaptureSummary(
            backend_id=self.backend_id,
            backend_name=self.display_name,
            event_count=emitted_events,
            started_at=started_at,
            ended_at=ended_at,
            output_path=config.output_path,
            notes=[f"Replay file: {path}"],
        )


class BLEAdapterCaptureBackend(CaptureBackend):
    backend_id = "ble_live"
    display_name = "BLE Adapter"
    description = "Live BLE advertisement capture using a local Bluetooth adapter through bleak."

    def availability(self) -> tuple[bool, str]:
        if importlib.util.find_spec("bleak") is None:
            return False, "Install bleak to enable BLE capture."
        return True, "Ready"

    def capture(
        self,
        config: CaptureConfig,
        on_event: EventCallback,
        on_status: StatusCallback,
        should_stop: StopCallback,
    ) -> CaptureSummary:
        started_at = datetime.now(timezone.utc).isoformat()
        notes: list[str] = []
        event_count = asyncio.run(self._capture_async(config, on_event, on_status, should_stop, notes))
        ended_at = datetime.now(timezone.utc).isoformat()
        return CaptureSummary(
            backend_id=self.backend_id,
            backend_name=self.display_name,
            event_count=event_count,
            started_at=started_at,
            ended_at=ended_at,
            output_path=config.output_path,
            notes=notes or ["BLE advertisement scan completed"],
        )

    async def _capture_async(
        self,
        config: CaptureConfig,
        on_event: EventCallback,
        on_status: StatusCallback,
        should_stop: StopCallback,
        notes: list[str],
    ) -> int:
        from bleak import BleakScanner

        event_count = 0
        recent_emit: dict[str, float] = {}
        start = time.monotonic()

        def detection_callback(device: Any, advertisement_data: Any) -> None:
            nonlocal event_count
            now = time.monotonic()
            address = getattr(device, "address", "unknown")
            if now - recent_emit.get(address, 0.0) < 1.25:
                return
            recent_emit[address] = now

            service_uuids = list(getattr(advertisement_data, "service_uuids", []) or [])
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "backend_id": self.backend_id,
                "source_label": getattr(device, "name", None) or address,
                "protocol": "BLE Advertisement",
                "channel": ",".join(service_uuids[:3]) if service_uuids else "ADV",
                "rssi_dbm": getattr(advertisement_data, "rssi", getattr(device, "rssi", None)),
                "summary": f"Address {address} advertising {len(service_uuids)} services",
                "metadata": {
                    "address": address,
                    "local_name": getattr(advertisement_data, "local_name", None),
                    "service_uuids": service_uuids,
                    "manufacturer_data": getattr(advertisement_data, "manufacturer_data", {}),
                    "tx_power": getattr(advertisement_data, "tx_power", None),
                },
            }
            on_event(event)
            event_count += 1

        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        on_status("BLE scan started")

        try:
            while time.monotonic() - start < config.duration_seconds:
                if should_stop():
                    notes.append("Stopped by operator")
                    break
                await asyncio.sleep(0.2)
        finally:
            await scanner.stop()
            on_status("BLE scan stopped")

        return event_count


class RTLSDRCaptureBackend(CaptureBackend):
    backend_id = "rtl_sdr"
    display_name = "RTL-SDR Sweep"
    description = "Passive spectrum-power sweep across a configurable frequency range using an RTL-SDR."

    def availability(self) -> tuple[bool, str]:
        if importlib.util.find_spec("rtlsdr") is None:
            return False, "Install pyrtlsdr and connect an RTL-SDR to enable this backend."
        return True, "Ready"

    def capture(
        self,
        config: CaptureConfig,
        on_event: EventCallback,
        on_status: StatusCallback,
        should_stop: StopCallback,
    ) -> CaptureSummary:
        from rtlsdr import RtlSdr

        started_at = datetime.now(timezone.utc).isoformat()
        start_mhz = min(config.start_freq_mhz, config.stop_freq_mhz)
        stop_mhz = max(config.start_freq_mhz, config.stop_freq_mhz)
        step_mhz = max(config.step_freq_mhz, 0.1)
        frequencies_mhz = np.arange(start_mhz, stop_mhz + 0.0001, step_mhz)

        if frequencies_mhz.size == 0:
            raise ValueError("Frequency sweep produced no channels.")

        sdr = RtlSdr(int(config.device_selector) if config.device_selector.strip() else 0)
        sdr.sample_rate = float(config.sample_rate_hz)
        sdr.gain = float(config.gain_db)
        dwell_seconds = max(config.dwell_ms, 50) / 1000.0
        event_count = 0
        notes = [f"Swept {start_mhz:.3f}-{stop_mhz:.3f} MHz"]
        on_status(f"RTL-SDR sweep with {len(frequencies_mhz)} bins")

        try:
            capture_start = time.monotonic()
            while time.monotonic() - capture_start < config.duration_seconds and not should_stop():
                for center_mhz in frequencies_mhz:
                    if should_stop() or time.monotonic() - capture_start >= config.duration_seconds:
                        break
                    sdr.center_freq = center_mhz * 1e6
                    samples = sdr.read_samples(262144)
                    power_db = 10.0 * math.log10(float(np.mean(np.abs(samples) ** 2)) + 1e-12)
                    event = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "backend_id": self.backend_id,
                        "source_label": f"RTL-SDR {config.device_selector or '0'}",
                        "protocol": "Spectrum Power",
                        "channel": f"{center_mhz:.3f} MHz",
                        "rssi_dbm": round(power_db, 2),
                        "summary": f"Average channel power at {center_mhz:.3f} MHz",
                        "metadata": {
                            "sample_rate_hz": config.sample_rate_hz,
                            "gain_db": config.gain_db,
                            "dwell_ms": config.dwell_ms,
                        },
                    }
                    on_event(event)
                    event_count += 1
                    time.sleep(dwell_seconds)
        finally:
            sdr.close()
            on_status("RTL-SDR closed")

        ended_at = datetime.now(timezone.utc).isoformat()
        return CaptureSummary(
            backend_id=self.backend_id,
            backend_name=self.display_name,
            event_count=event_count,
            started_at=started_at,
            ended_at=ended_at,
            output_path=config.output_path,
            notes=notes,
        )


def _load_observation_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Capture source file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "events" in payload:
        return list(payload["events"])
    raise ValueError("Unsupported capture JSON payload.")


def _score_to_rssi(score: float) -> float:
    return -98.0 + 18.0 * math.log10(max(score, 1e-4) * 10.0)
