"use client";

import { FormEvent, useState } from "react";

import { useBrowserVoice } from "@/hooks/use-browser-voice";
import type { AssistantTraceEvent } from "@/types/assistant";

const demoSteps = [
  {
    title: "Thoải mái",
    command: "Phòng hơi nóng, làm mát hơn một chút.",
    outcome: "LLM đọc sensor, chọn thay đổi nhỏ và guardrail giới hạn mức làm lạnh.",
  },
  {
    title: "Không khí",
    command: "CO₂ đang cao, hãy giúp phòng thoáng hơn.",
    outcome: "Trợ lý phân biệt CO₂ với PM2.5 và không tuyên bố máy lọc khí loại bỏ CO₂.",
  },
  {
    title: "Ra ngoài",
    command: "Tôi chuẩn bị đi chơi, tắt hết thiết bị điện.",
    outcome: "Thiết bị điện và ổ cắm tắt; rèm, cửa sổ không bị đổi ngoài yêu cầu.",
  },
  {
    title: "Ghi nhớ",
    command: "Hãy nhớ khi làm việc tôi thích đèn ở mức 70 phần trăm.",
    outcome: "Preference được lưu và có hiệu lực ngay cho những yêu cầu phù hợp sau đó.",
  },
];

interface AssistantPanelProps {
  configured: boolean;
  model: string;
  busy: boolean;
  requestId: string;
  traces: AssistantTraceEvent[];
  responseText: string;
  onSubmit: (text: string, source?: "text" | "voice") => Promise<void>;
}

