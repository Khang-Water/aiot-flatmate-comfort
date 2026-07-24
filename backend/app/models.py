from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnvironmentState(Model):
    temperature_c: float = Field(ge=10, le=45)
    humidity_percent: float = Field(ge=0, le=100)
    co2_ppm: float = Field(ge=300, le=10_000)
    pm25_ug_m3: float = Field(ge=0, le=1_000)
    ambient_light_lux: float = Field(ge=0, le=100_000)
    noise_db: float = Field(ge=0, le=140)


class OccupancyState(Model):
    room_present: bool
    bed_occupied: bool
    desk_occupied: bool


class OpeningsState(Model):
    window_state: Literal["open", "closed"]
    curtain_position_percent: int = Field(ge=0, le=100)


class SmartPlugState(Model):
    state: Literal["on", "off"]
    power_watts: float = Field(ge=0)


class PowerState(Model):
    computer_power_watts: float = Field(ge=0)
    smart_plugs: dict[str, SmartPlugState]


class AcState(Model):
    power: bool
    mode: Literal["cool", "dry", "fan", "auto"]
    temperature_c: float = Field(ge=18, le=30)
    fan_mode: Literal["low", "medium", "high", "auto"]


class FanState(Model):
    power: bool
    speed: int = Field(ge=0, le=3)
    oscillation: bool


class LightState(Model):
    power: bool
    brightness_percent: int = Field(ge=0, le=100)
    color_temperature_kelvin: int = Field(ge=2700, le=6500)


class SpeedDeviceState(Model):
    power: bool
    speed: int = Field(ge=0, le=3)


class CurtainState(Model):
    position_percent: int = Field(ge=0, le=100)


class HumidityDeviceState(Model):
    power: bool
    mode: Literal["humidify", "dehumidify"]
    target_humidity_percent: int = Field(ge=35, le=70)


class DeviceStates(Model):
    ac: AcState
    fan: FanState
    main_light: LightState
    bedside_light: LightState
    air_purifier: SpeedDeviceState
    curtain: CurtainState
    humidity_device: HumidityDeviceState


Context = Literal["working", "relaxing", "sleeping", "reading_in_bed", "away"]


class RoomSnapshot(Model):
    version: int = Field(ge=0)
    timestamp: datetime
    environment: EnvironmentState
    occupancy: OccupancyState
    openings: OpeningsState
    power: PowerState
    devices: DeviceStates
    inferred_context: Context
    context_confidence: float = Field(ge=0, le=1)


class DatabaseHealth(Model):
    ready: bool
    status: Literal["not_initialized", "ready", "error"]


class SimulationStatus(Model):
    running: bool
    phase: Literal["foundation", "simulation"] = "simulation"
    seed: int
    speed: Literal[1, 2, 5, 10]
    simulated_time: datetime
    active_scenario_id: str | None
    scenario_elapsed_minutes: int = Field(ge=0)


class HealthResponse(Model):
    status: Literal["ok"]
    version: str
    timestamp: datetime
    database: DatabaseHealth
    simulation: SimulationStatus
    openai_configured: bool
    openai_model: str


class SimulationControl(Model):
    action: Literal["pause", "resume", "reset", "set_speed"]
    speed: Literal[1, 2, 5, 10] | None = None

    @model_validator(mode="after")
    def validate_speed(self) -> "SimulationControl":
        if self.action == "set_speed" and self.speed is None:
            raise ValueError("speed is required for set_speed")
        if self.action != "set_speed" and self.speed is not None:
            raise ValueError("speed is only accepted for set_speed")
        return self


class ScenarioAction(Model):
    at_minute: int = Field(ge=0)
    target: str
    value: Any
    note: str = ""


