import asyncio
import math
import random
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.commands import CommandValidationError, apply_device_command, apply_room_scene
from app.models import (
    AcState,
    ChangedValue,
    CommandResult,
    CurtainState,
    DeviceCommand,
    DeviceStates,
    EnvironmentState,
    FanState,
    HumidityDeviceState,
    LightState,
    OccupancyState,
    OpeningsState,
    PowerState,
    RoomSceneTargets,
    RoomSnapshot,
    ScenarioDefinition,
    SimulationControl,
    SimulationStatus,
    SmartPlugState,
    SpeedDeviceState,
)
from app.scenarios import ScenarioRepository
from app.state import EventBroker
from app.storage import Storage, write_generated_csv

BANGKOK = ZoneInfo("Asia/Bangkok")
SIMULATION_START = datetime(2026, 7, 22, 8, 0, tzinfo=BANGKOK)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def initial_snapshot(timestamp: datetime = SIMULATION_START) -> RoomSnapshot:
    return RoomSnapshot(
        version=0,
        timestamp=timestamp,
        environment=EnvironmentState(
            temperature_c=28.4,
            humidity_percent=72,
            co2_ppm=1_150,
            pm25_ug_m3=12,
            ambient_light_lux=180,
            noise_db=37,
        ),
        occupancy=OccupancyState(room_present=True, bed_occupied=False, desk_occupied=True),
        openings=OpeningsState(window_state="closed", curtain_position_percent=60),
        power=PowerState(
            computer_power_watts=140,
            smart_plugs={
                "desk_computer": SmartPlugState(state="on", power_watts=140),
                "monitor": SmartPlugState(state="on", power_watts=32),
            },
        ),
        devices=DeviceStates(
            ac=AcState(power=True, mode="cool", temperature_c=26, fan_mode="auto"),
            fan=FanState(power=False, speed=0, oscillation=True),
            main_light=LightState(power=True, brightness_percent=65, color_temperature_kelvin=4_000),
            bedside_light=LightState(power=False, brightness_percent=0, color_temperature_kelvin=3_000),
            air_purifier=SpeedDeviceState(power=False, speed=0),
            curtain=CurtainState(position_percent=60),
            humidity_device=HumidityDeviceState(
                power=False,
                mode="dehumidify",
                target_humidity_percent=55,
            ),
        ),
        inferred_context="working",
        context_confidence=0.92,
    )


def infer_context(snapshot: RoomSnapshot, override: str | None = None) -> tuple[str, float]:
    if override:
        return override, 1.0
    if not snapshot.occupancy.room_present:
        return "away", 0.99
    if snapshot.occupancy.desk_occupied and snapshot.power.computer_power_watts > 20:
        return "working", 0.93
    if snapshot.occupancy.bed_occupied:
        return "sleeping", 0.88
    return "relaxing", 0.82


def apply_daily_schedule(
    snapshot: RoomSnapshot,
    timestamp: datetime,
    *,
    manage_computer_power: bool = True,
) -> RoomSnapshot:
    data = snapshot.model_dump(mode="python")
    hour = timestamp.hour
    if hour < 7 or hour >= 23:
        present, bed, desk, computer = True, True, False, 0.0
    elif 8 <= hour < 18:
        present, bed, desk, computer = True, False, True, 140.0
    elif hour == 7 or 18 <= hour < 23:
        present, bed, desk, computer = True, False, False, 0.0
    else:
        present, bed, desk, computer = False, False, False, 0.0
    data["occupancy"].update(
        room_present=present,
        bed_occupied=bed,
        desk_occupied=desk,
    )
    if manage_computer_power:
        data["power"]["computer_power_watts"] = computer
        computer_plug = data["power"]["smart_plugs"]["desk_computer"]
        computer_plug.update(state="on" if computer else "off", power_watts=computer)
    return RoomSnapshot.model_validate(data)


