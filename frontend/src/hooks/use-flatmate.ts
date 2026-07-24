"use client";

import { useEffect, useRef, useState } from "react";

import { API_URL, ApiError, jsonRequest, readJson } from "@/lib/api";
import type { AssistantAccepted, AssistantTraceEvent, HealthResponse } from "@/types/assistant";
import type { RoomSnapshot } from "@/types/room";
import type { SimulationStatus, StateChangedEvent } from "@/types/simulation";

export type ConnectionState = "connecting" | "connected" | "reconnecting";

export function useFlatmate() {
  const [snapshot, setSnapshot] = useState<RoomSnapshot | null>(null);
  const [simulation, setSimulation] = useState<SimulationStatus | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [assistantConfigured, setAssistantConfigured] = useState(false);
  const [assistantModel, setAssistantModel] = useState("");
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [assistantRequestId, setAssistantRequestId] = useState("");
  const [assistantTraces, setAssistantTraces] = useState<AssistantTraceEvent[]>([]);
  const [assistantText, setAssistantText] = useState("");
  const activeRequestRef = useRef("");
  const traceBufferRef = useRef(new Map<string, AssistantTraceEvent[]>());

  useEffect(() => {
    const source = new EventSource(`${API_URL}/api/events`);

    Promise.all([
      readJson<RoomSnapshot>("/api/state"),
      readJson<SimulationStatus>("/api/simulation"),
      readJson<HealthResponse>("/api/health"),
    ])
      .then(([room, status, health]) => {
        setSnapshot(room);
        setSimulation(status);
        setAssistantConfigured(health.openai_configured);
        setAssistantModel(health.openai_model);
        setError("");
      })
      .catch((cause: unknown) => setError(errorMessage(cause, "Không thể tải trạng thái căn hộ. Hãy kiểm tra API tại cổng 8000.")));

    source.onopen = () => {
      setConnection("connected");
      setError("");
    };
    source.onerror = () => setConnection("reconnecting");
    source.addEventListener("snapshot", (event) => {
      setSnapshot(JSON.parse((event as MessageEvent<string>).data) as RoomSnapshot);
    });
    source.addEventListener("state_changed", (event) => {
      const update = JSON.parse((event as MessageEvent<string>).data) as StateChangedEvent;
      setSnapshot(update.snapshot);
    });
    source.addEventListener("simulation", (event) => {
      setSimulation(JSON.parse((event as MessageEvent<string>).data) as SimulationStatus);
    });
    source.addEventListener("trace", (event) => {
      const trace = JSON.parse((event as MessageEvent<string>).data) as AssistantTraceEvent;
      const requestTraces = [...(traceBufferRef.current.get(trace.request_id) ?? []), trace].slice(-80);
      traceBufferRef.current.set(trace.request_id, requestTraces);
      if (trace.request_id !== activeRequestRef.current) return;
      setAssistantTraces(requestTraces);
      if (trace.stage === "assistant_response" && trace.status === "completed") {
        setAssistantText(String(trace.data.text ?? trace.summary_vi));
        setAssistantBusy(false);
      }
      if (trace.stage === "assistant_response" && trace.status === "failed") {
        setAssistantBusy(false);
      }
    });

    return () => source.close();
  }, []);

  async function runAction(label: string, action: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await action();
      setSnapshot(await readJson<RoomSnapshot>("/api/state"));
    } catch (cause) {
      setError(errorMessage(cause, "Thao tác mô phỏng thất bại. Kiểm tra API và thử lại."));
    } finally {
      setBusy("");
    }
  }

  function commandDevice(deviceId: string, values: Record<string, unknown>) {
    return runAction(deviceId, async () => {
      await readJson(
        `/api/devices/${deviceId}/commands`,
        jsonRequest("POST", { values, source: "manual" }),
      );
    });
  }

  function setContext(contextId: string) {
    return runAction(`context-${contextId}`, async () => {
      setSimulation(
        await readJson<SimulationStatus>(
          `/api/scenarios/${contextId}/activate`,
          jsonRequest("POST"),
        ),
      );
    });
  }

  async function submitAssistant(text: string, source: "text" | "voice" = "text") {
    setAssistantBusy(true);
    setAssistantText("");
    setAssistantTraces([]);
    activeRequestRef.current = "";
    setError("");
    try {
      const accepted = await readJson<AssistantAccepted>(
        "/api/assistant/requests",
        jsonRequest("POST", {
          text,
          source,
          session_id: getSessionId(),
        }),
      );
      activeRequestRef.current = accepted.request_id;
      setAssistantRequestId(accepted.request_id);
      const buffered = traceBufferRef.current.get(accepted.request_id) ?? [];
      setAssistantTraces(buffered);
      const finalTrace = buffered.findLast((trace) => trace.stage === "assistant_response");
      if (finalTrace?.status === "completed") {
        setAssistantText(String(finalTrace.data.text ?? finalTrace.summary_vi));
        setAssistantBusy(false);
      } else if (finalTrace?.status === "failed") {
        setAssistantBusy(false);
      }
    } catch (cause) {
      setAssistantBusy(false);
      setError(errorMessage(cause, "Không thể gửi yêu cầu tới trợ lý. Kiểm tra OPENAI_API_KEY và thử lại."));
    }
  }

  return {
    snapshot,
    simulation,
    connection,
    busy,
    error,
    commandDevice,
    setContext,
    assistantConfigured,
    assistantModel,
    assistantBusy,
    assistantRequestId,
    assistantTraces,
    assistantText,
    submitAssistant,
  };
}

function errorMessage(cause: unknown, fallback: string): string {
  return cause instanceof ApiError ? cause.message : fallback;
}

function getSessionId(): string {
  const key = "flatmate-session-id";
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const created = window.crypto.randomUUID();
  window.localStorage.setItem(key, created);
  return created;
}
