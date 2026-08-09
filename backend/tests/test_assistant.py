import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator

from app.assistant import PROVIDER_TOOLS, TOOLS, AssistantOrchestrator
from app.models import AssistantRequest, PreferenceCreate, PreferenceTargets
from app.scenarios import ScenarioRepository
from app.simulation import SimulationEngine
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


def test_tool_loop_commits_scene_after_final_response(tmp_path: Path) -> None:
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
        assert conversation.assistant_text.startswith("Tôi đã")
        assert client.responses.calls[1]["input"][-1]["type"] == "function_call_output"
        assert "validation_completed" in stages
        assert "action_applied" in stages
        assert stages[-1] == "assistant_response"
        assert "inferred_context" not in snapshot_data

    asyncio.run(run())


def test_openai_failure_after_preview_leaves_room_unchanged(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeClient(
            [
                response(tool_call("get_room_snapshot", {}, "call-1")),
                response(tool_call("set_room_scene", scene_arguments(), "call-2")),
                RuntimeError("simulated OpenAI outage"),
            ]
        )
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)
        before = await engine.snapshot()

        await orchestrator.submit(
            AssistantRequest(text="Đặt AC 25 độ và quạt mức 1.", source="text", session_id="test")
        )
        await orchestrator.wait_idle()

        after = await engine.snapshot()
        conversation = storage.conversations(1)[0]
        assert after == before
        assert conversation.status == "failed"
        assert "outage" in conversation.error_message

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
                "requested_intent": "độ sáng khi làm việc",
                "preferred_result": preference_targets(
                    main_light_power=True,
                    main_light_brightness_percent=70,
                ),
            }, "call-1")),
            response(text="Đã ghi nhớ đèn 70 phần trăm khi làm việc."),
        ])
        orchestrator, engine, storage = build_orchestrator(tmp_path, client)

        await orchestrator.submit(
            AssistantRequest(
                text="Không, khi làm việc tôi muốn đèn 70 phần trăm.",
                session_id="test",
            )
        )
        await orchestrator.wait_idle()

        learned = storage.preferences()[0]
        assert learned.source == "user_correction"
        assert learned.confirmed is True

        arguments = scene_arguments()
        arguments.update({
            "ac_temperature_c": None,
            "fan_speed": None,
            "main_light_power": True,
            "main_light_brightness_percent": 70,
            "applied_preference_id": learned.id,
            "reason": "Áp dụng độ sáng làm việc đã học.",
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

    asyncio.run(run())