def advance_snapshot(
    snapshot: RoomSnapshot,
    timestamp: datetime,
    rng: random.Random,
    minutes: int,
    *,
    use_schedule: bool,
    use_computer_schedule: bool = True,
    context_override: str | None = None,
) -> RoomSnapshot:
    current = (
        apply_daily_schedule(snapshot, timestamp, manage_computer_power=use_computer_schedule)
        if use_schedule
        else snapshot
    )
    data = current.model_dump(mode="python")
    hour = timestamp.hour + timestamp.minute / 60
    daylight = max(0.0, math.sin(math.pi * (hour - 6) / 12))
    outdoor_temperature = 27.5 + 4.5 * math.sin(math.pi * (hour - 9) / 12)
    environment = data["environment"]
    devices = data["devices"]
    openings = data["openings"]
    occupancy = data["occupancy"]

    temperature_delta = (outdoor_temperature - environment["temperature_c"]) * 0.012 * minutes
    if devices["ac"]["power"]:
        temperature_delta += (devices["ac"]["temperature_c"] - environment["temperature_c"]) * 0.035 * minutes
    temperature_delta += rng.uniform(-0.035, 0.035) * math.sqrt(minutes)
    environment["temperature_c"] = round(clamp(environment["temperature_c"] + temperature_delta, 16, 38), 2)

    humidity_target = 66 + 8 * math.sin(math.pi * (hour + 2) / 12)
    humidity_delta = (humidity_target - environment["humidity_percent"]) * 0.01 * minutes
    if devices["ac"]["power"] and devices["ac"]["mode"] in {"cool", "dry"}:
        humidity_delta -= 0.04 * minutes
    humidity_device = devices["humidity_device"]
    if humidity_device["power"]:
        direction = 1 if humidity_device["mode"] == "humidify" else -1
        humidity_delta += direction * 0.12 * minutes
    environment["humidity_percent"] = round(clamp(environment["humidity_percent"] + humidity_delta, 25, 95), 2)

    if openings["window_state"] == "open":
        co2_delta = (520 - environment["co2_ppm"]) * 0.035 * minutes
    elif occupancy["room_present"]:
        co2_delta = (1_650 - environment["co2_ppm"]) * 0.012 * minutes
    else:
        co2_delta = (500 - environment["co2_ppm"]) * 0.008 * minutes
    environment["co2_ppm"] = round(clamp(environment["co2_ppm"] + co2_delta, 400, 5_000), 1)

    pm_target = 11 + 3 * max(0.0, math.sin(math.pi * (hour - 7) / 12))
    pm_delta = (pm_target - environment["pm25_ug_m3"]) * 0.018 * minutes
    pm_delta += rng.uniform(-0.09, 0.09) * math.sqrt(minutes)
    if devices["air_purifier"]["power"]:
        pm_delta -= devices["air_purifier"]["speed"] * 0.18 * minutes
    environment["pm25_ug_m3"] = round(clamp(environment["pm25_ug_m3"] + pm_delta, 1, 500), 2)

    natural_lux = daylight * 3_500 * (openings["curtain_position_percent"] / 100)
    light_lux = sum(
        light["brightness_percent"] * multiplier if light["power"] else 0
        for light, multiplier in ((devices["main_light"], 3.5), (devices["bedside_light"], 1.5))
    )
    environment["ambient_light_lux"] = round(clamp(natural_lux + light_lux, 0, 100_000), 1)

    noise = 29.0
    noise += 6 if devices["ac"]["power"] else 0
    noise += devices["fan"]["speed"] * 4.5
    noise += devices["air_purifier"]["speed"] * 3.5
    noise += rng.uniform(-0.6, 0.6)
    environment["noise_db"] = round(clamp(noise, 20, 90), 1)

    data["timestamp"] = timestamp
    data["version"] += 1
    candidate = RoomSnapshot.model_validate(data)
    context, confidence = infer_context(candidate, context_override)
    return candidate.model_copy(
        update={"inferred_context": context, "context_confidence": confidence}
    )


def generate_baseline(seed: int) -> list[RoomSnapshot]:
    rng = random.Random(seed)
    timestamp = SIMULATION_START - timedelta(days=1)
    snapshot = initial_snapshot(timestamp)
    snapshots: list[RoomSnapshot] = []
    for _ in range(24 * 60):
        timestamp += timedelta(minutes=1)
        snapshot = advance_snapshot(snapshot, timestamp, rng, 1, use_schedule=True)
        snapshots.append(snapshot)
    return snapshots


