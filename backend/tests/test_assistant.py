import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator

from app.assistant import (
    PROVIDER_TOOLS,
    TOOLS,
    AssistantOrchestrator,
    action_confirmation,
    explicit_light_scene_targets,
    infer_request_context,
    request_requires_explicit_mode,
)
from app.models import AssistantRequest, ChangedValue, DeviceCommand, PreferenceCreate, PreferenceTargets
from app.scenarios import ScenarioRepository
from app.simulation import SimulationEngine, initial_snapshot
from app.state import EventBroker
from app.storage import Storage


class FakeResponses:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = FakeResponses(responses)


class FakeChatCompletions:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeChatClient:
    def __init__(self, responses: list[Any]) -> None:
        self.chat = SimpleNamespace(completions=FakeChatCompletions(responses))


def tool_call(name: str, arguments: dict[str, Any], call_id: str) -> Any:
    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=json.dumps(arguments),
        call_id=call_id,
    )


def response(*items: Any, text: str = "") -> Any:
    return SimpleNamespace(output=list(items), output_text=text)


def chat_tool_call(name: str, arguments: dict[str, Any], call_id: str) -> Any:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def chat_response(*calls: Any, text: str | None = None) -> Any:
    message = SimpleNamespace(content=text, tool_calls=list(calls))
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def scene_arguments(ac_temperature_c: float = 25, change_mode: str = "explicit") -> dict[str, Any]:
    return {
        "change_mode": change_mode,
        "ac_temperature_c": ac_temperature_c,
        "fan_speed": 1,
        "main_light_brightness_percent": None,
        "main_light_color_temperature_kelvin": None,
        "bedside_light_brightness_percent": None,
        "bedside_light_color_temperature_kelvin": None,
        "air_purifier_speed": None,
        "curtain_position_percent": None,
        "target_humidity_percent": None,
        "reason": "Phòng đang nóng và người dùng muốn mát hơn.",
    }


def preference_targets(**values: Any) -> dict[str, Any]:
    targets = {name: None for name in (
        "ac_power", "ac_temperature_c", "fan_power", "fan_speed", "main_light_power",
        "main_light_brightness_percent", "main_light_color_temperature_kelvin",
        "bedside_light_power", "bedside_light_brightness_percent",
        "bedside_light_color_temperature_kelvin", "air_purifier_power", "air_purifier_speed",
        "curtain_position_percent", "window_state", "humidity_device_power",
        "target_humidity_percent", "desk_computer_power", "monitor_power",
    )}
    targets.update(values)
    return targets


def build_orchestrator(
    tmp_path: Path,
    fake_client: Any,
    api_mode: str = "responses",
) -> tuple[AssistantOrchestrator, SimulationEngine, Storage]:
    storage = Storage(tmp_path / "assistant.db")
    storage.initialize()
    broker = EventBroker()
    scenarios = ScenarioRepository(tmp_path / "scenarios")
    engine = SimulationEngine(
        seed=42,
        tick_seconds=60,
        minutes_per_tick=1,
        storage=storage,
        scenarios=scenarios,
        broker=broker,
    )
    orchestrator = AssistantOrchestrator(
        client=fake_client,
        model="test-model",
        api_mode=api_mode,
        reasoning_effort="low",
        timeout_seconds=2,
        engine=engine,
        storage=storage,
        broker=broker,
    )
    return orchestrator, engine, storage