export function AssistantPanel({
  configured,
  model,
  busy,
  requestId,
  traces,
  responseText,
  onSubmit,
}: AssistantPanelProps) {
  const [selectedDemo, setSelectedDemo] = useState(0);
  const [text, setText] = useState(demoSteps[0].command);
  const voice = useBrowserVoice({
    busy: busy || !configured,
    responseText,
    onCommand: (transcript) => onSubmit(transcript, "voice"),
    onTranscript: setText,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = text.trim();
    if (trimmed) void onSubmit(trimmed, "text");
  }

  return (
    <section className="assistant-panel" aria-labelledby="assistant-title">
      <header>
        <div className="assistant-orb" aria-hidden="true"><span /></div>
        <div>
          <p className="eyebrow">OPENAI RESPONSES · {model || "CHƯA CẤU HÌNH"}</p>
          <h2 id="assistant-title">Yêu cầu và hành động</h2>
        </div>
      </header>

      {!configured ? (
        <div className="setup-warning" role="status">
          <strong>Thiếu OpenAI API key</strong>
          <span>Sao chép `.env.example` thành `.env`, đặt `OPENAI_API_KEY`, rồi khởi động lại API.</span>
        </div>
      ) : null}

      <section className="guided-demo" aria-labelledby="guided-demo-title">
        <header>
          <div><p className="eyebrow">DEMO NHANH</p><h3 id="guided-demo-title">Thử luồng hoàn chỉnh</h3></div>
          <span>{selectedDemo + 1}/{demoSteps.length}</span>
        </header>
        <div className="guided-demo-steps">
          {demoSteps.map((step, index) => (
            <button
              aria-pressed={selectedDemo === index}
              className={selectedDemo === index ? "selected" : ""}
              disabled={!configured || busy}
              key={step.title}
              onClick={() => { setSelectedDemo(index); setText(step.command); }}
              type="button"
            >
              <span>{index + 1}</span><strong>{step.title}</strong>
            </button>
          ))}
        </div>
        <p>{demoSteps[selectedDemo].outcome}</p>
      </section>

      <section className={`voice-console ${voice.status}`} aria-label="Điều khiển giọng nói">
        <div className="voice-status" role="status">
          <span aria-hidden="true" />
          <div>
            <strong>{voiceStatusLabel(voice.status, voice.mode)}</strong>
            <small>{voice.wakeEnabled
              ? "Đang chờ câu “Hey FlatMate” khi rảnh"
              : voice.mode === "browser"
                ? "Web Speech API xử lý giọng nói; dữ liệu hỗ trợ tùy trình duyệt"
                : "Localhost dùng faster-whisper và TTS ngoại tuyến"}</small>
          </div>
        </div>
        <div className="voice-actions">
          <button
            aria-pressed={voice.status === "listening"}
            className={voice.status === "listening" ? "voice-primary selected" : "voice-primary"}
            disabled={!configured || busy || !voice.supported || voice.status === "transcribing"}
            onClick={voice.toggleCommand}
            type="button"
          >
            {voice.status === "listening" ? "Tắt mic và gửi" : voice.status === "transcribing" ? "Đang nhận dạng…" : "Bật mic để nói"}
          </button>
          {voice.status === "waiting_wake" ? (
            <button onClick={voice.stopListening} type="button">Dừng nghe</button>
          ) : null}
          <button
            aria-pressed={voice.wakeEnabled}
            disabled={!configured || busy || !voice.wakeSupported || voice.status === "transcribing"}
            onClick={voice.toggleWake}
            type="button"
          >
            Wake word: {voice.wakeEnabled ? "Bật" : "Tắt"}
          </button>
        </div>
        {!voice.supported ? <p className="voice-error">{voice.mode === "browser"
          ? "Trình duyệt không hỗ trợ SpeechRecognition. Hãy dùng Chrome/Edge trên HTTPS hoặc tiếp tục nhập chữ."
          : "Trình duyệt không hỗ trợ thu âm. Hãy dùng trình duyệt hiện đại trên localhost hoặc HTTPS, hoặc tiếp tục nhập chữ."}</p> : null}
        {voice.error ? <p className="voice-error">{voice.error}</p> : null}
      </section>

      <form onSubmit={submit}>
        <label htmlFor="assistant-request">Yêu cầu tiếng Việt</label>
        <textarea
          disabled={!configured || busy}
          id="assistant-request"
          maxLength={2000}
          onChange={(event) => setText(event.target.value)}
          rows={3}
          value={text}
        />
        <button className="assistant-submit" disabled={!configured || busy || !text.trim()} type="submit">
          {busy ? "Đang xử lý…" : "Gửi yêu cầu"}
        </button>
      </form>

      {requestId ? <small className="request-id">Request {requestId.slice(0, 8)}</small> : null}

      <div className="trace-list" aria-live="polite">
        {traces.length ? traces.map((trace) => <TraceCard key={trace.id} trace={trace} />) : (
          <p className="trace-empty">Các bước quan sát được sẽ xuất hiện tại đây. Hệ thống không hiển thị suy luận nội bộ của mô hình.</p>
        )}
      </div>

      {responseText ? (
        <div className="assistant-answer">
          <span>Phản hồi cuối</span>
          <strong>{responseText}</strong>
          <div className="speech-actions">
            <button aria-pressed={voice.autoSpeak} onClick={() => voice.setAutoSpeak(!voice.autoSpeak)} type="button">
              Tự đọc: {voice.autoSpeak ? "Bật" : "Tắt"}
            </button>
            <button disabled={voice.synthesizing || !voice.speechSupported} onClick={() => void voice.speak(responseText)} type="button">
              {voice.synthesizing ? "Đang tạo giọng…" : "Đọc phản hồi"}
            </button>
            {(voice.speaking || voice.synthesizing) ? <button onClick={voice.stopSpeaking} type="button">Dừng đọc</button> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function voiceStatusLabel(
  status: "idle" | "listening" | "transcribing" | "waiting_wake" | "unsupported",
  mode: "browser" | "local",
) {
  if (status === "listening") return mode === "browser" ? "Trình duyệt đang nghe tiếng Việt" : "Đang thu âm tiếng Việt";
  if (status === "transcribing") return mode === "browser" ? "Đang gửi transcript" : "Đang nhận dạng bằng faster-whisper";
  if (status === "waiting_wake") return "Đang chờ Hey FlatMate";
  if (status === "unsupported") return "Voice không khả dụng";
  return "Voice sẵn sàng";
}

function TraceCard({ trace }: { trace: AssistantTraceEvent }) {
  return (
    <article className={`trace-card ${trace.status}`}>
      <div className="trace-marker" aria-hidden="true" />
      <div>
        <header>
          <strong>{trace.title_vi}</strong>
          <span>{trace.duration_ms === null ? trace.status : `${trace.duration_ms} ms`}</span>
        </header>
        {trace.summary_vi ? <p>{trace.summary_vi}</p> : null}
        {trace.error ? <p className="trace-error">{trace.error.message}</p> : null}
        {Object.keys(trace.data).length ? (
          <details>
            <summary>Dữ liệu quan sát</summary>
            <pre>{JSON.stringify(trace.data, null, 2)}</pre>
          </details>
        ) : null}
      </div>
    </article>
  );
}
