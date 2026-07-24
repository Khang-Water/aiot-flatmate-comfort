"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import type { SensorOverlay } from "@/components/apartment/apartment-canvas";
import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { useFlatmate } from "@/hooks/use-flatmate";
import { booleanLabel } from "@/lib/labels";

const ApartmentCanvas = dynamic(
  () => import("@/components/apartment/apartment-canvas"),
  { ssr: false, loading: () => <div className="scene-loading">Đang dựng căn hộ 3D…</div> },
);

const sensorOverlays: { id: SensorOverlay; label: string }[] = [
  { id: "none", label: "Ẩn sensor" },
  { id: "temperature", label: "Nhiệt độ" },
  { id: "air", label: "Không khí" },
  { id: "light", label: "Ánh sáng" },
  { id: "noise", label: "Tiếng ồn" },
];

const contextOptions = [
  { id: "working", label: "Bàn làm việc", description: "Ngồi tại bàn và dùng máy tính", contexts: ["working"] },
  { id: "relaxing", label: "Phòng khách", description: "Ngồi tại khu vực sinh hoạt", contexts: ["relaxing"] },
  { id: "reading_in_bed", label: "Đọc trên giường", description: "Ở phòng ngủ với đèn đầu giường", contexts: ["reading_in_bed"] },
  { id: "sleeping", label: "Đang ngủ", description: "Nằm trên giường, ánh sáng thấp", contexts: ["sleeping"] },
  { id: "empty_room", label: "Ra ngoài", description: "Không còn người trong căn hộ", contexts: ["away"] },
] as const;

export default function Home() {
  const {
    snapshot,
    simulation,
    connection,
    busy,
    error,
    setContext,
    assistantConfigured,
    assistantModel,
    assistantBusy,
    assistantRequestId,
    assistantTraces,
    assistantText,
    submitAssistant,
  } = useFlatmate();
  const [overlay, setOverlay] = useState<SensorOverlay>("temperature");
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  const connectionLabel = {
    connecting: "Đang kết nối",
    connected: "Dữ liệu trực tiếp",
    reconnecting: "Đang kết nối lại",
  }[connection];

  return (
    <main>
      {error ? <p className="error">{error}</p> : null}
      {connection === "reconnecting" ? (
        <div className="connection-warning" role="alert">
          <div><strong>Mất kết nối dữ liệu trực tiếp</strong><span>Trạng thái đang hiển thị có thể đã cũ. Hệ thống vẫn tự kết nối lại.</span></div>
          <button onClick={() => window.location.reload()} type="button">Tải lại trang</button>
        </div>
      ) : null}

      {snapshot && simulation ? (
        <>
          <section className="twin-toolbar" aria-label="Lớp dữ liệu căn hộ">
            <div className="toolbar-groups">
              <div className="toolbar-group sensor-controls">
                <header><strong>Cảm biến trong nhà</strong><span>Chọn dữ liệu muốn xem trên mô hình</span></header>
                <div className="overlay-buttons">
                  {sensorOverlays.map((item) => (
                    <button className={overlay === item.id ? "selected" : ""} key={item.id} onClick={() => setOverlay(item.id)}>{item.label}</button>
                  ))}
                </div>
              </div>
              <div className="toolbar-group device-overlay-control">
                <header><strong>Thiết bị thông minh</strong><span>Xem vị trí AC, đèn, ổ cắm và thiết bị khác</span></header>
                <button className={overlay === "devices" ? "selected" : ""} onClick={() => setOverlay(overlay === "devices" ? "none" : "devices")}>
                  {overlay === "devices" ? "Ẩn vị trí thiết bị" : "Hiện vị trí thiết bị"}
                </button>
              </div>
            </div>
            <div className="twin-status">
              <div className={`connection ${connection}`} role="status">
                <span aria-hidden="true" />
                {connectionLabel}
              </div>
              <div className="twin-clock">
                <span>{simulation.running ? "Đang chạy" : "Tạm dừng"} · {simulation.speed}×</span>
                <strong>{new Date(simulation.simulated_time).toLocaleString("vi-VN")}</strong>
              </div>
            </div>
          </section>

          <section className="digital-twin-grid">
            <aside className="context-sidebar" aria-labelledby="context-options-title">
              <div>
                <p className="eyebrow">NGỮ CẢNH MÔ PHỎNG</p>
                <h2 id="context-options-title">Bạn đang ở đâu?</h2>
                <p>Chọn vị trí hoặc hoạt động để cập nhật người và căn hộ.</p>
              </div>
              <div className="context-option-list">
                {contextOptions.map((item) => {
                  const selected = item.contexts.some((context) => context === snapshot.inferred_context);
                  return (
                    <button
                      aria-pressed={selected}
                      className={selected ? "context-option selected" : "context-option"}
                      disabled={Boolean(busy)}
                      key={item.id}
                      onClick={() => setContext(item.id)}
                    >
                      <span aria-hidden="true" />
                      <strong>{item.label}</strong>
                      <small>{item.description}</small>
                    </button>
                  );
                })}
              </div>
            </aside>

            <div className="scene-card" aria-label="Mô hình căn hộ 3D tương tác">
              <ApartmentCanvas snapshot={snapshot} overlay={overlay} reducedMotion={reducedMotion} />
            </div>

            <aside className="twin-sidebar">
              <AssistantPanel
                busy={assistantBusy}
                configured={assistantConfigured}
                model={assistantModel}
                onSubmit={submitAssistant}
                requestId={assistantRequestId}
                responseText={assistantText}
                traces={assistantTraces}
              />
            </aside>
          </section>

          <section className="accessible-state" aria-labelledby="apartment-state-title">
            <div>
              <p className="eyebrow">TRẠNG THÁI TƯƠNG ĐƯƠNG KHÔNG 3D</p>
              <h2 id="apartment-state-title">Căn hộ hiện tại</h2>
            </div>
            <div className="state-table" role="table" aria-label="Trạng thái cảm biến và thiết bị">
              <div role="row"><span role="cell">Nhiệt độ</span><strong role="cell">{snapshot.environment.temperature_c.toFixed(1)}°C</strong></div>
              <div role="row"><span role="cell">Độ ẩm</span><strong role="cell">{snapshot.environment.humidity_percent.toFixed(1)}%</strong></div>
              <div role="row"><span role="cell">CO₂</span><strong role="cell">{snapshot.environment.co2_ppm.toFixed(0)} ppm</strong></div>
              <div role="row"><span role="cell">PM2.5</span><strong role="cell">{snapshot.environment.pm25_ug_m3.toFixed(1)} µg/m³</strong></div>
              <div role="row"><span role="cell">AC</span><strong role="cell">{booleanLabel(snapshot.devices.ac.power)} · {snapshot.devices.ac.temperature_c}°C</strong></div>
              <div role="row"><span role="cell">Quạt</span><strong role="cell">{booleanLabel(snapshot.devices.fan.power)} · mức {snapshot.devices.fan.speed}</strong></div>
              <div role="row"><span role="cell">Rèm</span><strong role="cell">Mở {snapshot.devices.curtain.position_percent}%</strong></div>
              <div role="row"><span role="cell">Máy lọc</span><strong role="cell">{booleanLabel(snapshot.devices.air_purifier.power)} · mức {snapshot.devices.air_purifier.speed}</strong></div>
            </div>
          </section>
        </>
      ) : (
        <section className="loading" aria-live="polite">Đang tải căn hộ số…</section>
      )}
    </main>
  );
}
