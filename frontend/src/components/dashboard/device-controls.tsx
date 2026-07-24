"use client";

import { booleanLabel } from "@/lib/labels";
import type { RoomSnapshot } from "@/types/room";

interface DeviceControlsProps {
  snapshot: RoomSnapshot;
  busy: boolean;
  commandDevice: (deviceId: string, values: Record<string, unknown>) => Promise<void>;
}

function RangeControl({
  id,
  label,
  value,
  minimum,
  maximum,
  suffix,
  disabled,
  onCommit,
}: {
  id: string;
  label: string;
  value: number;
  minimum: number;
  maximum: number;
  suffix: string;
  disabled: boolean;
  onCommit: (value: number) => void;
}) {
  return (
    <label className="range-control" htmlFor={id}>
      <span>{label}<strong>{value}{suffix}</strong></span>
      <input
        defaultValue={value}
        disabled={disabled}
        id={id}
        key={`${id}-${value}`}
        max={maximum}
        min={minimum}
        onPointerUp={(event) => onCommit(Number(event.currentTarget.value))}
        onKeyUp={(event) => {
          if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            onCommit(Number(event.currentTarget.value));
          }
        }}
        type="range"
      />
    </label>
  );
}

export function DeviceControls({ snapshot, busy, commandDevice }: DeviceControlsProps) {
  const devices = snapshot.devices;

  return (
    <section className="device-section" aria-labelledby="device-controls-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">THIẾT BỊ TRONG NHÀ</p>
          <h2 id="device-controls-title">Điều khiển tại một nơi</h2>
        </div>
        <span>Thay đổi được cập nhật ngay trên căn hộ 3D và bảng số liệu.</span>
      </div>

      <div className="device-grid">
        <article className="device-card">
          <header><strong>Điều hòa</strong><span className={devices.ac.power ? "device-on" : "device-off"}>{booleanLabel(devices.ac.power)}</span></header>
          <p>{devices.ac.mode} · quạt {devices.ac.fan_mode}</p>
          <div className="button-row">
            <button disabled={busy} onClick={() => commandDevice("ac", { power: !devices.ac.power })}>{devices.ac.power ? "Tắt" : "Bật"}</button>
            <button disabled={busy || devices.ac.temperature_c <= 18} onClick={() => commandDevice("ac", { temperature_c: devices.ac.temperature_c - 1 })}>−</button>
            <strong>{devices.ac.temperature_c}°C</strong>
            <button disabled={busy || devices.ac.temperature_c >= 30} onClick={() => commandDevice("ac", { temperature_c: devices.ac.temperature_c + 1 })}>+</button>
          </div>
        </article>

        <article className="device-card">
          <header><strong>Quạt</strong><span className={devices.fan.power ? "device-on" : "device-off"}>{booleanLabel(devices.fan.power)}</span></header>
          <p>Dao động {devices.fan.oscillation ? "bật" : "tắt"}</p>
          <div className="level-buttons" aria-label="Tốc độ quạt">
            {[0, 1, 2, 3].map((speed) => <button className={devices.fan.speed === speed ? "selected" : ""} disabled={busy} key={speed} onClick={() => commandDevice("fan", { speed })}>{speed}</button>)}
          </div>
        </article>

        <article className="device-card">
          <header><strong>Đèn chính</strong><span className={devices.main_light.power ? "device-on" : "device-off"}>{booleanLabel(devices.main_light.power)}</span></header>
          <RangeControl id="main-light" label="Độ sáng" value={devices.main_light.brightness_percent} minimum={0} maximum={100} suffix="%" disabled={busy} onCommit={(value) => commandDevice("main_light", { brightness_percent: value })} />
          <RangeControl id="main-light-temp" label="Màu sáng" value={devices.main_light.color_temperature_kelvin} minimum={2700} maximum={6500} suffix="K" disabled={busy} onCommit={(value) => commandDevice("main_light", { color_temperature_kelvin: value })} />
        </article>

        <article className="device-card">
          <header><strong>Đèn đầu giường</strong><span className={devices.bedside_light.power ? "device-on" : "device-off"}>{booleanLabel(devices.bedside_light.power)}</span></header>
          <RangeControl id="bed-light" label="Độ sáng" value={devices.bedside_light.brightness_percent} minimum={0} maximum={100} suffix="%" disabled={busy} onCommit={(value) => commandDevice("bedside_light", { brightness_percent: value })} />
          <RangeControl id="bed-light-temp" label="Màu sáng" value={devices.bedside_light.color_temperature_kelvin} minimum={2700} maximum={6500} suffix="K" disabled={busy} onCommit={(value) => commandDevice("bedside_light", { color_temperature_kelvin: value })} />
        </article>

        <article className="device-card">
          <header><strong>Máy lọc không khí</strong><span className={devices.air_purifier.power ? "device-on" : "device-off"}>{booleanLabel(devices.air_purifier.power)}</span></header>
          <p>PM2.5 hiện tại {snapshot.environment.pm25_ug_m3.toFixed(1)} µg/m³</p>
          <div className="level-buttons" aria-label="Tốc độ máy lọc">
            {[0, 1, 2, 3].map((speed) => <button className={devices.air_purifier.speed === speed ? "selected" : ""} disabled={busy} key={speed} onClick={() => commandDevice("air_purifier", { speed })}>{speed}</button>)}
          </div>
        </article>

        <article className="device-card">
          <header><strong>Rèm cửa</strong><span className="device-on">{devices.curtain.position_percent}%</span></header>
          <p>Cửa sổ {snapshot.openings.window_state === "open" ? "đang mở" : "đang đóng"}</p>
          <button disabled={busy} onClick={() => commandDevice("window", { state: snapshot.openings.window_state === "open" ? "closed" : "open" })}>
            {snapshot.openings.window_state === "open" ? "Đóng cửa sổ" : "Mở cửa sổ"}
          </button>
          <RangeControl id="curtain" label="Độ mở" value={devices.curtain.position_percent} minimum={0} maximum={100} suffix="%" disabled={busy} onCommit={(value) => commandDevice("curtain", { position_percent: value })} />
        </article>

        <article className="device-card">
          <header><strong>Điều khiển độ ẩm</strong><span className={devices.humidity_device.power ? "device-on" : "device-off"}>{booleanLabel(devices.humidity_device.power)}</span></header>
          <p>{devices.humidity_device.mode === "humidify" ? "Tạo ẩm" : "Hút ẩm"}</p>
          <button disabled={busy} onClick={() => commandDevice("humidity_device", { power: !devices.humidity_device.power })}>{devices.humidity_device.power ? "Tắt" : "Bật"}</button>
          <RangeControl id="humidity-target" label="Mục tiêu" value={devices.humidity_device.target_humidity_percent} minimum={35} maximum={70} suffix="%" disabled={busy} onCommit={(value) => commandDevice("humidity_device", { target_humidity_percent: value })} />
        </article>

        <article className="device-card">
          <header><strong>Ổ cắm thông minh</strong><span>{snapshot.power.computer_power_watts.toFixed(0)} W</span></header>
          {Object.entries(snapshot.power.smart_plugs).map(([id, plug]) => (
            <div className="plug-row" key={id}>
              <span>{id === "desk_computer" ? "Máy tính" : "Màn hình"} · {plug.power_watts.toFixed(0)} W</span>
              <button disabled={busy} onClick={() => commandDevice(id, { state: plug.state === "on" ? "off" : "on" })}>{plug.state === "on" ? "Tắt" : "Bật"}</button>
            </div>
          ))}
        </article>
      </div>
    </section>
  );
}