def test_chat_completions_tool_loop_returns_final_response(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeChatClient([
            chat_response(chat_tool_call("get_room_snapshot", {}, "call-1")),
            chat_response(text="Nhiệt độ phòng hiện tại là 26.5°C."),
        ])
        orchestrator, _, storage = build_orchestrator(tmp_path, client, "chat_completions")

        await orchestrator.submit(
            AssistantRequest(text="Nhiệt độ phòng hiện tại là bao nhiêu?", session_id="test")
        )
        await orchestrator.wait_idle()

        conversation = storage.conversations(1)[0]
        assert conversation.status == "completed"
        assert conversation.assistant_text == "Nhiệt độ phòng hiện tại là 26.5°C."
        first_call = client.chat.completions.calls[0]
        second_call = client.chat.completions.calls[1]
        assert first_call["messages"][0]["role"] == "system"
        assert first_call["tools"][0]["function"]["name"] == "get_relevant_preferences"
        assert any(item["role"] == "tool" for item in second_call["messages"])

    asyncio.run(run())


def test_chat_completions_accepts_null_string_preference_sentinel(tmp_path: Path) -> None:
    async def run() -> None:
        arguments = scene_arguments()
        arguments["applied_preference_id"] = "null"
        client = FakeChatClient([
            chat_response(chat_tool_call("set_room_scene", arguments, "call-1")),
            chat_response(text="Đã đặt điều hòa 25 độ."),
        ])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client, "chat_completions")

        await orchestrator.submit(
            AssistantRequest(text="Đặt điều hòa 25 độ.", session_id="test")
        )
        await orchestrator.wait_idle()

        assert (await engine.snapshot()).devices.ac.temperature_c == 25
        assert storage.conversations(1)[0].assistant_text == "Đã đặt điều hòa 25 độ."
        assert "tools" not in client.chat.completions.calls[1]

    asyncio.run(run())


def test_shutdown_confirmation_does_not_claim_work_scene_is_ready() -> None:
    reply = action_confirmation(
        [
            ChangedValue(path="devices.main_light.power", before=True, after=False),
            ChangedValue(path="devices.main_light.brightness_percent", before=65, after=0),
        ],
        snapshot=initial_snapshot(),
        preparation_context=None,
        preference_saved=False,
        preference_used=False,
    )

    assert "Không gian làm việc đã sẵn sàng" not in reply


def test_work_ventilation_confirmation_does_not_mention_visual_preference() -> None:
    snapshot = initial_snapshot()
    snapshot = snapshot.model_copy(
        update={"openings": snapshot.openings.model_copy(update={"window_state": "open"})}
    )
    reply = action_confirmation(
        [
            ChangedValue(path="devices.ac.power", before=True, after=False),
            ChangedValue(path="openings.window_state", before="closed", after="open"),
        ],
        snapshot=snapshot,
        preparation_context="working",
        preference_saved=False,
        preference_used=False,
    )

    assert "Không gian làm việc đã sẵn sàng" in reply
    assert "vừa mắt" not in reply