class ScenarioDefinition(Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name_vi: str = Field(min_length=1)
    description_vi: str = Field(min_length=1)
    duration_minutes: int = Field(ge=1)
    actions: list[ScenarioAction] = Field(min_length=1)


class ScenarioSummary(Model):
    id: str
    name_vi: str
    description_vi: str
    duration_minutes: int


class ScenarioList(Model):
    active_scenario_id: str | None
    scenarios: list[ScenarioSummary]


class DeviceCommand(Model):
    values: dict[str, Any] = Field(min_length=1)
    source: Literal["manual", "assistant", "scenario"] = "manual"
    reason: str = ""


class ChangedValue(Model):
    path: str
    before: Any
    after: Any


class CommandResult(Model):
    command_id: str
    device_id: str
    source: str
    timestamp: datetime
    changed: list[ChangedValue]
    snapshot_version: int


class RoomSceneTargets(Model):
    change_mode: Literal["bounded", "explicit"]
    ac_power: bool | None = None
    ac_temperature_c: float | None = Field(default=None, ge=18, le=30)
    fan_power: bool | None = None
    fan_speed: int | None = Field(default=None, ge=0, le=3)
    main_light_power: bool | None = None
    main_light_brightness_percent: int | None = Field(default=None, ge=0, le=100)
    main_light_color_temperature_kelvin: int | None = Field(default=None, ge=2700, le=6500)
    bedside_light_power: bool | None = None
    bedside_light_brightness_percent: int | None = Field(default=None, ge=0, le=100)
    bedside_light_color_temperature_kelvin: int | None = Field(default=None, ge=2700, le=6500)
    air_purifier_power: bool | None = None
    air_purifier_speed: int | None = Field(default=None, ge=0, le=3)
    curtain_position_percent: int | None = Field(default=None, ge=0, le=100)
    window_state: Literal["open", "closed"] | None = None
    humidity_device_power: bool | None = None
    target_humidity_percent: int | None = Field(default=None, ge=35, le=70)
    desk_computer_power: bool | None = None
    monitor_power: bool | None = None
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_target(self) -> "RoomSceneTargets":
        targets = self.model_dump(exclude={"change_mode", "reason"}, exclude_none=True)
        if not targets:
            raise ValueError("at least one room target is required")
        if self.window_state == "open" and self.ac_power is True:
            raise ValueError("cannot open window while AC is powered on")
        for power_field, level_field in (
            ("fan_power", "fan_speed"),
            ("main_light_power", "main_light_brightness_percent"),
            ("bedside_light_power", "bedside_light_brightness_percent"),
            ("air_purifier_power", "air_purifier_speed"),
        ):
            power = getattr(self, power_field)
            level = getattr(self, level_field)
            if power is False and level not in {None, 0}:
                raise ValueError(f"{power_field}=false requires {level_field}=0 or null")
            if power is True and level == 0:
                raise ValueError(f"{power_field}=true requires {level_field}>0 or null")
        return self


PreferenceContext = Literal["working", "relaxing", "sleeping", "reading_in_bed", "away", "any"]
PreferenceSource = Literal["explicit", "temporary", "user_correction", "learned"]


class PreferenceTargets(Model):
    ac_power: bool | None = None
    ac_temperature_c: float | None = Field(default=None, ge=18, le=30)
    fan_power: bool | None = None
    fan_speed: int | None = Field(default=None, ge=0, le=3)
    main_light_power: bool | None = None
    main_light_brightness_percent: int | None = Field(default=None, ge=0, le=100)
    main_light_color_temperature_kelvin: int | None = Field(default=None, ge=2700, le=6500)
    bedside_light_power: bool | None = None
    bedside_light_brightness_percent: int | None = Field(default=None, ge=0, le=100)
    bedside_light_color_temperature_kelvin: int | None = Field(default=None, ge=2700, le=6500)
    air_purifier_power: bool | None = None
    air_purifier_speed: int | None = Field(default=None, ge=0, le=3)
    curtain_position_percent: int | None = Field(default=None, ge=0, le=100)
    window_state: Literal["open", "closed"] | None = None
    humidity_device_power: bool | None = None
    target_humidity_percent: int | None = Field(default=None, ge=35, le=70)
    desk_computer_power: bool | None = None
    monitor_power: bool | None = None

    @model_validator(mode="after")
    def validate_targets(self) -> "PreferenceTargets":
        values = self.model_dump(exclude_none=True)
        if not values:
            raise ValueError("at least one preference target is required")
        RoomSceneTargets.model_validate(
            {"change_mode": "explicit", "reason": "Sở thích người dùng", **values}
        )
        return self


class PreferenceCreate(Model):
    context: PreferenceContext
    requested_intent: str = Field(min_length=1, max_length=300)
    preferred_result: PreferenceTargets
    source: Literal["explicit", "temporary"] = "explicit"
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_expiry(self) -> "PreferenceCreate":
        if self.source == "temporary" and self.expires_at is None:
            raise ValueError("temporary preference requires expires_at")
        return self


class PreferenceUpdate(Model):
    context: PreferenceContext | None = None
    requested_intent: str | None = Field(default=None, min_length=1, max_length=300)
    preferred_result: PreferenceTargets | None = None
    source: Literal["explicit", "temporary"] | None = None
    expires_at: datetime | None = None


class PreferenceRecord(Model):
    id: str
    context: PreferenceContext
    requested_intent: str
    preferred_result: PreferenceTargets
    source: PreferenceSource
    confidence: float = Field(ge=0, le=1)
    observation_count: int = Field(ge=0)
    confirmed: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None


class PreferenceList(Model):
    preferences: list[PreferenceRecord]


class PreferenceReset(Model):
    confirm: bool


class PreferenceResetResult(Model):
    deleted: int = Field(ge=0)


class HistoryPoint(Model):
    timestamp: datetime
    value: float
    unit: str


class HistoryResponse(Model):
    metric: str
    points: list[HistoryPoint]


AssistantSource = Literal["voice", "text"]
TraceStatus = Literal["started", "completed", "failed", "skipped"]
TraceStage = Literal[
    "wake_detected",
    "speech_captured",
    "transcript_final",
    "context_inferred",
    "snapshot_read",
    "preference_retrieved",
    "model_requested",
    "tool_requested",
    "validation_completed",
    "action_applied",
    "state_updated",
    "preference_recorded",
    "assistant_response",
    "speech_started",
    "speech_completed",
]


class AssistantRequest(Model):
    text: str = Field(min_length=1, max_length=2_000)
    source: AssistantSource = "text"
    session_id: str = Field(min_length=1, max_length=200)


class AssistantAccepted(Model):
    request_id: str
    status: Literal["accepted"] = "accepted"


class SpeechRequest(Model):
    text: str = Field(min_length=1, max_length=2_000)


class TranscriptionResponse(Model):
    text: str
    language: str
    language_probability: float = Field(ge=0, le=1)
    duration_seconds: float = Field(ge=0)


class TraceError(Model):
    code: str
    message: str


class AssistantTraceEvent(Model):
    id: str
    request_id: str
    sequence: int = Field(ge=0)
    timestamp: datetime
    duration_ms: int | None = Field(default=None, ge=0)
    stage: TraceStage
    status: TraceStatus
    title_vi: str = Field(min_length=1)
    summary_vi: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    error: TraceError | None = None


class ConversationRecord(Model):
    request_id: str
    session_id: str
    source: AssistantSource
    user_text: str
    assistant_text: str
    status: Literal["processing", "completed", "failed"]
    error_message: str
    created_at: datetime
    completed_at: datetime | None


class ConversationList(Model):
    conversations: list[ConversationRecord]


class ErrorBody(Model):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(Model):
    error: ErrorBody
