import asyncio
import json
import re
from contextlib import suppress
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.commands import CommandValidationError, apply_room_scene
from app.models import (
    AssistantAccepted,
    AssistantRequest,
    AssistantTraceEvent,
    ChangedValue,
    Context,
    PreferenceCreate,
    PreferenceRecord,
    PreferenceTargets,
    RoomSceneTargets,
    RoomSnapshot,
    TraceError,
)
from app.simulation import SimulationEngine
from app.state import EventBroker
from app.storage import Storage

BANGKOK = ZoneInfo("Asia/Bangkok")


def assistant_snapshot(snapshot: RoomSnapshot) -> dict[str, Any]:
    data = snapshot.model_dump(mode="json")
    data.pop("inferred_context", None)
    data.pop("context_confidence", None)
    return data


CONTEXT_TERMS: tuple[tuple[Context, tuple[str, ...]], ...] = (
    ("reading_in_bed", ("đọc sách trên giường", "đọc trên giường", "đọc sách ở giường")),
    ("working", ("làm việc", "công việc", "bàn làm việc")),
    ("sleeping", ("đi ngủ", "ngủ", "giờ ngủ")),
    ("relaxing", ("thư giãn", "nghỉ ngơi", "xem phim")),
    ("away", ("ra ngoài", "rời nhà", "vắng nhà", "đi chơi")),
)
LIGHT_PERCENT_RE = re.compile(r"(?P<value>\d{1,3})\s*(?:%|phần\s*trăm)", re.IGNORECASE)
LIGHT_KELVIN_RE = re.compile(r"(?P<value>\d{4})\s*(?:k|kelvin)\b", re.IGNORECASE)
EXPLICIT_SETTING_RE = re.compile(
    r"(?:\d+(?:[.,]\d+)?\s*(?:%|phần\s*trăm|°\s*c|độ(?:\s*c)?|k|kelvin)|mức\s*\d+)",
    re.IGNORECASE,
)
LIGHT_FIELDS = {
    "main_light": (
        "main_light_power",
        "main_light_brightness_percent",
        "main_light_color_temperature_kelvin",
    ),
    "bedside_light": (
        "bedside_light_power",
        "bedside_light_brightness_percent",
        "bedside_light_color_temperature_kelvin",
    ),
}
EMPTY_PREFERENCE_IDS = {"", ".", "n/a", "na", "none", "null", "undefined"}


def infer_request_context(text: str, fallback: Context) -> Context:
    lowered = text.casefold()
    for context, terms in CONTEXT_TERMS:
        if any(term in lowered for term in terms):
            return context
    return fallback


def explicit_light_scene_targets(text: str) -> dict[str, Any]:
    """Return only high-confidence Vietnamese light targets."""
    lowered = text.casefold()
    if not any(term in lowered for term in ("đèn", "ánh sáng")):
        return {}
    if any(
        term in lowered
        for term in ("hãy nhớ", "ghi nhớ", "lưu sở thích", "nhớ rằng", "từ giờ", "về sau", "luôn để")
    ):
        return {}
    if any(
        term in lowered
        for term in ("bao nhiêu", "hiện tại là", "có phải", "muốn biết", "có phù hợp")
    ):
        return {}
    if "?" in lowered and any(term in lowered for term in ("đang", "màu gì", "trạng thái")):
        return {}

    bedside = any(term in lowered for term in ("đèn đầu giường", "đèn ngủ", "đèn cạnh giường"))
    main = any(term in lowered for term in ("đèn chính", "đèn trần"))
    if bedside and main:
        return {}
    prefix = "bedside_light" if bedside else "main_light"

    percent_match = LIGHT_PERCENT_RE.search(lowered)
    brightness = int(percent_match.group("value")) if percent_match else None
    if brightness is not None and not 0 <= brightness <= 100:
        return {}

    kelvin_match = LIGHT_KELVIN_RE.search(lowered)
    kelvin = int(kelvin_match.group("value")) if kelvin_match else None
    if kelvin is not None and not 2700 <= kelvin <= 6500:
        return {}
    if kelvin is None:
        if any(term in lowered for term in ("trắng lạnh", "ánh sáng lạnh", "màu lạnh")):
            kelvin = 6500
        elif any(term in lowered for term in ("trung tính", "trắng tự nhiên")):
            kelvin = 4000
        elif any(
            term in lowered
            for term in ("trắng ấm", "màu ấm", "đèn vàng", "ánh sáng vàng", "màu vàng")
        ):
            kelvin = 2700

    action_requested = any(
        term in lowered for term in ("bật", "tắt", "chỉnh", "đặt", "đổi", "cho", "tăng", "giảm", "muốn")
    )
    short_command = len(lowered) <= 40 and (brightness is not None or kelvin is not None)
    if not action_requested and not short_command:
        return {}

    power: bool | None = None
    turn_off = "tắt" in lowered and not any(term in lowered for term in ("không tắt", "đừng tắt"))
    turn_on = "bật" in lowered and not any(term in lowered for term in ("không bật", "đừng bật"))
    if turn_off:
        power = False
        brightness = 0
        kelvin = None
    elif turn_on or brightness is not None or kelvin is not None:
        power = True

    # ponytail: high-confidence light phrases only; add a real Vietnamese intent grammar when devices grow.
    if power is None and brightness is None and kelvin is None:
        return {}
    return {
        f"{prefix}_power": power,
        f"{prefix}_brightness_percent": brightness,
        f"{prefix}_color_temperature_kelvin": kelvin,
    }