class SimulationEngine:
    def __init__(
        self,
        *,
        seed: int,
        tick_seconds: float,
        minutes_per_tick: int,
        storage: Storage,
        scenarios: ScenarioRepository,
        broker: EventBroker,
    ) -> None:
        self.seed = seed
        self.tick_seconds = tick_seconds
        self.minutes_per_tick = minutes_per_tick
        self.storage = storage
        self.scenarios = scenarios
        self.broker = broker
        self._snapshot = initial_snapshot()
        self._rng = random.Random(seed)
        self._running = True
        self._speed: int = 1
        self._active_scenario: ScenarioDefinition | None = None
        self._scenario_elapsed = 0
        self._applied_scenario_actions: set[int] = set()
        self._context_override: str | None = None
        self._computer_schedule_enabled = True
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="flatmate-simulation")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def snapshot(self) -> RoomSnapshot:
        async with self._lock:
            return self._snapshot.model_copy(deep=True)

    async def status(self) -> SimulationStatus:
        async with self._lock:
            return self._status_unlocked()

    async def control(self, control: SimulationControl) -> SimulationStatus:
        async with self._lock:
            if control.action == "pause":
                self._running = False
            elif control.action == "resume":
                self._running = True
            elif control.action == "set_speed":
                self._speed = control.speed or 1
            elif control.action == "reset":
                self._rng = random.Random(self.seed)
                self._snapshot = initial_snapshot()
                self._running = True
                self._speed = 1
                self._active_scenario = None
                self._scenario_elapsed = 0
                self._applied_scenario_actions.clear()
                self._context_override = None
                self._computer_schedule_enabled = True
                self.storage.record_snapshot(self._snapshot)
            status = self._status_unlocked()
            snapshot = self._snapshot.model_dump(mode="json")
            self.storage.record_simulation_event(
                self._snapshot.timestamp,
                f"control_{control.action}",
                status.model_dump(mode="json"),
            )
        await self.broker.publish("simulation", status.model_dump(mode="json"))
        if control.action == "reset":
            await self.broker.publish(
                "state_changed",
                {"changed_paths": ["*"], "snapshot_version": snapshot["version"], "snapshot": snapshot},
            )
        return status

    async def activate_scenario(self, scenario: ScenarioDefinition) -> SimulationStatus:
        async with self._lock:
            before = self._snapshot
            self._active_scenario = scenario
            self._scenario_elapsed = 0
            self._applied_scenario_actions.clear()
            self._context_override = None
            self._apply_due_scenario_actions_unlocked()
            self._snapshot = self._snapshot.model_copy(
                update={"version": before.version + 1, "timestamp": before.timestamp}
            )
            self.storage.record_snapshot(self._snapshot)
            status = self._status_unlocked()
            snapshot = self._snapshot.model_dump(mode="json")
            self.storage.record_simulation_event(
                self._snapshot.timestamp,
                "scenario_activated",
                {"scenario_id": scenario.id},
            )
        await self.broker.publish("simulation", status.model_dump(mode="json"))
        await self.broker.publish(
            "state_changed",
            {"changed_paths": ["scenario"], "snapshot_version": snapshot["version"], "snapshot": snapshot},
        )
        return status

    async def command_device(self, device_id: str, command: DeviceCommand) -> CommandResult:
        async with self._lock:
            updated, changes = apply_device_command(self._snapshot, device_id, command.values)
            if device_id == "desk_computer" and changes:
                self._computer_schedule_enabled = False
            timestamp = self._snapshot.timestamp
            if changes:
                updated = updated.model_copy(update={"timestamp": timestamp})
                self._snapshot = updated
            command_id = str(uuid4())
            result = CommandResult(
                command_id=command_id,
                device_id=device_id,
                source=command.source,
                timestamp=timestamp,
                changed=changes,
                snapshot_version=self._snapshot.version,
            )
            if changes:
                self.storage.record_changes(
                    command_id,
                    timestamp,
                    device_id,
                    changes,
                    command.source,
                    command.reason,
                )
                self.storage.record_snapshot(self._snapshot)
            snapshot = self._snapshot.model_dump(mode="json")
        if changes:
            await self.broker.publish(
                "state_changed",
                {
                    "changed_paths": [change.path for change in changes],
                    "snapshot_version": snapshot["version"],
                    "snapshot": snapshot,
                    "command_id": command_id,
                },
            )
        return result

    async def preview_scene(
        self,
        scene: RoomSceneTargets,
        *,
        allow_large_changes: bool,
    ) -> tuple[RoomSnapshot, list[ChangedValue]]:
        async with self._lock:
            return apply_room_scene(
                self._snapshot,
                scene,
                allow_large_changes=allow_large_changes,
            )

    async def command_scene(
        self,
        scene: RoomSceneTargets,
        *,
        source: str,
        allow_large_changes: bool,
    ) -> CommandResult:
        async with self._lock:
            updated, changes = apply_room_scene(
                self._snapshot,
                scene,
                allow_large_changes=allow_large_changes,
            )
            timestamp = self._snapshot.timestamp
            command_id = str(uuid4())
            if changes:
                self._snapshot = updated.model_copy(update={"timestamp": timestamp})
                if scene.desk_computer_power is not None:
                    self._computer_schedule_enabled = False
                self.storage.record_changes(
                    command_id,
                    timestamp,
                    "room_scene",
                    changes,
                    source,
                    scene.reason,
                )
                self.storage.record_snapshot(self._snapshot)
            result = CommandResult(
                command_id=command_id,
                device_id="room_scene",
                source=source,
                timestamp=timestamp,
                changed=changes,
                snapshot_version=self._snapshot.version,
            )
            snapshot = self._snapshot.model_dump(mode="json")
        if changes:
            await self.broker.publish(
                "state_changed",
                {
                    "changed_paths": [change.path for change in changes],
                    "snapshot_version": snapshot["version"],
                    "snapshot": snapshot,
                    "command_id": command_id,
                },
            )
        return result

    async def tick(self) -> RoomSnapshot:
        async with self._lock:
            minutes = self.minutes_per_tick * self._speed
            timestamp = self._snapshot.timestamp + timedelta(minutes=minutes)
            if self._active_scenario:
                self._scenario_elapsed += minutes
                self._apply_due_scenario_actions_unlocked()
                if self._scenario_elapsed >= self._active_scenario.duration_minutes:
                    self._active_scenario = None
                    self._scenario_elapsed = 0
                    self._applied_scenario_actions.clear()
                    self._context_override = None
            self._snapshot = advance_snapshot(
                self._snapshot,
                timestamp,
                self._rng,
                minutes,
                use_schedule=self._active_scenario is None,
                use_computer_schedule=self._computer_schedule_enabled,
                context_override=self._context_override,
            )
            self.storage.record_snapshot(self._snapshot)
            snapshot = self._snapshot.model_dump(mode="json")
            status = self._status_unlocked().model_dump(mode="json")
        await self.broker.publish(
            "state_changed",
            {
                "changed_paths": ["environment", "timestamp"],
                "snapshot_version": snapshot["version"],
                "snapshot": snapshot,
            },
        )
        await self.broker.publish("simulation", status)
        return self._snapshot

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.tick_seconds)
            if self._running:
                await self.tick()

    def _status_unlocked(self) -> SimulationStatus:
        return SimulationStatus(
            running=self._running,
            seed=self.seed,
            speed=self._speed,
            simulated_time=self._snapshot.timestamp,
            active_scenario_id=self._active_scenario.id if self._active_scenario else None,
            scenario_elapsed_minutes=self._scenario_elapsed,
        )

    def _apply_due_scenario_actions_unlocked(self) -> None:
        if not self._active_scenario:
            return
        changes: dict[str, Any] = {}
        for index, action in enumerate(self._active_scenario.actions):
            if index in self._applied_scenario_actions or action.at_minute > self._scenario_elapsed:
                continue
            changes[action.target] = deepcopy(action.value)
            self._applied_scenario_actions.add(index)
        if changes:
            self._snapshot, self._context_override = apply_path_changes(
                self._snapshot,
                changes,
                self._context_override,
            )


