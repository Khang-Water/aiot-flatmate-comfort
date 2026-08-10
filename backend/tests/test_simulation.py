import random
from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.commands import apply_device_command, apply_room_scene
from app.models import RoomSceneTargets
from app.simulation import SIMULATION_START, advance_snapshot, generate_baseline, initial_snapshot


def test_baseline_generation_is_deterministic() -> None:
    first = generate_baseline(42)
    second = generate_baseline(42)

    assert len(first) == 1_440
    assert first[0] == second[0]
    assert first[-1] == second[-1]
    assert max(point.environment.co2_ppm for point in first) < 2_000
    assert max(point.environment.pm25_ug_m3 for point in first) < 30


def test_baseline_sensor_profile_varies_with_daily_routine() -> None:
    snapshots = generate_baseline(42)
    co2_values = [point.environment.co2_ppm for point in snapshots]
    high_co2_ratio = sum(value >= 1_000 for value in co2_values) / len(co2_values)

    assert initial_snapshot().environment.co2_ppm < 1_000
    assert 450 <= min(co2_values) < 700
    assert 1_020 <= max(co2_values) < 1_200
    assert 0.05 <= high_co2_ratio <= 0.2
    assert 60 <= sum(not point.occupancy.room_present for point in snapshots) <= 240
    assert 30 <= sum(point.openings.window_state == "open" for point in snapshots) <= 120
    assert {point.inferred_context for point in snapshots} == {
        "away",
        "relaxing",
        "sleeping",
        "working",
    }
    assert min(point.environment.ambient_light_lux for point in snapshots) == 0
    assert max(point.environment.ambient_light_lux for point in snapshots) > 1_500
    noise_values = [point.environment.noise_db for point in snapshots]
    assert max(noise_values) - min(noise_values) > 8


def test_runtime_schedule_does_not_lock_co2_above_warning_threshold() -> None:
    rng = random.Random(42)
    snapshot = initial_snapshot()
    last_day_co2: list[float] = []

    for minute in range(1, 3 * 24 * 60 + 1):
        snapshot = advance_snapshot(
            snapshot,
            SIMULATION_START + timedelta(minutes=minute),
            rng,
            1,
            use_schedule=True,
        )
        if minute > 2 * 24 * 60:
            last_day_co2.append(snapshot.environment.co2_ppm)

    high_co2_ratio = sum(value >= 1_000 for value in last_day_co2) / len(last_day_co2)
    assert min(last_day_co2) < 700
    assert max(last_day_co2) > 1_000
    assert high_co2_ratio < 0.5


def test_ac_moves_temperature_toward_target() -> None:
    start = initial_snapshot()
    cooled = advance_snapshot(
        start,
        SIMULATION_START + timedelta(minutes=10),
        random.Random(10),
        10,
        use_schedule=False,
    )
    ac_off, _ = apply_device_command(start, "ac", {"power": False})
    uncooled = advance_snapshot(
        ac_off,
        SIMULATION_START + timedelta(minutes=10),
        random.Random(10),
        10,
        use_schedule=False,
    )

    assert cooled.environment.temperature_c < uncooled.environment.temperature_c


def test_fan_speed_controls_power() -> None:
    snapshot = initial_snapshot()

    enabled, changes = apply_device_command(snapshot, "fan", {"speed": 2})
    disabled, _ = apply_device_command(enabled, "fan", {"speed": 0})

    assert enabled.devices.fan.power is True
    assert any(change.path == "devices.fan.power" for change in changes)
    assert disabled.devices.fan.power is False


def test_room_scene_can_turn_every_powered_device_off_and_open_window() -> None:
    snapshot = initial_snapshot()
    scene = RoomSceneTargets(
        change_mode="explicit",
        ac_power=False,
        fan_power=False,
        main_light_power=False,
        bedside_light_power=False,
        air_purifier_power=False,
        humidity_device_power=False,
        desk_computer_power=False,
        monitor_power=False,
        window_state="open",
        reason="Người dùng yêu cầu tắt thiết bị và mở cửa sổ.",
    )

    updated, changes = apply_room_scene(snapshot, scene, allow_large_changes=True)

    assert updated.devices.ac.power is False
    assert updated.devices.fan.power is False
    assert updated.devices.main_light.power is False
    assert updated.devices.bedside_light.power is False
    assert updated.devices.air_purifier.power is False
    assert updated.devices.humidity_device.power is False
    assert all(plug.state == "off" for plug in updated.power.smart_plugs.values())
    assert updated.openings.window_state == "open"
    assert any(change.path == "openings.window_state" for change in changes)


def test_scene_rejects_unsafe_ac_temperature() -> None:
    with pytest.raises(ValidationError):
        RoomSceneTargets(change_mode="explicit", ac_temperature_c=-5, reason="Giá trị nguy hiểm.")


def test_user_computer_power_override_survives_schedule_tick() -> None:
    snapshot, _ = apply_device_command(initial_snapshot(), "desk_computer", {"state": "off"})

    updated = advance_snapshot(
        snapshot,
        SIMULATION_START + timedelta(minutes=1),
        random.Random(42),
        1,
        use_schedule=True,
        use_computer_schedule=False,
    )

    assert updated.power.smart_plugs["desk_computer"].state == "off"
    assert updated.power.computer_power_watts == 0


def test_open_window_reduces_co2() -> None:
    closed = initial_snapshot()
    opened, _ = apply_device_command(closed, "window", {"state": "open"})

    assert opened.devices.ac.power is False

    closed_after = advance_snapshot(
        closed,
        SIMULATION_START + timedelta(minutes=10),
        random.Random(7),
        10,
        use_schedule=False,
    )
    opened_after = advance_snapshot(
        opened,
        SIMULATION_START + timedelta(minutes=10),
        random.Random(7),
        10,
        use_schedule=False,
    )

    assert opened_after.environment.co2_ppm < closed_after.environment.co2_ppm


def test_turning_ac_on_closes_window() -> None:
    opened, _ = apply_device_command(initial_snapshot(), "window", {"state": "open"})

    cooled, changes = apply_device_command(opened, "ac", {"power": True})

    assert cooled.devices.ac.power is True
    assert cooled.openings.window_state == "closed"
    assert any(change.path == "openings.window_state" for change in changes)


def test_scene_rejects_open_window_with_ac_on() -> None:
    with pytest.raises(ValidationError):
        RoomSceneTargets(
            change_mode="explicit",
            ac_power=True,
            window_state="open",
            reason="Hai trạng thái xung đột.",
        )