def is_work_preparation(text: str) -> bool:
    lowered = text.casefold()
    return any(
        phrase in lowered
        for phrase in ("chuẩn bị làm việc", "bắt đầu làm việc", "vào làm việc", "làm việc đây")
    ) and not any(phrase in lowered for phrase in ("không làm việc", "chưa làm việc"))


def request_requires_explicit_mode(text: str) -> bool:
    lowered = text.casefold()
    if any(term in lowered for term in ("bao nhiêu", "muốn biết", "có phù hợp", "có phải")):
        return False
    action_requested = any(
        term in lowered for term in ("bật", "tắt", "chỉnh", "đặt", "đổi", "cho", "tăng", "giảm", "muốn")
    )
    return action_requested and EXPLICIT_SETTING_RE.search(lowered) is not None


def request_scene_overrides(
    text: str,
    snapshot: RoomSnapshot,
    relevant_preferences: list[PreferenceRecord],
) -> tuple[dict[str, Any], str | None]:
    overrides: dict[str, Any] = {}
    applied_preference_id: str | None = None
    light_targets = explicit_light_scene_targets(text)

    if is_work_preparation(text):
        overrides.update(desk_computer_power=True, monitor_power=True)
        lowered = text.casefold()
        if snapshot.environment.ambient_light_lux < 300 and not any(
            phrase in lowered for phrase in ("không bật đèn", "đừng bật đèn", "không cần đèn")
        ):
            overrides.update(
                main_light_power=True,
                main_light_brightness_percent=70,
                main_light_color_temperature_kelvin=4000,
            )
        if relevant_preferences and not light_targets:
            preference = relevant_preferences[0]
            overrides.update(preference.preferred_result.model_dump(exclude_none=True))
            applied_preference_id = preference.id

    overrides.update(light_targets)
    return overrides, applied_preference_id


def resolve_scene_arguments(
    arguments: dict[str, Any],
    overrides: dict[str, Any],
    *,
    force_explicit: bool,
) -> dict[str, Any]:
    resolved = dict(arguments)
    if any(field in overrides for field in LIGHT_FIELDS["main_light"]):
        resolved.update(dict.fromkeys(LIGHT_FIELDS["bedside_light"]))
    if any(field in overrides for field in LIGHT_FIELDS["bedside_light"]):
        resolved.update(dict.fromkeys(LIGHT_FIELDS["main_light"]))
    resolved.update(overrides)
    if force_explicit or overrides:
        resolved["change_mode"] = "explicit"
    if overrides and not resolved.get("reason"):
        resolved["reason"] = "Thực hiện giá trị rõ ràng người dùng đã yêu cầu."
    return resolved


