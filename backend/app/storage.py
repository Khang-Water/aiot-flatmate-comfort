import csv
import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import (
    AssistantTraceEvent,
    ChangedValue,
    ConversationRecord,
    HistoryPoint,
    PreferenceCreate,
    PreferenceRecord,
    PreferenceTargets,
    PreferenceUpdate,
    RoomSnapshot,
)

METRICS: dict[str, tuple[str, str]] = {
    "temperature_c": ("temperature_c", "°C"),
    "humidity_percent": ("humidity_percent", "%"),
    "co2_ppm": ("co2_ppm", "ppm"),
    "pm25_ug_m3": ("pm25_ug_m3", "µg/m³"),
    "ambient_light_lux": ("ambient_light_lux", "lux"),
    "noise_db": ("noise_db", "dB"),
    "ac_temperature_c": ("ac_temperature_c", "°C"),
    "fan_speed": ("fan_speed", "level"),
    "main_light_brightness_percent": ("main_light_brightness_percent", "%"),
    "curtain_position_percent": ("curtain_position_percent", "%"),
    "air_purifier_speed": ("air_purifier_speed", "level"),
}

IMPLICIT_FEEDBACK_WINDOW = timedelta(minutes=30)
IMPLICIT_PROMOTION_OBSERVATIONS = 3
IMPLICIT_PREFERENCE_FIELDS: dict[tuple[str, str], tuple[str, str, str]] = {
    ("ac", "power"): ("devices.ac.power", "ac_power", "trạng thái điều hòa"),
    ("ac", "temperature_c"): ("devices.ac.temperature_c", "ac_temperature_c", "nhiệt độ điều hòa"),
    ("fan", "power"): ("devices.fan.power", "fan_power", "trạng thái quạt"),
    ("fan", "speed"): ("devices.fan.speed", "fan_speed", "tốc độ quạt"),
    ("main_light", "power"): ("devices.main_light.power", "main_light_power", "trạng thái đèn chính"),
    ("main_light", "brightness_percent"): (
        "devices.main_light.brightness_percent",
        "main_light_brightness_percent",
        "độ sáng đèn chính",
    ),
    ("main_light", "color_temperature_kelvin"): (
        "devices.main_light.color_temperature_kelvin",
        "main_light_color_temperature_kelvin",
        "màu ánh sáng đèn chính",
    ),
    ("bedside_light", "power"): (
        "devices.bedside_light.power",
        "bedside_light_power",
        "trạng thái đèn đầu giường",
    ),
    ("bedside_light", "brightness_percent"): (
        "devices.bedside_light.brightness_percent",
        "bedside_light_brightness_percent",
        "độ sáng đèn đầu giường",
    ),
    ("bedside_light", "color_temperature_kelvin"): (
        "devices.bedside_light.color_temperature_kelvin",
        "bedside_light_color_temperature_kelvin",
        "màu ánh sáng đèn đầu giường",
    ),
    ("air_purifier", "power"): (
        "devices.air_purifier.power",
        "air_purifier_power",
        "trạng thái máy lọc không khí",
    ),
    ("air_purifier", "speed"): (
        "devices.air_purifier.speed",
        "air_purifier_speed",
        "tốc độ máy lọc không khí",
    ),
    ("curtain", "position_percent"): (
        "devices.curtain.position_percent",
        "curtain_position_percent",
        "độ mở rèm",
    ),
    ("window", "state"): ("openings.window_state", "window_state", "trạng thái cửa sổ"),
    ("humidity_device", "power"): (
        "devices.humidity_device.power",
        "humidity_device_power",
        "trạng thái thiết bị độ ẩm",
    ),
    ("humidity_device", "target_humidity_percent"): (
        "devices.humidity_device.target_humidity_percent",
        "target_humidity_percent",
        "mức độ ẩm mục tiêu",
    ),
    ("desk_computer", "state"): (
        "power.smart_plugs.desk_computer.state",
        "desk_computer_power",
        "trạng thái máy tính bàn",
    ),
    ("monitor", "state"): (
        "power.smart_plugs.monitor.state",
        "monitor_power",
        "trạng thái màn hình",
    ),
}

