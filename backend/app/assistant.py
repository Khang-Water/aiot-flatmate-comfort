import asyncio
import json
from contextlib import suppress
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.commands import CommandValidationError
from app.models import (
    AssistantAccepted,
    AssistantRequest,
    AssistantTraceEvent,
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
        "description": "Đề xuất một thay đổi nguyên tử cho các thiết bị mô phỏng. Giá trị null giữ nguyên thiết bị.",
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
                "applied_preference_id": {"type": ["string", "null"]},
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

INSTRUCTIONS = """
Bạn là FlatMate Comfort, trợ lý cho một căn hộ studio mô phỏng.

Mục tiêu:
- Hiểu yêu cầu tiếng Việt và chuyển thành giá trị thiết bị cụ thể.
- Luôn gọi get_room_snapshot trước khi đề xuất thay đổi.
- Chỉ một set_room_scene hợp lệ được áp dụng. Nếu validation từ chối, đọc lỗi và được thử lại một lần
  với giá trị đã sửa trong giới hạn.
- Dùng get_recent_actions khi yêu cầu nhắc đến thay đổi trước đó.
- Nếu hệ thống báo có bộ nhớ sở thích, luôn gọi get_relevant_preferences với context bạn hiểu
  từ toàn bộ câu trước khi gọi set_room_scene.
- Thứ tự ưu tiên preference: explicit, temporary, user_correction, rồi learned.
- Nếu nhiều preference cùng source và scope phù hợp, dùng bản updated_at mới nhất.
- Chỉ áp dụng preference khi requested_intent phù hợp yêu cầu hiện tại; không áp dụng chỉ vì cùng context.
- Khi dùng preference, truyền id của nó vào applied_preference_id trong set_room_scene; nếu không dùng thì null.
- Chỉ gọi save_preference khi người dùng yêu cầu ghi nhớ rõ ràng. temporary phải có duration_hours.
- Khi người dùng sửa kết quả trước đó, gọi record_preference_correction với intent chuẩn hóa ổn định và target mới.
- Khi correction thể hiện sở thích hữu ích, lưu và cho phép áp dụng ngay; không yêu cầu xác nhận riêng.
- Lịch sử hội thoại chỉ dùng để hiểu tham chiếu và ngữ cảnh hiện tại; không lặp lại lệnh cũ.
- Không thay đổi thiết bị không liên quan; dùng null cho trường giữ nguyên.
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
- Lý do trong set_room_scene phải ngắn, bằng tiếng Việt, dựa trên dữ liệu quan sát được.
- Phản hồi cuối bằng tiếng Việt, ngắn, nói rõ thay đổi đã yêu cầu hoặc khuyến nghị nếu không thể hành động.
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
        reasoning_effort: str,
        timeout_seconds: float,
        engine: SimulationEngine,
        storage: Storage,
        broker: EventBroker,
    ) -> None:
        self.client = client
        self.model = model
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
            has_active_preferences = bool(self.storage.active_preferences(now, limit=1))
            relevant_preferences: list[PreferenceRecord] = []
            preference_lookup_done = not has_active_preferences
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
                "Đã đọc hiện diện vật lý",
                summary=(
                    "Có người trong phòng"
                    if snapshot.occupancy.room_present
                    else "Không phát hiện người trong phòng"
                ),
                data=snapshot.occupancy.model_dump(mode="json"),
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
                "started" if has_active_preferences else "skipped",
                "Chờ xác định ngữ cảnh sở thích" if has_active_preferences else "Không có sở thích đang lưu",
                summary="LLM sẽ chọn context để tra bộ nhớ." if has_active_preferences else "",
                data={"available": has_active_preferences},
            )

            # ponytail: six completed turns bound context growth;
            # add summary compaction when sessions become long-lived.
            previous_turns = self.storage.recent_session_conversations(request.session_id, limit=6)
            input_items: list[Any] = []
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
                        f"Bộ nhớ sở thích khả dụng: {'có' if has_active_preferences else 'không'}"
                    ),
                }
            )
            pending_scene: RoomSceneTargets | None = None
            applied_preference_id: str | None = None

            for loop_index in range(5):
                started = perf_counter()
                await trace(
                    "model_requested",
                    "started",
                    "Đang hỏi mô hình",
                    data={"model": self.model, "loop": loop_index + 1},
                )
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
                duration_ms = round((perf_counter() - started) * 1_000)
                output_items = list(response.output)
                input_items.extend(output_items)
                function_calls = [item for item in output_items if item.type == "function_call"]
                await trace(
                    "model_requested",
                    "completed",
                    "Mô hình đã phản hồi",
                    data={"tool_calls": len(function_calls)},
                    duration_ms=duration_ms,
                )

                if not function_calls:
                    assistant_text = response.output_text.strip()
                    if not assistant_text:
                        raise AssistantWorkflowError("Mô hình không trả về phản hồi cuối.")
                    break

                for item in function_calls:
                    arguments = json.loads(item.arguments)
                    await trace(
                        "tool_requested",
                        "completed",
                        f"Mô hình gọi {item.name}",
                        data={"tool": item.name, "arguments": arguments},
                    )
                    tool_output: dict[str, Any]
                    if item.name == "get_room_snapshot":
                        current = await self.engine.snapshot()
                        tool_output = assistant_snapshot(current)
                    elif item.name == "get_recent_actions":
                        limit = max(1, min(20, int(arguments["limit"])))
                        tool_output = {"actions": self.storage.recent_actions(limit)}
                    elif item.name == "get_relevant_preferences":
                        relevant_preferences = self.storage.relevant_preferences(arguments["context"], now)
                        preference_lookup_done = True
                        tool_output = {
                            "preferences": [item.model_dump(mode="json") for item in relevant_preferences]
                        }
                        await trace(
                            "preference_retrieved",
                            "completed" if relevant_preferences else "skipped",
                            "Đã đọc bộ nhớ sở thích" if relevant_preferences else "Không có sở thích phù hợp",
                            summary=f"Context {arguments['context']}: {len(relevant_preferences)} preference.",
                            data=tool_output,
                        )
                    elif item.name == "save_preference":
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
                            tool_output = {"ok": True, "preference": preference.model_dump(mode="json")}
                            await trace(
                                "preference_recorded",
                                "completed",
                                "Đã lưu sở thích",
                                summary=preference.requested_intent,
                                data=tool_output,
                            )
                    elif item.name == "record_preference_correction":
                        preference = self.storage.record_preference_correction(
                            request_id=request_id,
                            session_id=request.session_id,
                            context=arguments["context"],
                            requested_intent=arguments["requested_intent"],
                            correction_text=request.text,
                            preferred_result=PreferenceTargets.model_validate(arguments["preferred_result"]),
                            now=now,
                        )
                        tool_output = {"ok": True, "preference": preference.model_dump(mode="json")}
                        await trace(
                            "preference_recorded",
                            "completed",
                            "Đã ghi nhận chỉnh sửa",
                            summary="Preference học được đã được lưu và có hiệu lực.",
                            data=tool_output,
                        )
                    elif item.name == "set_room_scene":
                        if pending_scene is not None:
                            tool_output = {"ok": False, "error": "Chỉ được đề xuất một scene mỗi yêu cầu."}
                        elif not preference_lookup_done:
                            tool_output = {
                                "ok": False,
                                "error": "Phải gọi get_relevant_preferences với context đã hiểu trước khi đổi scene.",
                            }
                        else:
                            try:
                                requested_preference_id = arguments.pop("applied_preference_id", None)
                                valid_preference_ids = {preference.id for preference in relevant_preferences}
                                if requested_preference_id not in valid_preference_ids | {None}:
                                    raise ValueError("Preference chưa có hiệu lực, hết hạn hoặc không phù hợp context.")
                                scene = RoomSceneTargets.model_validate(arguments)
                                preview, changes = await self.engine.preview_scene(
                                    scene,
                                    allow_large_changes=scene.change_mode == "explicit",
                                )
                                pending_scene = scene
                                applied_preference_id = requested_preference_id
                                tool_output = {
                                    "ok": True,
                                    "pending": True,
                                    "changed": [change.model_dump(mode="json") for change in changes],
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
                        tool_output = {"ok": False, "error": f"Unknown tool: {item.name}"}

                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": item.call_id,
                            "output": json.dumps(tool_output, ensure_ascii=False),
                        }
                    )
            else:
                raise AssistantWorkflowError("Vượt quá số vòng gọi công cụ cho phép.")

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
