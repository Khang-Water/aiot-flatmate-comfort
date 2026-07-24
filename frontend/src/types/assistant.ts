export type TraceStatus = "started" | "completed" | "failed" | "skipped";

export interface AssistantTraceEvent {
  id: string;
  request_id: string;
  sequence: number;
  timestamp: string;
  duration_ms: number | null;
  stage: string;
  status: TraceStatus;
  title_vi: string;
  summary_vi: string;
  data: Record<string, unknown>;
  error: { code: string; message: string } | null;
}

export interface AssistantAccepted {
  request_id: string;
  status: "accepted";
}

export interface HealthResponse {
  openai_configured: boolean;
  openai_model: string;
}