def test_sleep_scene_normalizes_dependencies_and_confirms_ready(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([
            response(
                tool_call(
                    "set_room_scene",
                    {
                        "change_mode": "explicit",
                        "ac_power": True,
                        "main_light_power": False,
                        "main_light_brightness_percent": 65,
                        "bedside_light_power": True,
                        "bedside_light_brightness_percent": 15,
                        "bedside_light_color_temperature_kelvin": 2700,
                        "curtain_position_percent": 0,
                        "window_state": "open",
                        "desk_computer_power": False,
                        "monitor_power": False,
                        "reason": "Chuẩn bị phòng ngủ và thông gió.",
                    },
                    "call-1",
                )
            ),
            response(
                text=(
                    "Tôi đã tắt điều hòa, để rèm đóng, tắt đèn chính, bật đèn đầu giường "
                    "15% ở 2700K, mở cửa sổ và tắt máy tính, màn hình. "
                    "Không gian ngủ đã sẵn sàng."
                )
            ),
        ])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(AssistantRequest(text="Tôi chuẩn bị ngủ.", session_id="test"))
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        conversation = storage.conversations(1)[0]
        with storage.connect() as connection:
            validation_statuses = [
                row[0]
                for row in connection.execute(
                    "SELECT status FROM assistant_trace_events "
                    "WHERE stage = 'validation_completed' ORDER BY sequence"
                )
            ]
        assert snapshot.devices.ac.power is False
        assert snapshot.openings.window_state == "open"
        assert snapshot.devices.main_light.power is False
        assert snapshot.devices.main_light.brightness_percent == 0
        assert snapshot.devices.bedside_light.power is True
        assert snapshot.devices.bedside_light.brightness_percent == 15
        assert validation_statuses == ["completed"]
        assert "rèm đóng" in conversation.assistant_text
        assert "đèn chính 0%" not in conversation.assistant_text
        assert "Không gian ngủ đã sẵn sàng" in conversation.assistant_text

    asyncio.run(run())


def test_work_preparation_noop_returns_contextual_confirmation(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([response(text="Mọi thứ đã sẵn sàng.")])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)
        snapshot = await engine.snapshot()
        engine._snapshot = snapshot.model_copy(
            update={
                "environment": snapshot.environment.model_copy(
                    update={"ambient_light_lux": 500, "co2_ppm": 800}
                )
            }
        )

        await orchestrator.submit(
            AssistantRequest(text="Tôi chuẩn bị làm việc.", session_id="test")
        )
        await orchestrator.wait_idle()

        conversation = storage.conversations(1)[0]
        assert conversation.status == "completed"
        assert "máy tính và màn hình đang bật" in conversation.assistant_text
        assert "không cần thay đổi thêm" in conversation.assistant_text

    asyncio.run(run())


def test_abandoned_invalid_scene_is_failed_not_completed(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([
            response(
                tool_call(
                    "set_room_scene",
                    {
                        "change_mode": "explicit",
                        "ac_temperature_c": 17,
                        "reason": "Làm lạnh phòng.",
                    },
                    "call-1",
                )
            ),
            response(text="Xin lỗi, tôi không áp dụng được."),
        ])
        orchestrator, _, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(AssistantRequest(text="Làm mát phòng.", session_id="test"))
        await orchestrator.wait_idle()

        conversation = storage.conversations(1)[0]
        assert conversation.status == "failed"
        assert "không sửa được scene" in conversation.error_message

    asyncio.run(run())


def test_openai_function_tool_schemas_are_valid_json_schema() -> None:
    for tool in TOOLS:
        Draft202012Validator.check_schema(tool["parameters"])
        assert tool["strict"] is True


def test_provider_tool_schemas_use_gemini_compatible_subset() -> None:
    def check(schema: dict[str, Any]) -> None:
        assert schema.get("additionalProperties") is None
        assert not isinstance(schema.get("type"), list)
        assert None not in schema.get("enum", [])
        for value in schema.values():
            if isinstance(value, dict):
                check(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        check(item)

    for tool in PROVIDER_TOOLS:
        assert "strict" not in tool
        Draft202012Validator.check_schema(tool["parameters"])
        check(tool["parameters"])

    scene = next(tool for tool in PROVIDER_TOOLS if tool["name"] == "set_room_scene")
    assert scene["parameters"]["required"] == ["change_mode", "reason"]


def test_request_context_is_deterministic_for_supported_scenes() -> None:
    cases = {
        "Tôi chuẩn bị làm việc.": "working",
        "Cho tôi thư giãn một chút.": "relaxing",
        "Tôi đi ngủ đây.": "sleeping",
        "Tôi muốn đọc sách trên giường.": "reading_in_bed",
        "Tôi chuẩn bị ra ngoài.": "away",
        "Tôi ngừng làm việc rồi đi ngủ.": "sleeping",
        "Ngủ dậy tôi bắt đầu làm việc.": "working",
        "Giữ nguyên như hiện tại.": "working",
    }

    for text, expected in cases.items():
        assert infer_request_context(text, "working") == expected


def test_explicit_light_targets_cover_color_device_and_non_commands() -> None:
    assert explicit_light_scene_targets("Chỉnh đèn vàng ở mức 50%.") == {
        "main_light_power": True,
        "main_light_brightness_percent": 50,
        "main_light_color_temperature_kelvin": 2700,
    }
    assert explicit_light_scene_targets("Đặt đèn đầu giường trắng lạnh 30 phần trăm.") == {
        "bedside_light_power": True,
        "bedside_light_brightness_percent": 30,
        "bedside_light_color_temperature_kelvin": 6500,
    }
    assert explicit_light_scene_targets("Đèn chính hiện tại bao nhiêu phần trăm?") == {}
    assert explicit_light_scene_targets("Tôi muốn biết đèn vàng 50% có phù hợp không.") == {}
    assert explicit_light_scene_targets("Hãy nhớ đèn vàng 50% khi làm việc.") == {}
    assert explicit_light_scene_targets("Từ giờ khi làm việc luôn để đèn vàng 50%.") == {}
    assert explicit_light_scene_targets("Đèn vàng trong lúc làm việc không thực thi được.") == {}
    assert explicit_light_scene_targets("Không bật đèn.") == {}
    assert request_requires_explicit_mode("Đặt điều hòa 20 độ.") is True
    assert request_requires_explicit_mode("Đặt quạt mức 2.") is True
    assert request_requires_explicit_mode("Tôi muốn biết 20 độ có phù hợp không.") is False
    assert request_requires_explicit_mode("Làm phòng lạnh hơn một chút.") is False


def test_explicit_light_request_executes_when_model_skips_tool(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([
            response(text="Tôi chưa thực hiện thay đổi."),
            response(text="Tôi đã chỉnh đèn chính lên 50% với ánh sáng vàng 2700K."),
        ])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(
            AssistantRequest(text="Chỉnh đèn vàng ở mức 50%.", session_id="test")
        )
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        conversation = storage.conversations(1)[0]
        assert snapshot.devices.main_light.power is True
        assert snapshot.devices.main_light.brightness_percent == 50
        assert snapshot.devices.main_light.color_temperature_kelvin == 2700
        assert conversation.assistant_text == (
            "Tôi đã chỉnh đèn chính lên 50% với ánh sáng vàng 2700K."
        )

    asyncio.run(run())


def test_sleep_ventilation_respects_explicit_closed_window_request(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([
            response(
                tool_call(
                    "set_room_scene",
                    {
                        "change_mode": "explicit",
                        "ac_power": False,
                        "main_light_power": False,
                        "main_light_brightness_percent": 0,
                        "window_state": "open",
                        "reason": "Chuẩn bị ngủ nhưng giữ cửa sổ đóng theo yêu cầu.",
                    },
                    "call-1",
                )
            ),
            response(
                text=(
                    "Tôi đã giữ cửa sổ đóng theo yêu cầu. CO₂ vẫn cao khoảng 1.550 ppm; "
                    "bạn nên mở cửa sổ khi có thể."
                )
            ),
        ])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(
            AssistantRequest(
                text="Tôi chuẩn bị ngủ nhưng đừng mở cửa sổ.",
                session_id="test",
            )
        )
        await orchestrator.wait_idle()

        assert (await engine.snapshot()).openings.window_state == "closed"
        conversation = storage.conversations(1)[0]
        assert conversation.status == "completed"
        assert "CO₂ vẫn cao" in conversation.assistant_text
        assert "Không gian ngủ đã sẵn sàng" not in conversation.assistant_text

    asyncio.run(run())


def test_preparation_question_does_not_trigger_deterministic_scene(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([
            response(text="CO₂ đang cao, bạn nên thông gió trước khi ngủ."),
        ])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)
        before = await engine.snapshot()

        await orchestrator.submit(
            AssistantRequest(
                text="Nếu tôi đi ngủ bây giờ thì phòng có ổn không?",
                session_id="test",
            )
        )
        await orchestrator.wait_idle()

        assert await engine.snapshot() == before
        assert storage.conversations(1)[0].status == "completed"

    asyncio.run(run())


def test_work_preparation_respects_explicit_no_light_request(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([
            response(
                tool_call(
                    "set_room_scene",
                    {
                        "change_mode": "explicit",
                        "main_light_power": True,
                        "main_light_brightness_percent": 70,
                        "desk_computer_power": True,
                        "monitor_power": True,
                        "reason": "Chuẩn bị bàn làm việc.",
                    },
                    "call-1",
                )
            ),
            response(text="Đã chuẩn bị bàn làm việc."),
        ])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)
        storage.create_preference(
            PreferenceCreate(
                context="working",
                requested_intent="ánh sáng khi làm việc",
                preferred_result=PreferenceTargets(
                    main_light_power=True,
                    main_light_brightness_percent=70,
                    main_light_color_temperature_kelvin=4000,
                ),
            ),
            datetime.now(UTC),
        )
        await engine.command_device(
            "main_light",
            DeviceCommand(values={"power": False}, source="manual"),
        )

        await orchestrator.submit(
            AssistantRequest(
                text="Tôi chuẩn bị làm việc nhưng không bật đèn.",
                session_id="test",
            )
        )
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        assert snapshot.devices.main_light.power is False
        assert snapshot.devices.main_light.brightness_percent == 0
        assert storage.conversations(1)[0].status == "completed"

    asyncio.run(run())


def test_explicit_light_request_survives_model_tool_loop_limit(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient(
            [response(tool_call("get_room_snapshot", {}, f"call-{index}")) for index in range(5)]
        )
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(
            AssistantRequest(text="Chỉnh đèn vàng ở mức 50%.", session_id="test")
        )
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        assert snapshot.devices.main_light.brightness_percent == 50
        assert snapshot.devices.main_light.color_temperature_kelvin == 2700
        assert storage.conversations(1)[0].status == "completed"

    asyncio.run(run())


def test_explicit_light_request_corrects_wrong_bounded_tool_call(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient(
            [
                response(
                    tool_call(
                        "set_room_scene",
                        {
                            "change_mode": "bounded",
                            "main_light_power": True,
                            "main_light_brightness_percent": 20,
                            "reason": "Bật đèn nhẹ.",
                        },
                        "call-1",
                    )
                ),
                response(text="Tôi đã chỉnh đèn chính lên 50% với ánh sáng vàng 2700K."),
            ]
        )
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        accepted = await orchestrator.submit(
            AssistantRequest(text="Chỉnh đèn vàng ở mức 50%.", session_id="test")
        )
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        conversation = storage.conversations(1)[0]
        with storage.connect() as connection:
            trace_data = connection.execute(
                "SELECT data_json FROM assistant_trace_events "
                "WHERE request_id = ? AND stage = 'validation_completed'",
                (accepted.request_id,),
            ).fetchone()[0]
        resolved = json.loads(trace_data)["resolved_targets"]
        assert resolved["change_mode"] == "explicit"
        assert resolved["main_light_brightness_percent"] == 50
        assert resolved["main_light_color_temperature_kelvin"] == 2700
        assert snapshot.devices.main_light.brightness_percent == 50
        assert snapshot.devices.main_light.color_temperature_kelvin == 2700
        assert "20%" not in conversation.assistant_text

    asyncio.run(run())


def test_explicit_numeric_request_cannot_be_limited_as_bounded(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient(
            [
                response(
                    tool_call(
                        "set_room_scene",
                        {
                            "change_mode": "bounded",
                            "ac_temperature_c": 20,
                            "reason": "Làm lạnh phòng.",
                        },
                        "call-1",
                    )
                ),
                response(text="Đã đặt điều hòa 20°C."),
            ]
        )
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(AssistantRequest(text="Đặt điều hòa 20 độ.", session_id="test"))
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        assert snapshot.devices.ac.temperature_c == 20
        assert "20°C" in storage.conversations(1)[0].assistant_text

    asyncio.run(run())


def test_current_explicit_value_overrides_conflicting_stored_preference(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)
        preference = storage.create_preference(
            PreferenceCreate(
                context="working",
                requested_intent="ánh sáng khi làm việc",
                preferred_result=PreferenceTargets(
                    main_light_power=True,
                    main_light_brightness_percent=70,
                    main_light_color_temperature_kelvin=4000,
                ),
            ),
            datetime.now(UTC),
        )
        client.responses.responses.extend(
            [
                response(
                    tool_call(
                        "set_room_scene",
                        {
                            "change_mode": "explicit",
                            "main_light_power": True,
                            "main_light_brightness_percent": 70,
                            "main_light_color_temperature_kelvin": 4000,
                            "applied_preference_id": preference.id,
                            "reason": "Áp dụng sở thích cũ.",
                        },
                        "call-1",
                    )
                ),
                response(text="Tôi đã chỉnh đèn chính lên 50% với ánh sáng vàng 2700K."),
            ]
        )

        await orchestrator.submit(
            AssistantRequest(text="Chỉnh đèn vàng ở mức 50%.", session_id="test")
        )
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        assert snapshot.devices.main_light.brightness_percent == 50
        assert snapshot.devices.main_light.color_temperature_kelvin == 2700
        assert storage.get_preference(preference.id).last_used_at is None
        assert "áp dụng sở thích" not in storage.conversations(1)[0].assistant_text.casefold()

    asyncio.run(run())


def test_work_preparation_builds_complete_low_light_scene(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([response(text="Đã bật máy tính.")])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)
        await engine.command_device(
            "desk_computer",
            DeviceCommand(values={"state": "off"}, source="manual"),
        )
        await engine.command_device(
            "monitor",
            DeviceCommand(values={"state": "off"}, source="manual"),
        )
        await engine.command_device(
            "main_light",
            DeviceCommand(values={"brightness_percent": 0}, source="manual"),
        )

        await orchestrator.submit(AssistantRequest(text="Tôi chuẩn bị làm việc.", session_id="test"))
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        conversation = storage.conversations(1)[0]
        assert snapshot.power.smart_plugs["desk_computer"].state == "on"
        assert snapshot.power.smart_plugs["monitor"].state == "on"
        assert snapshot.devices.main_light.power is True
        assert snapshot.devices.main_light.brightness_percent == 70
        assert snapshot.devices.main_light.color_temperature_kelvin == 4000
        assert "Không gian làm việc đã sẵn sàng" in conversation.assistant_text

    asyncio.run(run())


def test_work_preparation_applies_context_preference_and_marks_used(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([response(text="Đã chuẩn bị làm việc.")])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)
        preference = storage.create_preference(
            PreferenceCreate(
                context="working",
                requested_intent="ánh sáng khi làm việc",
                preferred_result=PreferenceTargets(
                    main_light_power=True,
                    main_light_brightness_percent=50,
                    main_light_color_temperature_kelvin=2700,
                ),
            ),
            datetime.now(UTC),
        )

        await orchestrator.submit(AssistantRequest(text="Tôi chuẩn bị làm việc.", session_id="test"))
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        conversation = storage.conversations(1)[0]
        assert snapshot.devices.main_light.brightness_percent == 50
        assert snapshot.devices.main_light.color_temperature_kelvin == 2700
        assert storage.get_preference(preference.id).last_used_at is not None
        assert "áp dụng sở thích" in conversation.assistant_text

    asyncio.run(run())


def test_working_preference_is_not_injected_into_relaxing_context(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([response(text="Bạn có thể thư giãn với trạng thái hiện tại.")])
        orchestrator, _, storage = build_orchestrator(tmp_path, client)
        preference = storage.create_preference(
            PreferenceCreate(
                context="working",
                requested_intent="ánh sáng khi làm việc",
                preferred_result=PreferenceTargets(main_light_brightness_percent=50),
            ),
            datetime.now(UTC),
        )

        await orchestrator.submit(AssistantRequest(text="Tôi muốn thư giãn.", session_id="test"))
        await orchestrator.wait_idle()

        prompt = client.responses.calls[0]["input"][-1]["content"]
        assert "Context yêu cầu: relaxing" in prompt
        assert preference.id not in prompt

    asyncio.run(run())


def test_tool_loop_uses_llm_response_generated_from_committed_state(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient(
            [
                response(tool_call("get_room_snapshot", {}, "call-1")),
                response(tool_call("set_room_scene", scene_arguments(), "call-2")),
                response(text="Tôi đã đặt AC 25 độ và bật quạt mức 1."),
            ]
        )
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        accepted = await orchestrator.submit(
            AssistantRequest(text="Đặt AC 25 độ và quạt mức 1.", source="text", session_id="test")
        )
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        conversation = storage.conversations(1)[0]
        with storage.connect() as connection:
            stages = [
                row[0]
                for row in connection.execute(
                    "SELECT stage FROM assistant_trace_events WHERE request_id = ? ORDER BY sequence",
                    (accepted.request_id,),
                )
            ]
            snapshot_data = connection.execute(
                "SELECT data_json FROM assistant_trace_events WHERE request_id = ? AND stage = 'snapshot_read'",
                (accepted.request_id,),
            ).fetchone()[0]
        assert snapshot.devices.ac.temperature_c == 25
        assert snapshot.devices.fan.speed == 1
        assert conversation.request_id == accepted.request_id
        assert conversation.status == "completed"
        assert conversation.assistant_text == "Tôi đã đặt AC 25 độ và bật quạt mức 1."
        assert client.responses.calls[1]["input"][-1]["type"] == "function_call_output"
        final_call = client.responses.calls[2]
        final_payload = json.loads(final_call["input"][0]["content"])
        assert "tools" not in final_call
        assert final_payload["user_request"] == "Đặt AC 25 độ và quạt mức 1."
        assert final_payload["committed_snapshot"]["devices"]["ac"]["temperature_c"] == 25
        assert {
            item["path"]: item["after"] for item in final_payload["committed_changes"]
        }["devices.ac.temperature_c"] == 25
        assert "validation_completed" in stages
        assert "action_applied" in stages
        assert stages[-1] == "assistant_response"
        assert "inferred_context" not in snapshot_data

    asyncio.run(run())


def test_failed_or_empty_final_response_uses_fallback_after_commit(tmp_path: Path) -> None:
    async def run() -> None:
        for case, final_response in (
            ("error", RuntimeError("simulated OpenAI outage")),
            ("empty", response(text="")),
        ):
            client = FakeClient(
                [
                    response(tool_call("get_room_snapshot", {}, "call-1")),
                    response(tool_call("set_room_scene", scene_arguments(), "call-2")),
                    final_response,
                ]
            )
            orchestrator, engine, storage = build_orchestrator(tmp_path / case, client)
            await orchestrator.submit(
                AssistantRequest(
                    text="Đặt AC 25 độ và quạt mức 1.",
                    source="text",
                    session_id="test",
                )
            )
            await orchestrator.wait_idle()

            after = await engine.snapshot()
            conversation = storage.conversations(1)[0]
            assert after.devices.ac.temperature_c == 25
            assert after.devices.fan.speed == 1
            assert conversation.status == "completed"
            assert conversation.error_message == ""
            assert "điều hòa 25°C" in conversation.assistant_text
            with storage.connect() as connection:
                failed_final_call = connection.execute(
                    "SELECT status FROM assistant_trace_events "
                    "WHERE stage = 'model_requested' AND status = 'failed'"
                ).fetchone()
            assert failed_final_call is not None

    asyncio.run(run())


def test_vague_request_retries_with_safe_temperature_after_rejection(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient(
            [
                response(tool_call("get_room_snapshot", {}, "call-1")),
                response(tool_call("set_room_scene", scene_arguments(22, "bounded"), "call-2")),
                response(tool_call("set_room_scene", scene_arguments(24, "bounded"), "call-3")),
                response(text="Đã giảm AC xuống 24 độ và bật quạt mức 1."),
            ]
        )
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(
            AssistantRequest(text="Làm phòng lạnh hơn.", source="text", session_id="test")
        )
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        assert snapshot.devices.ac.temperature_c == 24
        assert snapshot.devices.fan.speed == 1
        assert storage.conversations(1)[0].status == "completed"
        with storage.connect() as connection:
            validation_statuses = [
                row[0]
                for row in connection.execute(
                    "SELECT status FROM assistant_trace_events "
                    "WHERE stage = 'validation_completed' ORDER BY sequence"
                )
            ]
        assert validation_statuses == ["failed", "completed"]

    asyncio.run(run())


def test_active_preference_is_exposed_and_marked_used(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)
        preference = storage.create_preference(
            PreferenceCreate(
                context="working",
                requested_intent="nhiệt độ khi làm việc",
                preferred_result=PreferenceTargets(ac_power=True, ac_temperature_c=25),
            ),
            datetime.now(UTC),
        )
        arguments = scene_arguments()
        arguments["applied_preference_id"] = preference.id
        client.responses.responses.extend([
            response(tool_call("get_relevant_preferences", {"context": "working"}, "call-1")),
            response(tool_call("set_room_scene", arguments, "call-2")),
            response(text="Đã dùng nhiệt độ làm việc bạn đã lưu."),
        ])

        await orchestrator.submit(AssistantRequest(text="Làm phòng dễ chịu khi làm việc.", session_id="test"))
        await orchestrator.wait_idle()

        assert (await engine.snapshot()).devices.ac.temperature_c == 25
        assert storage.get_preference(preference.id).last_used_at is not None
        outputs = [
            item["output"] for item in client.responses.calls[1]["input"]
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        ]
        assert any(preference.id in output for output in outputs)

    asyncio.run(run())


def test_llm_correction_is_saved_and_available_on_next_request(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([
            response(tool_call("record_preference_correction", {
                "context": "working",
                "requested_intent": "ánh sáng khi làm việc",
                "preferred_result": preference_targets(
                    main_light_power=True,
                    main_light_brightness_percent=70,
                    main_light_color_temperature_kelvin=2700,
                ),
            }, "call-1")),
            response(text="Đã ghi nhớ đèn vàng 70 phần trăm khi làm việc."),
        ])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(
            AssistantRequest(
                text="Không, khi làm việc tôi muốn đèn vàng 70 phần trăm.",
                session_id="test",
            )
        )
        await orchestrator.wait_idle()

        learned = storage.preferences()[0]
        assert learned.source == "user_correction"
        assert learned.confirmed is True
        immediate = await engine.snapshot()
        assert immediate.devices.main_light.brightness_percent == 70
        assert immediate.devices.main_light.color_temperature_kelvin == 2700
        assert "ghi nhớ chỉnh sửa" in storage.conversations(1)[0].assistant_text

        arguments = scene_arguments()
        arguments.update({
            "ac_temperature_c": None,
            "fan_speed": None,
            "main_light_power": True,
            "main_light_brightness_percent": 70,
            "main_light_color_temperature_kelvin": 2700,
            "applied_preference_id": learned.id,
            "reason": "Áp dụng ánh sáng làm việc đã học.",
        })
        client.responses.responses.extend([
            response(tool_call("get_relevant_preferences", {"context": "working"}, "call-2")),
            response(tool_call("set_room_scene", arguments, "call-3")),
            response(text="Đã bật đèn 70 phần trăm theo sở thích của bạn."),
        ])

        await orchestrator.submit(
            AssistantRequest(text="Thiết lập ánh sáng khi làm việc.", session_id="test")
        )
        await orchestrator.wait_idle()

        snapshot = await engine.snapshot()
        assert snapshot.devices.main_light.power is True
        assert snapshot.devices.main_light.brightness_percent == 70
        assert snapshot.devices.main_light.color_temperature_kelvin == 2700
        assert storage.get_preference(learned.id).last_used_at is not None
        outputs = [
            item["output"] for item in client.responses.calls[3]["input"]
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        ]
        assert any(learned.id in output for output in outputs)

    asyncio.run(run())


def test_session_history_is_passed_to_model_without_cross_session_leak(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([response(text="Đã hiểu yêu cầu nối tiếp.")])
        orchestrator, _, storage = build_orchestrator(tmp_path, client)
        now = datetime.now(UTC)
        storage.start_conversation("prior", "same-session", "text", "Bật đèn bàn.", now)
        storage.finish_conversation(
            "prior",
            status="completed",
            assistant_text="Đã bật đèn bàn.",
            error_message="",
            completed_at=now,
        )
        storage.start_conversation("private", "other-session", "text", "Mã riêng 123.", now)
        storage.finish_conversation(
            "private",
            status="completed",
            assistant_text="Đã lưu mã riêng 123.",
            error_message="",
            completed_at=now,
        )

        await orchestrator.submit(
            AssistantRequest(text="Giảm nó xuống 50 phần trăm.", session_id="same-session")
        )
        await orchestrator.wait_idle()

        input_items = client.responses.calls[0]["input"]
        assert input_items[0] == {"role": "user", "content": "Bật đèn bàn."}
        assert input_items[1] == {"role": "assistant", "content": "Đã bật đèn bàn."}
        assert "Yêu cầu hiện tại: Giảm nó xuống 50 phần trăm." in input_items[2]["content"]
        assert "Mã riêng 123" not in json.dumps(input_items, ensure_ascii=False)

    asyncio.run(run())


def test_assistant_can_save_explicit_preference(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient([
            response(tool_call("save_preference", {
                "context": "working",
                "requested_intent": "độ sáng khi làm việc",
                "source": "explicit",
                "preferred_result": preference_targets(
                    main_light_power=True,
                    main_light_brightness_percent=70,
                    main_light_color_temperature_kelvin=2700,
                ),
            }, "call-1")),
            response(text="Đã nhớ độ sáng khi làm việc."),
        ])
        orchestrator, _, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(
            AssistantRequest(text="Hãy nhớ khi làm việc tôi thích đèn 70 phần trăm.", session_id="test")
        )
        await orchestrator.wait_idle()

        saved = storage.preferences()
        assert len(saved) == 1
        assert saved[0].source == "explicit"
        assert saved[0].preferred_result.main_light_brightness_percent == 70
        assert saved[0].preferred_result.main_light_color_temperature_kelvin == 2700

    asyncio.run(run())