def apply_path_changes(
    snapshot: RoomSnapshot,
    changes: dict[str, Any],
    context_override: str | None,
) -> tuple[RoomSnapshot, str | None]:
    data = snapshot.model_dump(mode="python")
    for path, value in changes.items():
        if path == "inferred_context":
            context_override = str(value)
            continue
        parts = path.split(".")
        target = data
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                raise CommandValidationError("Đường dẫn kịch bản không hợp lệ.", {"target": path})
            target = target[part]
        if parts[-1] not in target:
            raise CommandValidationError("Đường dẫn kịch bản không hợp lệ.", {"target": path})
        target[parts[-1]] = deepcopy(value)

    if "openings.curtain_position_percent" in changes:
        data["devices"]["curtain"]["position_percent"] = data["openings"]["curtain_position_percent"]
    if "devices.curtain" in changes:
        data["openings"]["curtain_position_percent"] = data["devices"]["curtain"]["position_percent"]
    if "power.computer_power_watts" in changes:
        watts = data["power"]["computer_power_watts"]
        data["power"]["smart_plugs"]["desk_computer"] = {
            "state": "on" if watts else "off",
            "power_watts": watts,
        }

    try:
        candidate = RoomSnapshot.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        raise CommandValidationError(
            "Kịch bản chứa giá trị không hợp lệ.",
            {"field": ".".join(map(str, first["loc"])), "message": first["msg"]},
        ) from error
    context, confidence = infer_context(candidate, context_override)
    updated = candidate.model_copy(
        update={"inferred_context": context, "context_confidence": confidence}
    )
    return updated, context_override


def prepare_baseline_data(
    storage: Storage,
    output_dir: Path,
    seed: int,
) -> None:
    snapshots = generate_baseline(seed)
    write_generated_csv(output_dir, snapshots)
    storage.seed_history(snapshots)
