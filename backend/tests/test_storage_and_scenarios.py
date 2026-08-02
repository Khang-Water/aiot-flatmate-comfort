from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.models import PreferenceCreate, PreferenceTargets
from app.scenarios import ScenarioRepository
from app.simulation import generate_baseline
from app.storage import Storage, write_generated_csv


def test_all_committed_scenarios_load() -> None:
    directory = Path(__file__).resolve().parents[2] / "data" / "scenarios"
    repository = ScenarioRepository(directory)

    repository.load()

    assert len(repository.summaries()) == 10
    assert repository.get("reading_in_bed") is not None


def test_storage_seeds_history_once_and_exports_csv(tmp_path: Path) -> None:
    snapshots = generate_baseline(42)
    storage = Storage(tmp_path / "flatmate.db")
    storage.initialize()

    storage.seed_history(snapshots)
    storage.seed_history(snapshots)
    latest = snapshots[-1]
    replacement = latest.model_copy(
        update={"environment": latest.environment.model_copy(update={"co2_ppm": 999.0})}
    )
    storage.record_snapshot(replacement)
    points = storage.history("co2_ppm", None, None, 2_000)
    write_generated_csv(tmp_path / "generated", snapshots)

    assert len(points) == 1_440
    assert points[-1].value == 999.0
    assert (tmp_path / "generated" / "sensor_history.csv").is_file()
    assert (tmp_path / "generated" / "device_history.csv").is_file()


def test_preference_lifecycle_and_scoped_learned_reset(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "preferences.db")
    storage.initialize()
    now = datetime.now(UTC)
    explicit = storage.create_preference(
        PreferenceCreate(
            context="working",
            requested_intent="nhiệt độ khi làm việc",
            preferred_result=PreferenceTargets(ac_power=True, ac_temperature_c=25),
            source="explicit",
        ),
        now,
    )
    correction = storage.record_preference_correction(
        request_id="request-1",
        session_id="session-1",
        context="working",
        requested_intent="độ sáng khi làm việc",
        correction_text="Tăng đèn lên 70 phần trăm",
        preferred_result=PreferenceTargets(main_light_power=True, main_light_brightness_percent=70),
        now=now,
    )
    learned = storage.record_preference_correction(
        request_id="request-2",
        session_id="session-1",
        context="working",
        requested_intent="độ sáng khi làm việc",
        correction_text="Tôi vẫn muốn đèn 70 phần trăm",
        preferred_result=PreferenceTargets(main_light_power=True, main_light_brightness_percent=70),
        now=now + timedelta(minutes=5),
    )

    assert explicit.confirmed is True
    assert correction.source == "user_correction"
    assert correction.confidence == 0.85
    assert correction.confirmed is True
    assert learned.source == "user_correction"
    assert learned.confirmed is True
    assert learned.observation_count == 2
    relevant_ids = {item.id for item in storage.relevant_preferences("working", now + timedelta(minutes=7))}
    assert relevant_ids == {explicit.id, learned.id}
    assert storage.reset_learned_preferences() == 1
    assert [item.id for item in storage.preferences()] == [explicit.id]


def test_recent_session_conversations_are_scoped_bounded_and_chronological(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "conversation-history.db")
    storage.initialize()
    now = datetime.now(UTC)
    for index in range(8):
        request_id = f"same-{index}"
        created_at = now + timedelta(minutes=index)
        storage.start_conversation(request_id, "same", "text", f"user {index}", created_at)
        storage.finish_conversation(
            request_id,
            status="completed",
            assistant_text=f"assistant {index}",
            error_message="",
            completed_at=created_at + timedelta(seconds=1),
        )
    storage.start_conversation("other", "other", "text", "private", now + timedelta(minutes=9))
    storage.finish_conversation(
        "other",
        status="completed",
        assistant_text="must not leak",
        error_message="",
        completed_at=now + timedelta(minutes=9, seconds=1),
    )
    storage.start_conversation("failed", "same", "text", "failed", now + timedelta(minutes=10))
    storage.finish_conversation(
        "failed",
        status="failed",
        assistant_text="error",
        error_message="failed",
        completed_at=now + timedelta(minutes=10, seconds=1),
    )

    history = storage.recent_session_conversations("same")

    assert [turn.user_text for turn in history] == [f"user {index}" for index in range(2, 8)]
    assert all(turn.session_id == "same" and turn.status == "completed" for turn in history)


def test_newest_explicit_preference_is_returned_first(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "preference-order.db")
    storage.initialize()
    now = datetime.now(UTC)
    older = storage.create_preference(
        PreferenceCreate(
            context="working",
            requested_intent="đèn khi làm việc",
            preferred_result=PreferenceTargets(main_light_brightness_percent=70),
        ),
        now,
    )
    newer = storage.create_preference(
        PreferenceCreate(
            context="working",
            requested_intent="làm việc",
            preferred_result=PreferenceTargets(
                main_light_brightness_percent=50,
                main_light_color_temperature_kelvin=2700,
            ),
        ),
        now + timedelta(minutes=1),
    )

    relevant = storage.relevant_preferences("working", now + timedelta(minutes=2))

    assert [item.id for item in relevant] == [newer.id, older.id]
