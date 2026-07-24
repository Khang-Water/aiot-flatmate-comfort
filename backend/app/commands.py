from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from app.models import ChangedValue, RoomSceneTargets, RoomSnapshot

DEVICE_NAMES = {
    "ac",
    "fan",
    "main_light",
    "bedside_light",
    "air_purifier",
    "curtain",
    "humidity_device",
}
SMART_PLUG_WATTS = {"desk_computer": 140.0, "monitor": 32.0}

SCENE_STEPS = {
    "ac_temperature_c": 2,
    "fan_speed": 1,
    "main_light_brightness_percent": 20,
    "bedside_light_brightness_percent": 20,
    "air_purifier_speed": 1,
    "curtain_position_percent": 20,
}


class CommandValidationError(ValueError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


def apply_device_command(
    snapshot: RoomSnapshot,
    device_id: str,
    values: dict[str, Any],
) -> tuple[RoomSnapshot, list[ChangedValue]]:
    data = snapshot.model_dump(mode="python")

    if device_id == "window":
        unknown = set(values) - {"state"}
        state = values.get("state")
        if unknown or state not in {"open", "closed"}:
            raise CommandValidationError(
                "Cửa sổ chỉ hỗ trợ trạng thái open hoặc closed.",
                {"device_id": device_id, "fields": sorted(unknown), "value": state},
            )
        data["openings"]["window_state"] = state
        if state == "open":
            data["devices"]["ac"]["power"] = False
    elif device_id in DEVICE_NAMES:
        device = data["devices"][device_id]
        unknown = set(values) - set(device)
        if unknown:
            raise CommandValidationError(
                "Thiết bị không hỗ trợ thuộc tính được yêu cầu.",
                {"device_id": device_id, "fields": sorted(unknown)},
            )
        device.update(deepcopy(values))
        _normalize_device(device_id, device, values)
        if device_id == "ac" and device["power"]:
            data["openings"]["window_state"] = "closed"
        if device_id == "curtain":
            data["openings"]["curtain_position_percent"] = device["position_percent"]
    elif device_id in SMART_PLUG_WATTS:
        plug = data["power"]["smart_plugs"][device_id]
        unknown = set(values) - {"state"}
        if unknown:
            raise CommandValidationError(
                "Ổ cắm chỉ hỗ trợ thuộc tính state.",
                {"device_id": device_id, "fields": sorted(unknown)},
            )
        state = values.get("state")
        if state not in {"on", "off"}:
            raise CommandValidationError(
                "Trạng thái ổ cắm phải là on hoặc off.",
                {"device_id": device_id, "value": state},
            )
        plug["state"] = state
        plug["power_watts"] = SMART_PLUG_WATTS[device_id] if state == "on" else 0.0
        if device_id == "desk_computer":
            data["power"]["computer_power_watts"] = plug["power_watts"]
    else:
        raise CommandValidationError("Không tìm thấy thiết bị.", {"device_id": device_id})

    data["version"] += 1
    try:
        updated = RoomSnapshot.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        raise CommandValidationError(
            "Giá trị thiết bị không hợp lệ.",
            {"device_id": device_id, "field": ".".join(map(str, first["loc"])), "message": first["msg"]},
        ) from error

    changed = compare_device(snapshot, updated, device_id)
    if device_id == "window":
        changed.extend(compare_device(snapshot, updated, "ac"))
    elif device_id == "ac" and snapshot.openings.window_state != updated.openings.window_state:
        changed.extend(compare_device(snapshot, updated, "window"))
    if not changed:
        return snapshot, []
    return updated, changed


def apply_room_scene(
    snapshot: RoomSnapshot,
    scene: RoomSceneTargets,
    *,
    allow_large_changes: bool,
) -> tuple[RoomSnapshot, list[ChangedValue]]:
    targets = scene.model_dump(exclude={"change_mode", "reason"}, exclude_none=True)
    if not allow_large_changes:
        _validate_vague_steps(snapshot, targets)

    device_values: dict[str, dict[str, Any]] = {}
    if "ac_power" in targets or "ac_temperature_c" in targets:
        device_values["ac"] = {
            key.removeprefix("ac_"): value for key, value in targets.items() if key.startswith("ac_")
        }
    if "fan_power" in targets or "fan_speed" in targets:
        device_values["fan"] = {
            key.removeprefix("fan_"): value for key, value in targets.items() if key.startswith("fan_")
        }
    if any(key.startswith("main_light_") for key in targets):
        device_values["main_light"] = {
            key.removeprefix("main_light_"): value
            for key, value in targets.items()
            if key.startswith("main_light_")
        }
    if any(key.startswith("bedside_light_") for key in targets):
        device_values["bedside_light"] = {
            key.removeprefix("bedside_light_"): value
            for key, value in targets.items()
            if key.startswith("bedside_light_")
        }
    if "air_purifier_power" in targets or "air_purifier_speed" in targets:
        device_values["air_purifier"] = {
            key.removeprefix("air_purifier_"): value
            for key, value in targets.items()
            if key.startswith("air_purifier_")
        }
    if "curtain_position_percent" in targets:
        device_values["curtain"] = {"position_percent": targets["curtain_position_percent"]}
    if "window_state" in targets:
        device_values["window"] = {"state": targets["window_state"]}
    if "humidity_device_power" in targets or "target_humidity_percent" in targets:
        device_values["humidity_device"] = {
            **({"power": targets["humidity_device_power"]} if "humidity_device_power" in targets else {}),
            **(
                {"target_humidity_percent": targets["target_humidity_percent"]}
                if "target_humidity_percent" in targets
                else {}
            ),
        }
    if "desk_computer_power" in targets:
        device_values["desk_computer"] = {"state": "on" if targets["desk_computer_power"] else "off"}
    if "monitor_power" in targets:
        device_values["monitor"] = {"state": "on" if targets["monitor_power"] else "off"}

    updated = snapshot
    changes: list[ChangedValue] = []
    for device_id, values in device_values.items():
        updated, device_changes = apply_device_command(updated, device_id, values)
        changes.extend(device_changes)
    if not changes:
        return snapshot, []
    return updated.model_copy(update={"version": snapshot.version + 1}), changes


def _validate_vague_steps(snapshot: RoomSnapshot, targets: dict[str, Any]) -> None:
    current = {
        "ac_temperature_c": snapshot.devices.ac.temperature_c,
        "fan_speed": snapshot.devices.fan.speed,
        "main_light_brightness_percent": snapshot.devices.main_light.brightness_percent,
        "bedside_light_brightness_percent": snapshot.devices.bedside_light.brightness_percent,
        "air_purifier_speed": snapshot.devices.air_purifier.speed,
        "curtain_position_percent": snapshot.devices.curtain.position_percent,
    }
    for field, maximum_delta in SCENE_STEPS.items():
        if field in targets and abs(targets[field] - current[field]) > maximum_delta:
            raise CommandValidationError(
                "Yêu cầu mơ hồ thay đổi thiết bị quá mức cho phép.",
                {
                    "field": field,
                    "current": current[field],
                    "requested": targets[field],
                    "maximum_delta": maximum_delta,
                },
            )


def _normalize_device(device_id: str, device: dict[str, Any], supplied: dict[str, Any]) -> None:
    if device_id in {"fan", "air_purifier"}:
        if "speed" in supplied:
            device["power"] = device["speed"] > 0
        elif supplied.get("power") is False:
            device["speed"] = 0
        elif supplied.get("power") is True and device["speed"] == 0:
            device["speed"] = 1
    elif device_id in {"main_light", "bedside_light"}:
        if "brightness_percent" in supplied:
            device["power"] = device["brightness_percent"] > 0
        elif supplied.get("power") is False:
            device["brightness_percent"] = 0
        elif supplied.get("power") is True and device["brightness_percent"] == 0:
            device["brightness_percent"] = 20


def compare_device(before: RoomSnapshot, after: RoomSnapshot, device_id: str) -> list[ChangedValue]:
    if device_id == "window":
        old = {"window_state": before.openings.window_state}
        new = {"window_state": after.openings.window_state}
        prefix = "openings"
    elif device_id in DEVICE_NAMES:
        old = before.model_dump(mode="python")["devices"][device_id]
        new = after.model_dump(mode="python")["devices"][device_id]
        prefix = f"devices.{device_id}"
    else:
        old = before.model_dump(mode="python")["power"]["smart_plugs"][device_id]
        new = after.model_dump(mode="python")["power"]["smart_plugs"][device_id]
        prefix = f"power.smart_plugs.{device_id}"
    changes = [
        ChangedValue(path=f"{prefix}.{field}", before=old[field], after=new[field])
        for field in old
        if old[field] != new[field]
    ]
    if device_id == "curtain" and before.openings.curtain_position_percent != after.openings.curtain_position_percent:
        changes.append(
            ChangedValue(
                path="openings.curtain_position_percent",
                before=before.openings.curtain_position_percent,
                after=after.openings.curtain_position_percent,
            )
        )
    if device_id == "desk_computer" and before.power.computer_power_watts != after.power.computer_power_watts:
        changes.append(
            ChangedValue(
                path="power.computer_power_watts",
                before=before.power.computer_power_watts,
                after=after.power.computer_power_watts,
            )
        )
    return changes
