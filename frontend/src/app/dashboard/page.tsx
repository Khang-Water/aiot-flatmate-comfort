"use client";

import { DeviceControls } from "@/components/dashboard/device-controls";
import { HistoryChart } from "@/components/dashboard/history-chart";
import { useFlatmate } from "@/hooks/use-flatmate";

function tone(value: number, good: number, warning: number): "good" | "warning" | "danger" {
  if (value <= good) return "good";
  if (value <= warning) return "warning";
  return "danger";
}

export default function Dashboard() {
  const { snapshot, simulation, connection, busy, error, commandDevice } = useFlatmate();

  const connectionLabel = {
    connecting: "Đang kết nối",
    connected: "Đang cập nhật trực tiếp",
    reconnecting: "Đang kết nối lại",
  }[connection];

  if (!snapshot || !simulation) {
    return <main><section className="loading" aria-live="polite">Đang tải bảng điều khiển…</section></main>;
  }

  const activeDevices = [
    snapshot.devices.ac.power,
    snapshot.devices.fan.power,
    snapshot.devices.main_light.power,
    snapshot.devices.bedside_light.power,
    snapshot.devices.air_purifier.power,
    snapshot.devices.humidity_device.power,
    ...Object.values(snapshot.power.smart_plugs).map((plug) => plug.state === "on"),
  ].filter(Boolean).length;

  const metrics = [
    { label: "Nhiệt độ", value: `${snapshot.environment.temperature_c.toFixed(1)}°C`, detail: `AC đặt ${snapshot.devices.ac.temperature_c}°C`, tone: tone(Math.abs(snapshot.environment.temperature_c - 25), 2, 4) },
    { label: "Độ ẩm", value: `${snapshot.environment.humidity_percent.toFixed(1)}%`, detail: "Mức dễ chịu 40–65%", tone: snapshot.environment.humidity_percent >= 40 && snapshot.environment.humidity_percent <= 65 ? "good" as const : "warning" as const },
    { label: "CO₂", value: `${snapshot.environment.co2_ppm.toFixed(0)} ppm`, detail: snapshot.environment.co2_ppm < 1000 ? "Không khí thông thoáng" : "Nên tăng thông gió", tone: tone(snapshot.environment.co2_ppm, 1000, 1500) },
    { label: "PM2.5", value: `${snapshot.environment.pm25_ug_m3.toFixed(1)} µg/m³`, detail: snapshot.environment.pm25_ug_m3 <= 15 ? "Không khí sạch" : "Kiểm tra máy lọc", tone: tone(snapshot.environment.pm25_ug_m3, 15, 35) },
    { label: "Ánh sáng", value: `${snapshot.environment.ambient_light_lux.toFixed(0)} lux`, detail: "Độ sáng trong nhà", tone: "neutral" as const },
    { label: "Tiếng ồn", value: `${snapshot.environment.noise_db.toFixed(1)} dB`, detail: snapshot.environment.noise_db < 45 ? "Không gian yên tĩnh" : "Có tiếng ồn", tone: tone(snapshot.environment.noise_db, 45, 60) },
  ];

  return (
    <main>
      <header className="dashboard-hero end-user-hero">
        <div>
          <p className="eyebrow">TỔNG QUAN CĂN HỘ</p>
          <h1>Nhà của bạn.</h1>
          <p className="lede">Theo dõi chất lượng không gian và điều khiển mọi thiết bị tại một nơi.</p>
        </div>
        <div className={`connection ${connection}`} role="status"><span aria-hidden="true" />{connectionLabel}</div>
      </header>

      {error ? <p className="error">{error}</p> : null}
      {connection === "reconnecting" ? (
        <div className="connection-warning" role="alert">
          <div><strong>Mất kết nối dữ liệu trực tiếp</strong><span>Số liệu có thể đã cũ. Hệ thống vẫn tự kết nối lại.</span></div>
          <button onClick={() => window.location.reload()} type="button">Tải lại trang</button>
        </div>
      ) : null}

      <section className="home-summary" aria-label="Tổng quan nhanh">
        <article className="summary-primary">
          <span className="summary-icon" aria-hidden="true">⌂</span>
          <div><small>Hiện diện</small><strong>{snapshot.occupancy.room_present ? "Có người ở nhà" : "Nhà đang trống"}</strong></div>
        </article>
        <article><small>Thiết bị đang bật</small><strong>{activeDevices}</strong><span>trên 8 thiết bị điện</span></article>
        <article><small>Cửa sổ</small><strong>{snapshot.openings.window_state === "open" ? "Đang mở" : "Đã đóng"}</strong><span>Rèm mở {snapshot.openings.curtain_position_percent}%</span></article>
        <article><small>Cập nhật gần nhất</small><strong>{new Date(simulation.simulated_time).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</strong><span>{new Date(simulation.simulated_time).toLocaleDateString("vi-VN")}</span></article>
      </section>

      <section className="metric-grid end-user-metrics" aria-label="Chỉ số môi trường">
        {metrics.map((metric) => (
          <article className={`metric-tile ${metric.tone}`} key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </section>

      <section className="section-heading dashboard-section-heading">
        <div><p className="eyebrow">XU HƯỚNG GẦN ĐÂY</p><h2>Môi trường thay đổi thế nào?</h2></div>
        <span>Biểu đồ cập nhật tự động từ dữ liệu mô phỏng được lưu trong SQLite.</span>
      </section>
      <section className="chart-tile-grid" aria-label="Biểu đồ môi trường">
        <HistoryChart metric="temperature_c" refreshKey={Math.floor(snapshot.version / 5)} />
        <HistoryChart metric="co2_ppm" refreshKey={Math.floor(snapshot.version / 5)} />
        <HistoryChart metric="pm25_ug_m3" refreshKey={Math.floor(snapshot.version / 5)} />
      </section>

      <DeviceControls snapshot={snapshot} busy={Boolean(busy)} commandDevice={commandDevice} />
    </main>
  );
}
