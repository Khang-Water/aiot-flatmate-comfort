import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.asr import Transcription
from app.main import app, encode_sse, offline_tts, vietnamese_asr
from app.tts import SynthesizedSpeech


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        test_client.post("/api/simulation/control", json={"action": "pause"})
        yield test_client


def reset(client: TestClient) -> dict:
    client.post("/api/simulation/control", json={"action": "reset"})
    client.post("/api/simulation/control", json={"action": "pause"})
    return client.get("/api/state").json()


def test_health_reports_ready_simulation(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == {"ready": True, "status": "ready"}
    assert body["simulation"]["phase"] == "simulation"
    assert body["simulation"]["seed"] == 42


def test_snapshot_matches_phase_zero_contract(client: TestClient) -> None:
    response = client.get("/api/state")

    assert response.status_code == 200
    schema_path = Path(__file__).resolve().parents[2] / "contracts" / "room-snapshot.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(response.json())


def test_cors_allows_configured_web_origin(client: TestClient) -> None:
    response = client.options(
        "/api/state",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_sse_encoding_preserves_vietnamese_text() -> None:
    event = encode_sse("trace", 7, {"title_vi": "Đã kết nối"})

    assert event.startswith("id: 7\nevent: trace\n")
    assert 'data: {"title_vi":"Đã kết nối"}\n\n' in event


def test_scenarios_activate_and_change_state(client: TestClient) -> None:
    reset(client)
    listing = client.get("/api/scenarios").json()

    assert len(listing["scenarios"]) == 10
    response = client.post("/api/scenarios/hot_room/activate")
    assert response.status_code == 200
    assert response.json()["active_scenario_id"] == "hot_room"

    snapshot = client.get("/api/state").json()
    assert snapshot["environment"]["temperature_c"] == 33.0
    assert snapshot["environment"]["humidity_percent"] == 78.0


def test_device_command_is_atomic_and_normalized(client: TestClient) -> None:
    reset(client)
    response = client.post(
        "/api/devices/fan/commands",
        json={"values": {"speed": 2}, "source": "manual"},
    )

    assert response.status_code == 200
    snapshot = client.get("/api/state").json()
    assert snapshot["devices"]["fan"]["speed"] == 2
    assert snapshot["devices"]["fan"]["power"] is True

    version = snapshot["version"]
    invalid = client.post(
        "/api/devices/fan/commands",
        json={"values": {"speed": 9}, "source": "manual"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_device_value"
    assert client.get("/api/state").json()["version"] == version


def test_history_starts_with_generated_baseline(client: TestClient) -> None:
    response = client.get("/api/history", params={"metric": "temperature_c", "limit": 60})

    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "temperature_c"
    assert len(body["points"]) == 60
    assert all(point["unit"] == "°C" for point in body["points"])


def test_history_is_clamped_to_latest_24_simulated_hours(client: TestClient) -> None:
    state = reset(client)
    end = datetime.fromisoformat(state["timestamp"])
    response = client.get(
        "/api/history",
        params={
            "metric": "co2_ppm",
            "from": (end - timedelta(days=3)).isoformat(),
            "limit": 1_440,
        },
    )

    points = response.json()["points"]
    assert response.status_code == 200
    assert points
    assert datetime.fromisoformat(points[0]["timestamp"]) >= end - timedelta(hours=24)
    assert datetime.fromisoformat(points[-1]["timestamp"]) <= end


def test_control_validation_and_reproducible_reset(client: TestClient) -> None:
    first = reset(client)
    client.post("/api/scenarios/polluted_air/activate")
    second = reset(client)

    assert first == second
    invalid = client.post("/api/simulation/control", json={"action": "set_speed"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_request"


def test_assistant_reports_missing_api_key_when_unconfigured(client: TestClient) -> None:
    health = client.get("/api/health").json()
    if health["openai_configured"]:
        pytest.skip("OpenAI key configured in local environment")

    response = client.post(
        "/api/assistant/requests",
        json={"text": "Làm phòng mát hơn.", "source": "text", "session_id": "test-browser"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "openai_not_configured"


def test_tts_returns_actual_engine_headers_without_loading_model(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        offline_tts,
        "synthesize",
        lambda text: SynthesizedSpeech(
            b"RIFF-test-wave",
            1.25,
            text.lower(),
            "vieneu-v3-turbo-onnx-int8",
            "Mai Anh",
        ),
    )

    response = client.post("/api/tts", json={"text": "Xin chào"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["x-tts-engine"] == "vieneu-v3-turbo-onnx-int8"
    assert response.headers["x-tts-voice"] == "Mai Anh"
    assert response.content.startswith(b"RIFF")


def test_asr_returns_vietnamese_transcript_without_loading_model(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vietnamese_asr,
        "transcribe",
        lambda _: Transcription("Tắt điều hòa", "vi", 0.99, 1.4),
    )

    response = client.post("/api/asr", files={"audio": ("command.webm", b"audio-data", "audio/webm")})

    assert response.status_code == 200
    assert response.json()["text"] == "Tắt điều hòa"
    assert response.json()["language"] == "vi"
