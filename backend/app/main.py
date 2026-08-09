import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI

from app.assistant import AssistantBusy, AssistantNotConfigured, AssistantOrchestrator
from app.commands import CommandValidationError
from app.config import PROJECT_ROOT, get_settings
from app.models import (
    AssistantAccepted,
    AssistantRequest,
    CommandResult,
    ConversationList,
    DatabaseHealth,
    DeviceCommand,
    ErrorBody,
    ErrorResponse,
    HealthResponse,
    HistoryResponse,
    PreferenceCreate,
    PreferenceList,
    PreferenceRecord,
    PreferenceReset,
    PreferenceResetResult,
    PreferenceUpdate,
    RoomSnapshot,
    ScenarioList,
    SimulationControl,
    SimulationStatus,
    SpeechRequest,
    TranscriptionResponse,
)
from app.scenarios import ScenarioRepository
from app.simulation import SimulationEngine, prepare_baseline_data
from app.state import EventBroker, SseMessage
from app.storage import METRICS, Storage

APP_VERSION = "0.6.0"
BANGKOK = ZoneInfo("Asia/Bangkok")
settings = get_settings()
storage = Storage(settings.database_path)
scenarios = ScenarioRepository(PROJECT_ROOT / "data" / "scenarios")
broker = EventBroker()
engine = SimulationEngine(
    seed=settings.simulation_seed,
    tick_seconds=settings.simulation_tick_seconds,
    minutes_per_tick=settings.simulation_minutes_per_tick,
    storage=storage,
    scenarios=scenarios,
    broker=broker,
)
openai_client = (
    AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    if settings.openai_api_key
    else None
)
assistant = AssistantOrchestrator(
    client=openai_client,
    model=settings.openai_model,
    api_mode=settings.openai_api_mode,
    reasoning_effort=settings.openai_reasoning_effort,
    timeout_seconds=settings.openai_timeout_seconds,
    engine=engine,
    storage=storage,
    broker=broker,
)
offline_tts: Any | None = None
vietnamese_asr: Any | None = None
if settings.local_speech_enabled:
    from app.asr import VietnameseAsr
    from app.tts import OfflineTts, SupertonicTts, VieneuTts

    supertonic_tts = SupertonicTts(
        voice=settings.supertonic_voice,
        steps=settings.supertonic_steps,
        speed=settings.supertonic_speed,
    )
    vieneu_tts = VieneuTts(voice=settings.vieneu_voice)
    offline_tts = OfflineTts(
        primary=vieneu_tts if settings.tts_engine == "vieneu" else supertonic_tts,
        fallback=supertonic_tts if settings.tts_engine == "vieneu" else None,
    )
    vietnamese_asr = VietnameseAsr(
        model_name=settings.asr_model,
        device=settings.asr_device,
        compute_type=settings.asr_compute_type,
        beam_size=settings.asr_beam_size,
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    storage.initialize()
    scenarios.load()
    prepare_baseline_data(storage, PROJECT_ROOT / "data" / "generated", settings.simulation_seed)
    storage.record_snapshot(await engine.snapshot())
    await engine.start()
    try:
        yield
    finally:
        await assistant.shutdown()
        await engine.stop()
        if openai_client:
            await openai_client.close()


app = FastAPI(title="FlatMate Comfort API", version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def encode_sse(event: str, sequence: int, data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {sequence}\nevent: {event}\ndata: {payload}\n\n"


def error_response(status_code: int, code: str, message: str, details: dict[str, Any]) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


@app.exception_handler(CommandValidationError)
async def command_error_handler(_: Request, error: CommandValidationError) -> JSONResponse:
    return error_response(422, "invalid_device_value", str(error), error.details)


@app.exception_handler(AssistantNotConfigured)
async def assistant_config_error(_: Request, error: AssistantNotConfigured) -> JSONResponse:
    return error_response(503, "openai_not_configured", str(error), {})


@app.exception_handler(AssistantBusy)
async def assistant_busy_error(_: Request, error: AssistantBusy) -> JSONResponse:
    return error_response(409, "assistant_busy", str(error), {})


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    errors = [
        {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
        for item in error.errors()
    ]
    return error_response(422, "invalid_request", "Dữ liệu yêu cầu không hợp lệ.", {"errors": errors})


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        timestamp=(await engine.snapshot()).timestamp,
        database=DatabaseHealth(ready=storage.ready, status="ready" if storage.ready else "not_initialized"),
        simulation=await engine.status(),
        openai_configured=assistant.configured,
        openai_model=settings.openai_model,
    )


@app.get("/api/state", response_model=RoomSnapshot)
async def room_state() -> RoomSnapshot:
    return await engine.snapshot()


@app.get("/api/simulation", response_model=SimulationStatus)
async def simulation_status() -> SimulationStatus:
    return await engine.status()


@app.post("/api/simulation/control", response_model=SimulationStatus)
async def control_simulation(control: SimulationControl) -> SimulationStatus:
    return await engine.control(control)


@app.get("/api/scenarios", response_model=ScenarioList)
async def list_scenarios() -> ScenarioList:
    status = await engine.status()
    return ScenarioList(active_scenario_id=status.active_scenario_id, scenarios=scenarios.summaries())


@app.post("/api/scenarios/{scenario_id}/activate", response_model=SimulationStatus)
async def activate_scenario(scenario_id: str) -> SimulationStatus:
    scenario = scenarios.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return await engine.activate_scenario(scenario)


@app.post("/api/devices/{device_id}/commands", response_model=CommandResult)
async def command_device(device_id: str, command: DeviceCommand) -> CommandResult:
    return await engine.command_device(device_id, command)


@app.post("/api/assistant/requests", response_model=AssistantAccepted, status_code=202)
async def assistant_request(request: AssistantRequest) -> AssistantAccepted:
    return await assistant.submit(request)


@app.post("/api/tts")
async def synthesize_speech(request: SpeechRequest) -> Response:
    if offline_tts is None:
        raise HTTPException(status_code=503, detail="Local TTS is disabled; use browser speech synthesis.")
    try:
        speech = await asyncio.to_thread(offline_tts.synthesize, request.text)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Không thể tạo giọng đọc ngoại tuyến.") from error
    return Response(
        content=speech.audio,
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-store",
            "X-Audio-Duration": f"{speech.duration_seconds:.3f}",
            "X-TTS-Engine": speech.engine,
            "X-TTS-Voice": speech.voice,
        },
    )


@app.post("/api/asr", response_model=TranscriptionResponse)
async def transcribe_speech(audio: Annotated[UploadFile, File()]) -> TranscriptionResponse:
    if vietnamese_asr is None:
        raise HTTPException(status_code=503, detail="Local ASR is disabled; use browser speech recognition.")
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=415, detail="Tệp tải lên phải là âm thanh.")
    payload = await audio.read(15 * 1024 * 1024 + 1)
    if not payload:
        raise HTTPException(status_code=422, detail="Âm thanh trống.")
    if len(payload) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Âm thanh vượt quá 15 MB.")
    try:
        result = await asyncio.to_thread(vietnamese_asr.transcribe, payload)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Không thể nhận dạng giọng nói tiếng Việt.") from error
    if not result.text:
        raise HTTPException(status_code=422, detail="Không nhận diện được nội dung giọng nói.")
    return TranscriptionResponse(
        text=result.text,
        language=result.language,
        language_probability=result.language_probability,
        duration_seconds=result.duration_seconds,
    )


@app.get("/api/conversations", response_model=ConversationList)
async def conversations(limit: Annotated[int, Query(ge=1, le=200)] = 50) -> ConversationList:
    return ConversationList(conversations=storage.conversations(limit))


@app.get("/api/preferences", response_model=PreferenceList)
async def list_preferences() -> PreferenceList:
    return PreferenceList(preferences=storage.preferences())


@app.post("/api/preferences", response_model=PreferenceRecord, status_code=201)
async def create_preference(preference: PreferenceCreate) -> PreferenceRecord:
    return storage.create_preference(preference, datetime.now(BANGKOK))


@app.put("/api/preferences/{preference_id}", response_model=PreferenceRecord)
async def update_preference(preference_id: str, update: PreferenceUpdate) -> PreferenceRecord:
    try:
        return storage.update_preference(preference_id, update, datetime.now(BANGKOK))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Không tìm thấy sở thích.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/preferences/{preference_id}", status_code=204)
async def delete_preference(preference_id: str) -> Response:
    if not storage.delete_preference(preference_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy sở thích.")
    return Response(status_code=204)


@app.post("/api/preferences/reset-learned", response_model=PreferenceResetResult)
async def reset_learned_preferences(reset: PreferenceReset) -> PreferenceResetResult:
    if not reset.confirm:
        raise HTTPException(status_code=422, detail="Cần xác nhận trước khi xóa preference đã học.")
    return PreferenceResetResult(deleted=storage.reset_learned_preferences())


@app.get("/api/history", response_model=HistoryResponse)
async def history(
    metric: str,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=1_440)] = 1_440,
) -> HistoryResponse:
    if metric not in METRICS:
        raise HTTPException(status_code=400, detail=f"Unknown metric: {metric}")
    reference = (await engine.snapshot()).timestamp
    end = end or reference
    start = max(start, end - timedelta(hours=24)) if start else end - timedelta(hours=24)
    return HistoryResponse(metric=metric, points=storage.history(metric, start, end, limit))


async def event_stream(request: Request) -> AsyncIterator[str]:
    async with broker.subscribe() as queue:
        snapshot = (await engine.snapshot()).model_dump(mode="json")
        yield encode_sse("snapshot", broker.next_sequence(), snapshot)

        while not await request.is_disconnected():
            try:
                message: SseMessage = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield f": heartbeat {(await engine.snapshot()).timestamp.isoformat()}\n\n"
                continue
            yield encode_sse(message.event, message.sequence, message.data)


@app.get("/api/events")
async def events(request: Request) -> StreamingResponse:
    return StreamingResponse(
        event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def mount_frontend(application: FastAPI, export_directory: Path) -> bool:
    if not export_directory.is_dir():
        return False
    application.mount("/", StaticFiles(directory=export_directory, html=True), name="frontend")
    return True


mount_frontend(app, PROJECT_ROOT / "frontend" / "out")