SENSOR_COLUMNS = [
    "timestamp",
    "version",
    "temperature_c",
    "humidity_percent",
    "co2_ppm",
    "pm25_ug_m3",
    "ambient_light_lux",
    "noise_db",
    "room_present",
    "bed_occupied",
    "desk_occupied",
    "window_state",
    "curtain_position_percent",
    "computer_power_watts",
    "inferred_context",
    "ac_temperature_c",
    "fan_speed",
    "main_light_brightness_percent",
    "air_purifier_speed",
]


class Storage:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.ready = False

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sensor_samples (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    temperature_c REAL NOT NULL,
                    humidity_percent REAL NOT NULL,
                    co2_ppm REAL NOT NULL,
                    pm25_ug_m3 REAL NOT NULL,
                    ambient_light_lux REAL NOT NULL,
                    noise_db REAL NOT NULL,
                    room_present INTEGER NOT NULL,
                    bed_occupied INTEGER NOT NULL,
                    desk_occupied INTEGER NOT NULL,
                    window_state TEXT NOT NULL,
                    curtain_position_percent INTEGER NOT NULL,
                    computer_power_watts REAL NOT NULL,
                    inferred_context TEXT NOT NULL,
                    ac_temperature_c REAL NOT NULL,
                    fan_speed INTEGER NOT NULL,
                    main_light_brightness_percent INTEGER NOT NULL,
                    air_purifier_speed INTEGER NOT NULL
                );
                DELETE FROM sensor_samples
                WHERE id NOT IN (
                    SELECT MAX(id) FROM sensor_samples GROUP BY timestamp
                );
                DROP INDEX IF EXISTS idx_sensor_samples_timestamp;
                CREATE UNIQUE INDEX idx_sensor_samples_timestamp
                    ON sensor_samples(timestamp);
                CREATE TABLE IF NOT EXISTS device_actions (
                    id INTEGER PRIMARY KEY,
                    command_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    property TEXT NOT NULL,
                    before_json TEXT NOT NULL,
                    after_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS simulation_events (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    request_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    user_text TEXT NOT NULL,
                    assistant_text TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_session_created
                    ON conversations(session_id, created_at);
                CREATE TABLE IF NOT EXISTS assistant_trace_events (
                    id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title_vi TEXT NOT NULL,
                    summary_vi TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    error_json TEXT,
                    duration_ms INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_trace_request_sequence
                    ON assistant_trace_events(request_id, sequence);
                CREATE TABLE IF NOT EXISTS preferences (
                    id TEXT PRIMARY KEY,
                    context TEXT NOT NULL,
                    requested_intent TEXT NOT NULL,
                    preferred_result_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    observation_count INTEGER NOT NULL,
                    confirmed INTEGER NOT NULL,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_preferences_context
                    ON preferences(context, confirmed, updated_at);
                CREATE TABLE IF NOT EXISTS preference_evidence (
                    id TEXT PRIMARY KEY,
                    preference_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    correction_text TEXT NOT NULL,
                    preferred_result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(preference_id) REFERENCES preferences(id) ON DELETE CASCADE
                );
                """
            )
        self.ready = True

    def record_snapshot(self, snapshot: RoomSnapshot) -> None:
        row = snapshot_row(snapshot)
        placeholders = ",".join("?" for _ in SENSOR_COLUMNS)
        updates = ",".join(
            f"{column}=excluded.{column}" for column in SENSOR_COLUMNS if column != "timestamp"
        )
        with self.connect() as connection:
            connection.execute(
                f"""
                INSERT INTO sensor_samples ({','.join(SENSOR_COLUMNS)}) VALUES ({placeholders})
                ON CONFLICT(timestamp) DO UPDATE SET {updates}
                """,
                [row[column] for column in SENSOR_COLUMNS],
            )

    def seed_history(self, snapshots: Iterable[RoomSnapshot]) -> None:
        with self.connect() as connection:
            rows = [snapshot_row(snapshot) for snapshot in snapshots]
            placeholders = ",".join("?" for _ in SENSOR_COLUMNS)
            updates = ",".join(
                f"{column}=excluded.{column}" for column in SENSOR_COLUMNS if column != "timestamp"
            )
            connection.executemany(
                f"""
                INSERT INTO sensor_samples ({','.join(SENSOR_COLUMNS)}) VALUES ({placeholders})
                ON CONFLICT(timestamp) DO UPDATE SET {updates}
                """,
                ([row[column] for column in SENSOR_COLUMNS] for row in rows),
            )

    def record_changes(
        self,
        command_id: str,
        timestamp: datetime,
        device_id: str,
        changes: list[ChangedValue],
        source: str,
        reason: str,
    ) -> None:
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO device_actions
                    (
                        command_id, timestamp, device_id, property,
                        before_json, after_json, source, reason
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        command_id,
                        timestamp.isoformat(),
                        device_id,
                        change.path,
                        json.dumps(change.before, ensure_ascii=False),
                        json.dumps(change.after, ensure_ascii=False),
                        source,
                        reason,
                    )
                    for change in changes
                ),
            )

    def record_implicit_feedback(
        self,
        *,
        command_id: str,
        timestamp: datetime,
        context: str,
        device_id: str,
        supplied_values: dict[str, Any],
        changes: list[ChangedValue],
    ) -> list[PreferenceRecord]:
        changes_by_path = {change.path: change for change in changes}
        learned_ids: list[str] = []
        cutoff = (timestamp - IMPLICIT_FEEDBACK_WINDOW).isoformat()
        observed_at = timestamp.isoformat()

        with self.connect() as connection:
            for supplied_field in supplied_values:
                mapping = IMPLICIT_PREFERENCE_FIELDS.get((device_id, supplied_field))
                if mapping is None:
                    continue
                property_path, target_field, requested_intent = mapping
                change = changes_by_path.get(property_path)
                if change is None:
                    continue

                previous = connection.execute(
                    """
                    SELECT command_id, source, after_json
                    FROM device_actions
                    WHERE property = ?
                      AND command_id != ?
                      AND timestamp >= ?
                      AND timestamp <= ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (property_path, command_id, cutoff, observed_at),
                ).fetchone()
                if previous is None or previous["source"] != "assistant":
                    continue
                if json.loads(previous["after_json"]) != change.before:
                    continue

                preferred_value = change.after
                if target_field in {"desk_computer_power", "monitor_power"}:
                    preferred_value = preferred_value == "on"
                preferred_result = PreferenceTargets.model_validate({target_field: preferred_value})
                preferred_result_json = preferred_result.model_dump_json(exclude_none=True)

                candidate = connection.execute(
                    """
                    SELECT id, observation_count
                    FROM preferences
                    WHERE context = ?
                      AND requested_intent = ?
                      AND preferred_result_json = ?
                      AND source = 'learned'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (context, requested_intent, preferred_result_json),
                ).fetchone()
                observation_count = int(candidate["observation_count"]) + 1 if candidate else 1
                confirmed = observation_count >= IMPLICIT_PROMOTION_OBSERVATIONS
                confidence = min(0.98, observation_count / IMPLICIT_PROMOTION_OBSERVATIONS)

                if candidate is None:
                    preference_id = str(uuid4())
                    connection.execute(
                        """
                        INSERT INTO preferences (
                            id, context, requested_intent, preferred_result_json, source,
                            confidence, observation_count, confirmed, expires_at,
                            created_at, updated_at, last_used_at
                        ) VALUES (?, ?, ?, ?, 'learned', ?, ?, ?, NULL, ?, ?, NULL)
                        """,
                        (
                            preference_id,
                            context,
                            requested_intent,
                            preferred_result_json,
                            confidence,
                            observation_count,
                            int(confirmed),
                            observed_at,
                            observed_at,
                        ),
                    )
                else:
                    preference_id = candidate["id"]
                    connection.execute(
                        """
                        UPDATE preferences
                        SET confidence = ?, observation_count = ?, confirmed = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (confidence, observation_count, int(confirmed), observed_at, preference_id),
                    )

                if confirmed:
                    connection.execute(
                        """
                        UPDATE preferences
                        SET confirmed = 0
                        WHERE context = ?
                          AND requested_intent = ?
                          AND source = 'learned'
                          AND id != ?
                        """,
                        (context, requested_intent, preference_id),
                    )

                # ponytail: exact repeated targets and simulated-time window fit local controls;
                # add tolerant clustering and wall-clock timestamps when input becomes noisy.
                connection.execute(
                    """
                    INSERT INTO preference_evidence (
                        id, preference_id, request_id, session_id, correction_text,
                        preferred_result_json, created_at
                    ) VALUES (?, ?, ?, 'implicit-feedback', ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        preference_id,
                        command_id,
                        (
                            f"Manual override {property_path} from {change.before!r} to {change.after!r} "
                            f"after assistant command {previous['command_id']}."
                        ),
                        preferred_result_json,
                        observed_at,
                    ),
                )
                learned_ids.append(preference_id)

        return [self.get_preference(preference_id) for preference_id in learned_ids]

    def record_simulation_event(self, timestamp: datetime, event: str, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO simulation_events (timestamp, event, payload_json) VALUES (?, ?, ?)",
                (timestamp.isoformat(), event, json.dumps(payload, ensure_ascii=False)),
            )

    def recent_actions(self, limit: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, device_id, property, before_json, after_json, source, reason
                FROM device_actions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "device_id": row["device_id"],
                "property": row["property"],
                "before": json.loads(row["before_json"]),
                "after": json.loads(row["after_json"]),
                "source": row["source"],
                "reason": row["reason"],
            }
            for row in rows
        ]

    def start_conversation(
        self,
        request_id: str,
        session_id: str,
        source: str,
        user_text: str,
        created_at: datetime,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations
                    (request_id, session_id, source, user_text, status, created_at)
                VALUES (?, ?, ?, ?, 'processing', ?)
                """,
                (request_id, session_id, source, user_text, created_at.isoformat()),
            )

    def finish_conversation(
        self,
        request_id: str,
        *,
        status: str,
        assistant_text: str,
        error_message: str,
        completed_at: datetime,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE conversations
                SET status = ?, assistant_text = ?, error_message = ?, completed_at = ?
                WHERE request_id = ?
                """,
                (status, assistant_text, error_message, completed_at.isoformat(), request_id),
            )

    def record_trace(self, event: AssistantTraceEvent) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO assistant_trace_events
                    (
                        id, request_id, sequence, timestamp, stage, status,
                        title_vi, summary_vi, data_json, error_json, duration_ms
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.request_id,
                    event.sequence,
                    event.timestamp.isoformat(),
                    event.stage,
                    event.status,
                    event.title_vi,
                    event.summary_vi,
                    json.dumps(event.data, ensure_ascii=False),
                    json.dumps(event.error.model_dump(mode="json"), ensure_ascii=False) if event.error else None,
                    event.duration_ms,
                ),
            )

    def conversations(self, limit: int) -> list[ConversationRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT request_id, session_id, source, user_text, assistant_text,
                       status, error_message, created_at, completed_at
                FROM conversations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            ConversationRecord(
                request_id=row["request_id"],
                session_id=row["session_id"],
                source=row["source"],
                user_text=row["user_text"],
                assistant_text=row["assistant_text"],
                status=row["status"],
                error_message=row["error_message"],
                created_at=datetime.fromisoformat(row["created_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            )
            for row in rows
        ]

    def recent_session_conversations(
        self,
        session_id: str,
        limit: int = 6,
    ) -> list[ConversationRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT request_id, session_id, source, user_text, assistant_text,
                       status, error_message, created_at, completed_at
                FROM conversations
                WHERE session_id = ? AND status = 'completed' AND assistant_text != ''
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            ConversationRecord(
                request_id=row["request_id"],
                session_id=row["session_id"],
                source=row["source"],
                user_text=row["user_text"],
                assistant_text=row["assistant_text"],
                status=row["status"],
                error_message=row["error_message"],
                created_at=datetime.fromisoformat(row["created_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            )
            for row in reversed(rows)
        ]

    def create_preference(self, preference: PreferenceCreate, now: datetime) -> PreferenceRecord:
        preference_id = str(uuid4())
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO preferences (
                    id, context, requested_intent, preferred_result_json, source,
                    confidence, observation_count, confirmed, expires_at,
                    created_at, updated_at, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    preference_id,
                    preference.context,
                    preference.requested_intent,
                    preference.preferred_result.model_dump_json(exclude_none=True),
                    preference.source,
                    1.0,
                    1,
                    1,
                    preference.expires_at.isoformat() if preference.expires_at else None,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.get_preference(preference_id)

    def get_preference(self, preference_id: str) -> PreferenceRecord:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM preferences WHERE id = ?", (preference_id,)).fetchone()
        if row is None:
            raise KeyError(preference_id)
        return preference_from_row(row)

    def preferences(self) -> list[PreferenceRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM preferences ORDER BY confirmed DESC, updated_at DESC"
            ).fetchall()
        return [preference_from_row(row) for row in rows]

    def active_preferences(self, now: datetime, limit: int = 50) -> list[PreferenceRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM preferences
                WHERE confirmed = 1
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY
                    CASE source
                        WHEN 'explicit' THEN 0
                        WHEN 'temporary' THEN 1
                        WHEN 'user_correction' THEN 2
                        ELSE 3
                    END,
                    updated_at DESC
                LIMIT ?
                """,
                (now.isoformat(), limit),
            ).fetchall()
        return [preference_from_row(row) for row in rows]

    def relevant_preferences(
        self,
        context: str,
        now: datetime,
        limit: int = 10,
    ) -> list[PreferenceRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM preferences
                WHERE context IN (?, 'any')
                  AND confirmed = 1
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY
                    CASE source
                        WHEN 'explicit' THEN 0
                        WHEN 'temporary' THEN 1
                        WHEN 'user_correction' THEN 2
                        ELSE 3
                    END,
                    CASE WHEN context = ? THEN 0 ELSE 1 END,
                    updated_at DESC
                LIMIT ?
                """,
                (context, now.isoformat(), context, limit),
            ).fetchall()
        return [preference_from_row(row) for row in rows]

    def update_preference(
        self,
        preference_id: str,
        update: PreferenceUpdate,
        now: datetime,
    ) -> PreferenceRecord:
        current = self.get_preference(preference_id)
        values = update.model_dump(exclude_unset=True)
        merged = current.model_dump()
        merged.update(values)
        source = merged["source"]
        expires_at = merged["expires_at"]
        if source == "temporary" and expires_at is None:
            raise ValueError("temporary preference requires expires_at")
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE preferences
                SET context = ?, requested_intent = ?, preferred_result_json = ?,
                    source = ?, confidence = 1, confirmed = 1, expires_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    merged["context"],
                    merged["requested_intent"],
                    PreferenceTargets.model_validate(merged["preferred_result"]).model_dump_json(exclude_none=True),
                    source,
                    expires_at.isoformat() if expires_at else None,
                    now.isoformat(),
                    preference_id,
                ),
            )
        return self.get_preference(preference_id)

    def delete_preference(self, preference_id: str) -> bool:
        with self.connect() as connection:
            connection.execute("DELETE FROM preference_evidence WHERE preference_id = ?", (preference_id,))
            result = connection.execute("DELETE FROM preferences WHERE id = ?", (preference_id,))
        return result.rowcount > 0

    def mark_preference_used(self, preference_id: str, now: datetime) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE preferences SET last_used_at = ? WHERE id = ? AND confirmed = 1",
                (now.isoformat(), preference_id),
            )

    def reset_learned_preferences(self) -> int:
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM preference_evidence
                WHERE preference_id IN (
                    SELECT id FROM preferences WHERE source IN ('learned', 'user_correction')
                )
                """
            )
            result = connection.execute(
                "DELETE FROM preferences WHERE source IN ('learned', 'user_correction')"
            )
        return result.rowcount

    def record_preference_correction(
        self,
        *,
        request_id: str,
        session_id: str,
        context: str,
        requested_intent: str,
        correction_text: str,
        preferred_result: PreferenceTargets,
        now: datetime,
    ) -> PreferenceRecord:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM preferences
                WHERE context = ? AND requested_intent = ?
                  AND source IN ('user_correction', 'learned')
                ORDER BY updated_at DESC LIMIT 1
                """,
                (context, requested_intent),
            ).fetchone()
            if row is None:
                preference_id = str(uuid4())
                observation_count = 1
                connection.execute(
                    """
                    INSERT INTO preferences (
                        id, context, requested_intent, preferred_result_json, source,
                        confidence, observation_count, confirmed, expires_at,
                        created_at, updated_at, last_used_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL, ?, ?, NULL)
                    """,
                    (
                        preference_id, context, requested_intent,
                        preferred_result.model_dump_json(exclude_none=True), "user_correction",
                        0.85, observation_count, now.isoformat(), now.isoformat(),
                    ),
                )
            else:
                preference_id = row["id"]
                observation_count = int(row["observation_count"]) + 1
                source = "user_correction"
                confidence = min(0.98, 0.8 + observation_count * 0.05)
                connection.execute(
                    """
                    UPDATE preferences
                    SET preferred_result_json = ?, source = ?, confidence = ?,
                        observation_count = ?, confirmed = 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        preferred_result.model_dump_json(exclude_none=True), source,
                        confidence, observation_count, now.isoformat(), preference_id,
                    ),
                )
            connection.execute(
                """
                INSERT INTO preference_evidence (
                    id, preference_id, request_id, session_id, correction_text,
                    preferred_result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()), preference_id, request_id, session_id, correction_text,
                    preferred_result.model_dump_json(exclude_none=True), now.isoformat(),
                ),
            )
        return self.get_preference(preference_id)

    def history(
        self,
        metric: str,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[HistoryPoint]:
        column, unit = METRICS[metric]
        clauses: list[str] = []
        parameters: list[Any] = []
        if start:
            clauses.append("timestamp >= ?")
            parameters.append(start.isoformat())
        if end:
            clauses.append("timestamp <= ?")
            parameters.append(end.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT timestamp, {column} AS value
                FROM sensor_samples
                {where}
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [
            HistoryPoint(timestamp=datetime.fromisoformat(row["timestamp"]), value=row["value"], unit=unit)
            for row in reversed(rows)
        ]


def snapshot_row(snapshot: RoomSnapshot) -> dict[str, Any]:
    return {
        "timestamp": snapshot.timestamp.isoformat(),
        "version": snapshot.version,
        "temperature_c": snapshot.environment.temperature_c,
        "humidity_percent": snapshot.environment.humidity_percent,
        "co2_ppm": snapshot.environment.co2_ppm,
        "pm25_ug_m3": snapshot.environment.pm25_ug_m3,
        "ambient_light_lux": snapshot.environment.ambient_light_lux,
        "noise_db": snapshot.environment.noise_db,
        "room_present": int(snapshot.occupancy.room_present),
        "bed_occupied": int(snapshot.occupancy.bed_occupied),
        "desk_occupied": int(snapshot.occupancy.desk_occupied),
        "window_state": snapshot.openings.window_state,
        "curtain_position_percent": snapshot.openings.curtain_position_percent,
        "computer_power_watts": snapshot.power.computer_power_watts,
        "inferred_context": snapshot.inferred_context,
        "ac_temperature_c": snapshot.devices.ac.temperature_c,
        "fan_speed": snapshot.devices.fan.speed,
        "main_light_brightness_percent": snapshot.devices.main_light.brightness_percent,
        "air_purifier_speed": snapshot.devices.air_purifier.speed,
    }


def preference_from_row(row: sqlite3.Row) -> PreferenceRecord:
    return PreferenceRecord(
        id=row["id"],
        context=row["context"],
        requested_intent=row["requested_intent"],
        preferred_result=PreferenceTargets.model_validate_json(row["preferred_result_json"]),
        source=row["source"],
        confidence=row["confidence"],
        observation_count=row["observation_count"],
        confirmed=bool(row["confirmed"]),
        expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        last_used_at=datetime.fromisoformat(row["last_used_at"]) if row["last_used_at"] else None,
    )


def write_generated_csv(output_dir: Path, snapshots: list[RoomSnapshot]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "sensor_history.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SENSOR_COLUMNS)
        writer.writeheader()
        writer.writerows(snapshot_row(snapshot) for snapshot in snapshots)

    with (output_dir / "device_history.csv").open("w", newline="", encoding="utf-8") as file:
        fieldnames = ["timestamp", "device_id", "property", "previous_value", "new_value", "source", "reason"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        initial = snapshots[0]
        for device_id, values in initial.devices.model_dump(mode="json").items():
            for property_name, value in values.items():
                writer.writerow(
                    {
                        "timestamp": initial.timestamp.isoformat(),
                        "device_id": device_id,
                        "property": property_name,
                        "previous_value": "",
                        "new_value": json.dumps(value, ensure_ascii=False),
                        "source": "baseline",
                        "reason": "Trạng thái đầu bộ dữ liệu",
                    }
                )