def normalize_optional_preference_id(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("applied_preference_id phải là chuỗi hoặc null.")
    normalized = value.strip()
    return None if normalized.casefold() in EMPTY_PREFERENCE_IDS else normalized


def snapshot_satisfies_preference(snapshot: RoomSnapshot, preference: PreferenceRecord) -> bool:
    preference_scene = RoomSceneTargets(
        change_mode="explicit",
        reason="Kiểm tra preference sau preview.",
        **preference.preferred_result.model_dump(exclude_none=True),
    )
    _, missing_changes = apply_room_scene(snapshot, preference_scene, allow_large_changes=True)
    return not missing_changes


def action_confirmation(
    changes: list[ChangedValue],
    *,
    context: Context,
    preference_saved: bool,
    preference_used: bool,
) -> str:
    facts = [fact for change in changes if (fact := _change_fact(change))]
    if not facts:
        response = "Thiết bị đã ở đúng trạng thái bạn yêu cầu, nên tôi giữ nguyên để tránh thay đổi thừa."
    else:
        response = f"Tôi đã hoàn tất: {'; '.join(facts)}."
    if preference_saved:
        return f"{response} Tôi cũng đã ghi nhớ chỉnh sửa này cho đúng ngữ cảnh."
    if preference_used:
        return f"{response} Tôi cũng đã áp dụng sở thích phù hợp đã ghi nhớ cho bạn."
    main_light_turned_off = any(
        change.path == "devices.main_light.power" and change.after is False
        for change in changes
    )
    work_light_prepared = not main_light_turned_off and any(
        change.path == "devices.main_light.power" and change.after is True
        or change.path == "devices.main_light.brightness_percent" and change.after > 0
        or change.path == "devices.main_light.color_temperature_kelvin"
        for change in changes
    )
    if context == "working" and work_light_prepared:
        return f"{response} Không gian làm việc đã sẵn sàng; nếu thấy vừa mắt, bạn có thể bảo tôi ghi nhớ mức này."
    return response


def _change_fact(change: ChangedValue) -> str | None:
    path = change.path
    value = change.after
    power_labels = {
        "devices.ac.power": "điều hòa",
        "devices.fan.power": "quạt",
        "devices.main_light.power": "đèn chính",
        "devices.bedside_light.power": "đèn đầu giường",
        "devices.air_purifier.power": "máy lọc không khí",
        "devices.humidity_device.power": "thiết bị độ ẩm",
    }
    if path in power_labels:
        return f"{power_labels[path]} {'bật' if value else 'tắt'}"
    if path == "devices.ac.temperature_c":
        return f"điều hòa {value:g}°C"
    if path == "devices.fan.speed":
        return f"quạt mức {value}"
    if path == "devices.main_light.brightness_percent":
        return f"đèn chính {value}%"
    if path == "devices.main_light.color_temperature_kelvin":
        return f"đèn chính màu {_light_color_name(value)} {value}K"
    if path == "devices.bedside_light.brightness_percent":
        return f"đèn đầu giường {value}%"
    if path == "devices.bedside_light.color_temperature_kelvin":
        return f"đèn đầu giường màu {_light_color_name(value)} {value}K"
    if path == "devices.air_purifier.speed":
        return f"máy lọc không khí mức {value}"
    if path == "devices.curtain.position_percent":
        return f"rèm mở {value}%"
    if path == "openings.window_state":
        return f"cửa sổ {'mở' if value == 'open' else 'đóng'}"
    if path == "devices.humidity_device.target_humidity_percent":
        return f"độ ẩm mục tiêu {value}%"
    if path == "power.smart_plugs.desk_computer.state":
        return f"máy tính bàn {'bật' if value == 'on' else 'tắt'}"
    if path == "power.smart_plugs.monitor.state":
        return f"màn hình {'bật' if value == 'on' else 'tắt'}"
    return None


def _light_color_name(kelvin: int) -> str:
    if kelvin <= 3000:
        return "vàng ấm"
    if kelvin <= 4500:
        return "trắng trung tính"
    return "trắng lạnh"


PREFERENCE_TARGET_PROPERTIES: dict[str, Any] = {
    "ac_power": {"type": ["boolean", "null"]},
    "ac_temperature_c": {"type": ["number", "null"], "minimum": 18, "maximum": 30},
    "fan_power": {"type": ["boolean", "null"]},
    "fan_speed": {"type": ["integer", "null"], "minimum": 0, "maximum": 3},
    "main_light_power": {"type": ["boolean", "null"]},
    "main_light_brightness_percent": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
    "main_light_color_temperature_kelvin": {
        "type": ["integer", "null"], "minimum": 2700, "maximum": 6500,
    },
    "bedside_light_power": {"type": ["boolean", "null"]},
    "bedside_light_brightness_percent": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
    "bedside_light_color_temperature_kelvin": {
        "type": ["integer", "null"], "minimum": 2700, "maximum": 6500,
    },
    "air_purifier_power": {"type": ["boolean", "null"]},
    "air_purifier_speed": {"type": ["integer", "null"], "minimum": 0, "maximum": 3},
    "curtain_position_percent": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
    "window_state": {"type": ["string", "null"], "enum": ["open", "closed", None]},
    "humidity_device_power": {"type": ["boolean", "null"]},
    "target_humidity_percent": {"type": ["integer", "null"], "minimum": 35, "maximum": 70},
    "desk_computer_power": {"type": ["boolean", "null"]},
    "monitor_power": {"type": ["boolean", "null"]},
}
PREFERENCE_TARGET_REQUIRED = list(PREFERENCE_TARGET_PROPERTIES)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_relevant_preferences",
        "description": "Đọc sở thích đang có hiệu lực cho ngữ cảnh mà bạn xác định từ toàn bộ yêu cầu.",
        "parameters": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "enum": ["working", "relaxing", "sleeping", "reading_in_bed", "away", "any"],
                },
            },
            "required": ["context"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "save_preference",
        "description": "Lưu sở thích khi người dùng nói rõ muốn hệ thống ghi nhớ lâu dài hoặc tạm thời.",
        "parameters": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "enum": ["working", "relaxing", "sleeping", "reading_in_bed", "away", "any"],
                },
                "requested_intent": {"type": "string", "minLength": 1, "maxLength": 300},
                "source": {"type": "string", "enum": ["explicit", "temporary"]},
                "duration_hours": {"type": ["number", "null"], "minimum": 0.25, "maximum": 720},
                "preferred_result": {
                    "type": "object",
                    "properties": PREFERENCE_TARGET_PROPERTIES,
                    "required": PREFERENCE_TARGET_REQUIRED,
                    "additionalProperties": False,
                },
            },
            "required": ["context", "requested_intent", "source", "duration_hours", "preferred_result"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "record_preference_correction",
        "description": "Lưu preference học được khi người dùng sửa kết quả trước đó.",
        "parameters": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "enum": ["working", "relaxing", "sleeping", "reading_in_bed", "away", "any"],
                },
                "requested_intent": {"type": "string", "minLength": 1, "maxLength": 300},
                "preferred_result": {
                    "type": "object",
                    "properties": PREFERENCE_TARGET_PROPERTIES,
                    "required": PREFERENCE_TARGET_REQUIRED,
                    "additionalProperties": False,
                },
            },
            "required": ["context", "requested_intent", "preferred_result"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_room_snapshot",
        "description": "Đọc toàn bộ cảm biến, ngữ cảnh và trạng thái thiết bị hiện tại trước khi quyết định.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_recent_actions",
        "description": "Đọc các thay đổi thiết bị gần nhất khi cần hiểu tham chiếu như 'giảm thêm' hoặc 'như trước'.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            "required": ["limit"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "set_room_scene",
        "description": (
            "Đề xuất một thay đổi nguyên tử cho các thiết bị mô phỏng. "
            "Giá trị null hoặc trường bị bỏ qua giữ nguyên thiết bị."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "change_mode": {"type": "string", "enum": ["bounded", "explicit"]},
                "ac_power": {"type": ["boolean", "null"]},
                "ac_temperature_c": {"type": ["number", "null"], "minimum": 18, "maximum": 30},
                "fan_power": {"type": ["boolean", "null"]},
                "fan_speed": {"type": ["integer", "null"], "minimum": 0, "maximum": 3},
                "main_light_power": {"type": ["boolean", "null"]},
                "main_light_brightness_percent": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
                "main_light_color_temperature_kelvin": {"type": ["integer", "null"], "minimum": 2700, "maximum": 6500},
                "bedside_light_power": {"type": ["boolean", "null"]},
                "bedside_light_brightness_percent": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
                "bedside_light_color_temperature_kelvin": {
                    "type": ["integer", "null"],
                    "minimum": 2700,
                    "maximum": 6500,
                },
                "air_purifier_power": {"type": ["boolean", "null"]},
                "air_purifier_speed": {"type": ["integer", "null"], "minimum": 0, "maximum": 3},
                "curtain_position_percent": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
                "window_state": {"type": ["string", "null"], "enum": ["open", "closed", None]},
                "humidity_device_power": {"type": ["boolean", "null"]},
                "target_humidity_percent": {"type": ["integer", "null"], "minimum": 35, "maximum": 70},
                "desk_computer_power": {"type": ["boolean", "null"]},
                "monitor_power": {"type": ["boolean", "null"]},
                "applied_preference_id": {
                    "type": ["string", "null"],
                    "description": (
                        "ID preference đã dùng. Gửi null hoặc bỏ trường khi không dùng; "
                        "không gửi chuỗi 'null' hay chuỗi rỗng."
                    ),
                },
                "reason": {"type": "string", "minLength": 1, "maxLength": 500},
            },
            "required": [
                "change_mode",
                "ac_power",
                "ac_temperature_c",
                "fan_power",
                "fan_speed",
                "main_light_power",
                "main_light_brightness_percent",
                "main_light_color_temperature_kelvin",
                "bedside_light_power",
                "bedside_light_brightness_percent",
                "bedside_light_color_temperature_kelvin",
                "air_purifier_power",
                "air_purifier_speed",
                "curtain_position_percent",
                "window_state",
                "humidity_device_power",
                "target_humidity_percent",
                "desk_computer_power",
                "monitor_power",
                "applied_preference_id",
                "reason",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def _compatible_schema(schema: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties", {})
    nullable = {
        name
        for name, value in properties.items()
        if isinstance(value.get("type"), list) and "null" in value["type"]
    }
    compatible: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "additionalProperties":
            continue
        if key == "type" and isinstance(value, list):
            types = [item for item in value if item != "null"]
            value = types[0] if len(types) == 1 else types
        elif key == "enum" and isinstance(value, list):
            value = [item for item in value if item is not None]
        elif key == "required" and isinstance(value, list):
            value = [item for item in value if item not in nullable]
            if not value:
                continue
        elif isinstance(value, dict):
            value = _compatible_schema(value)
        elif isinstance(value, list):
            value = [_compatible_schema(item) if isinstance(item, dict) else item for item in value]
        compatible[key] = value
    return compatible


# ponytail: shared Gemini-compatible schema; route schemas per provider if strict validation becomes necessary.
PROVIDER_TOOLS = [
    {
        key: _compatible_schema(value) if key == "parameters" else value
        for key, value in tool.items()
        if key != "strict"
    }
    for tool in TOOLS
]
CHAT_TOOLS = [
    {
        "type": "function",
        "function": {key: value for key, value in tool.items() if key != "type"},
    }
    for tool in PROVIDER_TOOLS
]

INSTRUCTIONS = """
Bạn là FlatMate Comfort, trợ lý cho một căn hộ studio mô phỏng.

Mục tiêu:
- Hiểu yêu cầu tiếng Việt và chuyển thành giá trị thiết bị cụ thể.
- Luôn gọi get_room_snapshot trước khi đề xuất thay đổi.
- Chỉ một set_room_scene hợp lệ được áp dụng. Nếu validation từ chối, đọc lỗi và được thử lại một lần
  với giá trị đã sửa trong giới hạn.
- Dùng get_recent_actions khi yêu cầu nhắc đến thay đổi trước đó.
- Backend đã xác định context và cung cấp preference phù hợp. Có thể gọi get_relevant_preferences để đọc lại chi tiết.
- Thứ tự ưu tiên preference: explicit, temporary, user_correction, rồi learned.
- Nếu nhiều preference cùng source và scope phù hợp, dùng bản updated_at mới nhất.
- Chỉ áp dụng preference khi requested_intent phù hợp yêu cầu hiện tại; không áp dụng chỉ vì cùng context.
- Khi dùng preference, truyền id của nó vào applied_preference_id trong set_room_scene. Nếu không dùng,
  gửi null khi schema cho phép hoặc bỏ trường; không gửi chuỗi "null", chuỗi rỗng hay ký hiệu thay thế.
- Chỉ gọi save_preference khi người dùng yêu cầu ghi nhớ rõ ràng. temporary phải có duration_hours.
- Khi người dùng sửa kết quả trước đó, gọi record_preference_correction với intent chuẩn hóa ổn định và target mới.
- Khi correction thể hiện sở thích hữu ích, lưu và cho phép áp dụng ngay; không yêu cầu xác nhận riêng.
- Lịch sử hội thoại chỉ dùng để hiểu tham chiếu và ngữ cảnh hiện tại; không lặp lại lệnh cũ.
- Không thay đổi thiết bị không liên quan; dùng null hoặc bỏ trường nếu schema provider không hỗ trợ null.
- Nếu yêu cầu chưa đủ rõ để xác định thiết bị hoặc trạng thái, hỏi lại và không gọi set_room_scene.
- Tự phân loại ý định từ toàn bộ câu và dữ liệu sensor; không dựa vào danh sách từ khóa từ backend.
- Dùng change_mode="explicit" khi user nói rõ trạng thái, giá trị hoặc phạm vi cần đổi.
- Dùng change_mode="bounded" cho yêu cầu cảm tính như "hơi nóng" hoặc "sáng hơn một chút".
- Với bounded, mức đổi tối đa từ trạng thái hiện tại: AC 2°C; quạt 1 mức; độ sáng đèn 20%;
  máy lọc 1 mức; rèm 20%. Nếu mong muốn lớn hơn, áp dụng mức an toàn tối đa ngay lần đầu.
- "Tắt tất cả" nghĩa là tắt mọi thiết bị dùng điện và hai ổ cắm; không tự đổi rèm hoặc cửa sổ.
- Không nói AC hoặc máy lọc loại bỏ CO2. CO2 cao cần thông gió.
- Dùng window_state="open" khi người dùng yêu cầu mở cửa sổ.
- Khi mở cửa sổ để thông gió, đặt ac_power=false trong cùng scene.
- Khi bật AC hoặc làm lạnh, đặt window_state="closed" trong cùng scene.
- Không bao giờ đề xuất window_state="open" cùng ac_power=true.
- Không yêu cầu giá trị ngoài schema. Điều hòa chỉ nhận 18–30°C.
- Với đèn: vàng/trắng ấm = 2700K; trắng trung tính = 4000K; trắng lạnh = 6500K.
- Khi người dùng chuẩn bị làm việc, bật máy tính và màn hình; nếu ánh sáng dưới 300 lux thì chuẩn bị
  đèn chính 70%, 4000K, trừ khi người dùng hoặc preference yêu cầu khác.
- Lý do trong set_room_scene phải ngắn, bằng tiếng Việt, dựa trên dữ liệu quan sát được.
- Phản hồi cuối bằng tiếng Việt, thân thiện và chu đáo trong 1–3 câu. Xác nhận đúng giá trị tool trả về,
  không nói đã đổi thuộc tính không xuất hiện trong changed.
- Sau khi hoàn tất, có thể gợi ý một bước hữu ích sát ngữ cảnh như ghi nhớ thiết lập; không dài dòng.
- Không xuất chuỗi suy luận nội bộ. Chỉ cung cấp lý do ngắn và kết quả quan sát được.

Dừng khi đã có đủ dữ liệu và một phản hồi cuối hữu ích.
""".strip()


class AssistantNotConfigured(RuntimeError):
    pass


class AssistantBusy(RuntimeError):
    pass


class AssistantWorkflowError(RuntimeError):
    pass


class AssistantOrchestrator:
    def __init__(
        self,
        *,
        client: AsyncOpenAI | Any | None,
        model: str,
        api_mode: str = "responses",
        reasoning_effort: str,
        timeout_seconds: float,
        engine: SimulationEngine,
        storage: Storage,
        broker: EventBroker,
    ) -> None:
        self.client = client
        self.model = model
        self.api_mode = api_mode
        self.reasoning_effort = reasoning_effort
        self.timeout_seconds = timeout_seconds
        self.engine = engine
        self.storage = storage
        self.broker = broker
        self._active_task: asyncio.Task[None] | None = None
        self._submit_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return self.client is not None

    async def submit(self, request: AssistantRequest) -> AssistantAccepted:
        if not self.configured:
            raise AssistantNotConfigured("OPENAI_API_KEY chưa được cấu hình.")
        async with self._submit_lock:
            if self._active_task and not self._active_task.done():
                raise AssistantBusy("Trợ lý đang xử lý một yêu cầu khác.")
            request_id = str(uuid4())
            created_at = datetime.now(BANGKOK)
            self.storage.start_conversation(
                request_id,
                request.session_id,
                request.source,
                request.text,
                created_at,
            )
            self._active_task = asyncio.create_task(
                self._run(request_id, request),
                name=f"assistant-{request_id}",
            )
            return AssistantAccepted(request_id=request_id)

    async def wait_idle(self) -> None:
        task = self._active_task
        if task:
            await task

    async def shutdown(self) -> None:
        task = self._active_task
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _run(self, request_id: str, request: AssistantRequest) -> None:
        sequence = 0
        assistant_text = ""

        async def trace(
            stage: str,
            status: str,
            title: str,
            *,
            summary: str = "",
            data: dict[str, Any] | None = None,
            error: TraceError | None = None,
            duration_ms: int | None = None,
        ) -> None:
            nonlocal sequence
            sequence += 1
            event = AssistantTraceEvent(
                id=str(uuid4()),
                request_id=request_id,
                sequence=sequence,
                timestamp=datetime.now(BANGKOK),
                duration_ms=duration_ms,
                stage=stage,
                status=status,
                title_vi=title,
                summary_vi=summary,
                data=data or {},
                error=error,
            )
            self.storage.record_trace(event)
            await self.broker.publish("trace", event.model_dump(mode="json"))

        try:
            snapshot = await self.engine.snapshot()
            now = datetime.now(BANGKOK)
            request_context = infer_request_context(request.text, snapshot.inferred_context)
            relevant_preferences = self.storage.relevant_preferences(request_context, now)
            scene_overrides, automatic_preference_id = request_scene_overrides(
                request.text,
                snapshot,
                relevant_preferences,
            )
            force_explicit = request_requires_explicit_mode(request.text)
            await trace(
                "transcript_final",
                "completed",
                "Đã nhận yêu cầu",
                summary=request.text,
                data={"source": request.source},
            )
            await trace(
                "context_inferred",
                "completed",
                "Đã xác định ngữ cảnh yêu cầu",
                summary=(
                    f"Context {request_context}; "
                    + ("có người trong phòng" if snapshot.occupancy.room_present else "không có người trong phòng")
                ),
                data={
                    "context": request_context,
                    "occupancy": snapshot.occupancy.model_dump(mode="json"),
                },
            )
            await trace(
                "snapshot_read",
                "completed",
                "Đã đọc trạng thái phòng",
                summary=f"{snapshot.environment.temperature_c:.1f}°C, CO₂ {snapshot.environment.co2_ppm:.0f} ppm",
                data=assistant_snapshot(snapshot),
            )
            await trace(
                "preference_retrieved",
                "completed" if relevant_preferences else "skipped",
                "Đã đọc bộ nhớ sở thích" if relevant_preferences else "Không có sở thích phù hợp",
                summary=f"Context {request_context}: {len(relevant_preferences)} preference.",
                data={
                    "context": request_context,
                    "preferences": [item.model_dump(mode="json") for item in relevant_preferences],
                },
            )

            # ponytail: six completed turns bound context growth;
            # add summary compaction when sessions become long-lived.
            previous_turns = self.storage.recent_session_conversations(request.session_id, limit=6)
            input_items: list[Any] = []
            preference_payload = json.dumps(
                [item.model_dump(mode="json") for item in relevant_preferences],
                ensure_ascii=False,
            )
            for turn in previous_turns:
                input_items.extend(
                    [
                        {"role": "user", "content": turn.user_text},
                        {"role": "assistant", "content": turn.assistant_text},
                    ]
                )
            input_items.append(
                {
                    "role": "user",
                    "content": (
                        f"Yêu cầu hiện tại: {request.text}\n"
                        f"Hiện diện vật lý: {snapshot.occupancy.model_dump_json()}\n"
                        f"Thời gian mô phỏng: {snapshot.timestamp.isoformat()}\n"
                        f"Context yêu cầu: {request_context}\n"
                        f"Preference phù hợp đã truy xuất: {preference_payload}"
                    ),
                }
            )
            chat_messages = [{"role": "system", "content": INSTRUCTIONS}, *input_items]
            pending_scene: RoomSceneTargets | None = None
            applied_preference_id: str | None = None
            preference_saved = False

            for loop_index in range(5):
                started = perf_counter()
                await trace(
                    "model_requested",
                    "started",
                    "Đang hỏi mô hình",
                    data={"model": self.model, "loop": loop_index + 1},
                )
                if self.api_mode == "chat_completions":
                    response = await asyncio.wait_for(
                        self.client.chat.completions.create(
                            model=self.model,
                            messages=chat_messages,
                            tools=CHAT_TOOLS,
                            max_tokens=600,
                        ),
                        timeout=self.timeout_seconds,
                    )
                    message = response.choices[0].message
                    raw_function_calls = list(message.tool_calls or [])
                    function_calls = [
                        {
                            "name": item.function.name,
                            "arguments": item.function.arguments,
                            "call_id": item.id,
                        }
                        for item in raw_function_calls
                    ]
                    assistant_message: dict[str, Any] = {
                        "role": "assistant",
                        "content": message.content,
                    }
                    if raw_function_calls:
                        assistant_message["tool_calls"] = [
                            {
                                "id": item.id,
                                "type": "function",
                                "function": {
                                    "name": item.function.name,
                                    "arguments": item.function.arguments,
                                },
                            }
                            for item in raw_function_calls
                        ]
                    chat_messages.append(assistant_message)
                    model_text = message.content or ""
                else:
                    response = await asyncio.wait_for(
                        self.client.responses.create(
                            model=self.model,
                            instructions=INSTRUCTIONS,
                            input=input_items,
                            tools=PROVIDER_TOOLS,
                            reasoning={"effort": self.reasoning_effort},
                            text={"verbosity": "low"},
                            store=False,
                        ),
                        timeout=self.timeout_seconds,
                    )
                    output_items = list(response.output)
                    input_items.extend(output_items)
                    function_calls = [
                        {
                            "name": item.name,
                            "arguments": item.arguments,
                            "call_id": item.call_id,
                        }
                        for item in output_items
                        if item.type == "function_call"
                    ]
                    model_text = response.output_text
                duration_ms = round((perf_counter() - started) * 1_000)
                await trace(
                    "model_requested",
                    "completed",
                    "Mô hình đã phản hồi",
                    data={"tool_calls": len(function_calls)},
                    duration_ms=duration_ms,
                )

                if not function_calls:
                    assistant_text = model_text.strip()
                    if not assistant_text:
                        raise AssistantWorkflowError("Mô hình không trả về phản hồi cuối.")
                    break

                for item in function_calls:
                    arguments = json.loads(item["arguments"])
                    await trace(
                        "tool_requested",
                        "completed",
                        f"Mô hình gọi {item['name']}",
                        data={"tool": item["name"], "arguments": arguments},
                    )
                    tool_output: dict[str, Any]
                    if item["name"] == "get_room_snapshot":
                        current = await self.engine.snapshot()
                        tool_output = assistant_snapshot(current)
                    elif item["name"] == "get_recent_actions":
                        limit = max(1, min(20, int(arguments["limit"])))
                        tool_output = {"actions": self.storage.recent_actions(limit)}
                    elif item["name"] == "get_relevant_preferences":
                        relevant_preferences = self.storage.relevant_preferences(request_context, now)
                        tool_output = {
                            "preferences": [item.model_dump(mode="json") for item in relevant_preferences]
                        }
                        await trace(
                            "preference_retrieved",
                            "completed" if relevant_preferences else "skipped",
                            "Đã đọc bộ nhớ sở thích" if relevant_preferences else "Không có sở thích phù hợp",
                            summary=f"Context {request_context}: {len(relevant_preferences)} preference.",
                            data=tool_output,
                        )
                    elif item["name"] == "save_preference":
                        source = arguments["source"]
                        duration = arguments.get("duration_hours")
                        if source == "temporary" and duration is None:
                            tool_output = {"ok": False, "error": "temporary cần duration_hours"}
                        else:
                            expires_at = now + timedelta(hours=float(duration)) if source == "temporary" else None
                            preference = self.storage.create_preference(
                                PreferenceCreate(
                                    context=arguments["context"],
                                    requested_intent=arguments["requested_intent"],
                                    preferred_result=PreferenceTargets.model_validate(arguments["preferred_result"]),
                                    source=source,
                                    expires_at=expires_at,
                                ),
                                now,
                            )
                            if preference.context in {request_context, "any"}:
                                relevant_preferences = [
                                    preference,
                                    *[item for item in relevant_preferences if item.id != preference.id],
                                ]
                            preference_saved = True
                            tool_output = {"ok": True, "preference": preference.model_dump(mode="json")}
                            await trace(
                                "preference_recorded",
                                "completed",
                                "Đã lưu sở thích",
                                summary=preference.requested_intent,
                                data=tool_output,
                            )
                    elif item["name"] == "record_preference_correction":
                        preference = self.storage.record_preference_correction(
                            request_id=request_id,
                            session_id=request.session_id,
                            context=arguments["context"],
                            requested_intent=arguments["requested_intent"],
                            correction_text=request.text,
                            preferred_result=PreferenceTargets.model_validate(arguments["preferred_result"]),
                            now=now,
                        )
                        if preference.context in {request_context, "any"}:
                            relevant_preferences = [
                                preference,
                                *[item for item in relevant_preferences if item.id != preference.id],
                            ]
                        preference_saved = True
                        tool_output = {"ok": True, "preference": preference.model_dump(mode="json")}
                        await trace(
                            "preference_recorded",
                            "completed",
                            "Đã ghi nhận chỉnh sửa",
                            summary="Preference học được đã được lưu và có hiệu lực.",
                            data=tool_output,
                        )
                    elif item["name"] == "set_room_scene":
                        if pending_scene is not None:
                            tool_output = {"ok": False, "error": "Chỉ được đề xuất một scene mỗi yêu cầu."}
                        else:
                            try:
                                model_preference_id = normalize_optional_preference_id(
                                    arguments.pop("applied_preference_id", None)
                                )
                                requested_preference_id = automatic_preference_id or model_preference_id
                                valid_preference_ids = {preference.id for preference in relevant_preferences}
                                if requested_preference_id not in valid_preference_ids | {None}:
                                    raise ValueError("Preference chưa có hiệu lực, hết hạn hoặc không phù hợp context.")
                                resolved_arguments = resolve_scene_arguments(
                                    arguments,
                                    scene_overrides,
                                    force_explicit=force_explicit,
                                )
                                scene = RoomSceneTargets.model_validate(resolved_arguments)
                                preview, changes = await self.engine.preview_scene(
                                    scene,
                                    allow_large_changes=scene.change_mode == "explicit",
                                )
                                if requested_preference_id is not None:
                                    requested_preference = next(
                                        preference
                                        for preference in relevant_preferences
                                        if preference.id == requested_preference_id
                                    )
                                    if not snapshot_satisfies_preference(preview, requested_preference):
                                        requested_preference_id = None
                                pending_scene = scene
                                applied_preference_id = requested_preference_id
                                tool_output = {
                                    "ok": True,
                                    "pending": True,
                                    "changed": [change.model_dump(mode="json") for change in changes],
                                    "applied_preference_id": requested_preference_id,
                                    "resolved_targets": scene.model_dump(mode="json", exclude_none=True),
                                    "preview_snapshot_version": preview.version,
                                }
                                await trace(
                                    "validation_completed",
                                    "completed",
                                    "Giá trị thiết bị hợp lệ",
                                    summary=scene.reason,
                                    data=tool_output,
                                )
                            except (ValidationError, CommandValidationError, ValueError) as error:
                                details = getattr(error, "details", {})
                                tool_output = {"ok": False, "error": str(error), "details": details}
                                await trace(
                                    "validation_completed",
                                    "failed",
                                    "Giá trị thiết bị bị từ chối",
                                    summary=str(error),
                                    data=details,
                                )
                    else:
                        tool_output = {"ok": False, "error": f"Unknown tool: {item['name']}"}

                    output = json.dumps(tool_output, ensure_ascii=False)
                    if self.api_mode == "chat_completions":
                        chat_messages.append(
                            {"role": "tool", "tool_call_id": item["call_id"], "content": output}
                        )
                    else:
                        input_items.append(
                            {
                                "type": "function_call_output",
                                "call_id": item["call_id"],
                                "output": output,
                            }
                        )
            else:
                if not scene_overrides:
                    raise AssistantWorkflowError("Vượt quá số vòng gọi công cụ cho phép.")

            if pending_scene is None and scene_overrides:
                fallback_arguments = resolve_scene_arguments(
                    {"reason": "Thực hiện trực tiếp giá trị rõ ràng người dùng đã yêu cầu."},
                    scene_overrides,
                    force_explicit=True,
                )
                pending_scene = RoomSceneTargets.model_validate(fallback_arguments)
                preview, changes = await self.engine.preview_scene(
                    pending_scene,
                    allow_large_changes=True,
                )
                applied_preference_id = automatic_preference_id
                await trace(
                    "validation_completed",
                    "completed",
                    "Đã chuẩn hóa yêu cầu rõ ràng",
                    summary=pending_scene.reason,
                    data={
                        "changed": [change.model_dump(mode="json") for change in changes],
                        "resolved_targets": pending_scene.model_dump(mode="json", exclude_none=True),
                        "preview_snapshot_version": preview.version,
                    },
                )

            if pending_scene:
                result = await self.engine.command_scene(
                    pending_scene,
                    source="assistant",
                    allow_large_changes=pending_scene.change_mode == "explicit",
                )
                await trace(
                    "action_applied",
                    "completed",
                    "Đã áp dụng hành động mô phỏng",
                    summary=pending_scene.reason,
                    data=result.model_dump(mode="json"),
                )
                if applied_preference_id:
                    self.storage.mark_preference_used(applied_preference_id, datetime.now(BANGKOK))
                assistant_text = action_confirmation(
                    result.changed,
                    context=request_context,
                    preference_saved=preference_saved,
                    preference_used=applied_preference_id is not None,
                )
                await trace(
                    "state_updated",
                    "completed",
                    "Trạng thái căn hộ đã cập nhật",
                    data={"snapshot_version": result.snapshot_version},
                )

            await trace(
                "assistant_response",
                "completed",
                "Trợ lý đã trả lời",
                summary=assistant_text,
                data={"text": assistant_text},
            )
            self.storage.finish_conversation(
                request_id,
                status="completed",
                assistant_text=assistant_text,
                error_message="",
                completed_at=datetime.now(BANGKOK),
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await trace(
                "assistant_response",
                "failed",
                "Yêu cầu thất bại",
                summary="Căn hộ không thay đổi nếu hành động chưa được xác nhận.",
                error=TraceError(code=type(error).__name__, message=str(error)),
            )
            self.storage.finish_conversation(
                request_id,
                status="failed",
                assistant_text="",
                error_message=str(error),
                completed_at=datetime.now(BANGKOK),
            )
        finally:
            self._active_task = None
