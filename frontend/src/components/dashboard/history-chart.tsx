"use client";

import { useEffect, useMemo, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

import { readJson } from "@/lib/api";
import type { HistoryResponse } from "@/types/simulation";

const metrics = [
  ["temperature_c", "Nhiệt độ"],
  ["humidity_percent", "Độ ẩm"],
  ["co2_ppm", "CO₂"],
  ["pm25_ug_m3", "PM2.5"],
  ["ambient_light_lux", "Ánh sáng"],
  ["noise_db", "Tiếng ồn"],
  ["ac_temperature_c", "Mức đặt AC"],
  ["fan_speed", "Tốc độ quạt"],
] as const;

type Metric = (typeof metrics)[number][0];

export function HistoryChart({ metric, refreshKey }: { metric: Metric; refreshKey: number }) {
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [error, setError] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  useEffect(() => {
    readJson<HistoryResponse>(`/api/history?metric=${metric}&limit=1440`)
      .then((data) => {
        setHistory(data);
        setError(false);
      })
      .catch(() => setError(true));
  }, [metric, refreshKey]);

  const chart = useMemo(() => {
    const rawPoints = history?.points ?? [];
    if (!rawPoints.length) return null;
    const bucketSize = Math.max(1, Math.ceil(rawPoints.length / 288));
    const points = Array.from({ length: Math.ceil(rawPoints.length / bucketSize) }, (_, index) => {
      const bucket = rawPoints.slice(index * bucketSize, (index + 1) * bucketSize);
      return {
        ...bucket.at(-1)!,
        value: bucket.reduce((sum, point) => sum + point.value, 0) / bucket.length,
      };
    });
    const values = points.map((point) => point.value);
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const range = maximum - minimum || 1;
    const plotPoints = points.map((point, index) => {
        const x = 28 + (index / Math.max(1, points.length - 1)) * 744;
        const y = 208 - ((point.value - minimum) / range) * 172;
        return { ...point, x, y };
      });
    const path = plotPoints
      .map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`)
      .join(" ");
    return { plotPoints, values, minimum, maximum, path, unit: points.at(-1)?.unit ?? "" };
  }, [history]);

  const hovered = chart && hoveredIndex !== null ? chart.plotPoints[hoveredIndex] : null;

  function selectFromPointer(event: ReactPointerEvent<SVGRectElement>) {
    if (!chart) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    setHoveredIndex(Math.round(ratio * (chart.plotPoints.length - 1)));
  }

  return (
    <article className="chart-card">
      <div className="chart-header">
        <div>
          <p className="eyebrow">24 GIỜ GẦN NHẤT</p>
          <h2>{metrics.find(([value]) => value === metric)?.[1]}</h2>
        </div>
      </div>

      {error ? <p className="error">Không thể tải dữ liệu lịch sử.</p> : null}
      {chart ? (
        <>
          <svg className="history-chart" role="img" aria-labelledby={`${metric}-chart-title ${metric}-chart-description`} viewBox="0 0 800 240">
            <title id={`${metric}-chart-title`}>Biểu đồ {metrics.find(([value]) => value === metric)?.[1]}</title>
            <desc id={`${metric}-chart-description`}>Từ {chart.minimum.toFixed(1)} đến {chart.maximum.toFixed(1)} {chart.unit}.</desc>
            {[36, 79, 122, 165, 208].map((y) => <line key={y} x1="28" x2="772" y1={y} y2={y} />)}
            <path className="chart-area" d={`${chart.path} L772,208 L28,208 Z`} />
            <path className="chart-line" d={chart.path} />
            {hovered ? (
              <g className="chart-tooltip" pointerEvents="none">
                <line x1={hovered.x} x2={hovered.x} y1="24" y2="208" />
                <circle cx={hovered.x} cy={hovered.y} r="7" />
                <g transform={`translate(${Math.max(34, Math.min(626, hovered.x - 73))} ${Math.max(8, hovered.y - 70)})`}>
                  <rect width="146" height="52" rx="9" />
                  <text x="12" y="20">{new Date(hovered.timestamp).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</text>
                  <text className="chart-tooltip-value" x="12" y="40">{hovered.value.toFixed(1)} {chart.unit}</text>
                </g>
              </g>
            ) : null}
            <rect
              aria-label="Di chuột hoặc dùng phím mũi tên để xem dữ liệu theo giờ"
              aria-valuemax={chart.plotPoints.length - 1}
              aria-valuemin={0}
              aria-valuenow={hoveredIndex ?? chart.plotPoints.length - 1}
              aria-valuetext={hovered ? `${new Date(hovered.timestamp).toLocaleString("vi-VN")}: ${hovered.value.toFixed(1)} ${chart.unit}` : "Mốc mới nhất"}
              className="chart-hit-area"
              height="200"
              onBlur={() => setHoveredIndex(null)}
              onFocus={() => setHoveredIndex(chart.plotPoints.length - 1)}
              onKeyDown={(event) => {
                if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
                event.preventDefault();
                const direction = event.key === "ArrowLeft" ? -1 : 1;
                setHoveredIndex((current) => Math.max(0, Math.min(chart.plotPoints.length - 1, (current ?? chart.plotPoints.length - 1) + direction)));
              }}
              onPointerLeave={() => setHoveredIndex(null)}
              onPointerMove={selectFromPointer}
              role="slider"
              tabIndex={0}
              width="744"
              x="28"
              y="20"
            />
          </svg>
          <div className="chart-summary">
            <span>Thấp nhất <strong>{chart.minimum.toFixed(1)} {chart.unit}</strong></span>
            <span>Cao nhất <strong>{chart.maximum.toFixed(1)} {chart.unit}</strong></span>
            <span>Mới nhất <strong>{chart.values.at(-1)?.toFixed(1)} {chart.unit}</strong></span>
          </div>
        </>
      ) : <p className="loading-inline">Đang tải lịch sử…</p>}
    </article>
  );
}
