"use client";

import { useEffect, useRef, useState } from "react";

import { API_URL, jsonRequest } from "@/lib/api";

type VoiceStatus = "idle" | "listening" | "transcribing" | "waiting_wake" | "unsupported";

interface RecognitionResult { 0: { transcript: string } }
interface RecognitionEvent extends Event { results: ArrayLike<RecognitionResult> }
interface RecognitionErrorEvent extends Event { error: string }
interface Recognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onend: (() => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onresult: ((event: RecognitionEvent) => void) | null;
  abort(): void;
  start(): void;
  stop(): void;
}
type RecognitionConstructor = new () => Recognition;
interface VoiceWindow extends Window {
  SpeechRecognition?: RecognitionConstructor;
  webkitSpeechRecognition?: RecognitionConstructor;
}
interface TranscriptionResponse { text: string }
interface UseBrowserVoiceOptions {
  busy: boolean;
  responseText: string;
  onCommand: (text: string) => Promise<void>;
  onTranscript: (text: string) => void;
}

export function useBrowserVoice({ busy, responseText, onCommand, onTranscript }: UseBrowserVoiceOptions) {
  const [supported, setSupported] = useState(false);
  const [wakeSupported, setWakeSupported] = useState(false);
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [wakeEnabled, setWakeEnabled] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [speaking, setSpeaking] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);
  const [error, setError] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<number | null>(null);
  const recognitionRef = useRef<Recognition | null>(null);
  const wakeEnabledRef = useRef(false);
  const wakeToCommandRef = useRef(false);
  const busyRef = useRef(busy);
  const onCommandRef = useRef(onCommand);
  const onTranscriptRef = useRef(onTranscript);
  const lastSpokenRef = useRef("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef("");
  const speechRequestRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const voiceWindow = window as VoiceWindow;
    const canRecord = Boolean(navigator.mediaDevices && "MediaRecorder" in window);
    const canWake = Boolean(voiceWindow.SpeechRecognition || voiceWindow.webkitSpeechRecognition);
    setSupported(canRecord);
    setWakeSupported(canWake);
    setStatus(canRecord ? "idle" : "unsupported");
    return () => {
      wakeEnabledRef.current = false;
      recognitionRef.current?.abort();
      stopRecording(false);
      stopSpeaking();
    };
  }, []);

  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);

  useEffect(() => {
    onCommandRef.current = onCommand;
    onTranscriptRef.current = onTranscript;
  }, [onCommand, onTranscript]);

  useEffect(() => {
    if (busy || !wakeEnabled || !wakeSupported || recorderRef.current) return;
    const timer = window.setTimeout(startWake, 250);
    return () => window.clearTimeout(timer);
  }, [busy, wakeEnabled, wakeSupported]);

  useEffect(() => {
    if (!autoSpeak || !responseText || responseText === lastSpokenRef.current) return;
    lastSpokenRef.current = responseText;
    void speak(responseText);
  }, [autoSpeak, responseText]);

  function recognitionConstructor(): RecognitionConstructor | null {
    const voiceWindow = window as VoiceWindow;
    return voiceWindow.SpeechRecognition || voiceWindow.webkitSpeechRecognition || null;
  }

  function startWake() {
    const RecognitionClass = recognitionConstructor();
    if (!RecognitionClass || busyRef.current || recorderRef.current || recognitionRef.current) return;
    const recognition = new RecognitionClass();
    recognitionRef.current = recognition;
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results, (result) => result[0]?.transcript || "").join(" ");
      if (/\bhey\s+flat\s*mate\b/i.test(transcript)) {
        wakeToCommandRef.current = true;
        recognition.stop();
      }
    };
    recognition.onerror = (event) => {
      if (event.error === "aborted") return;
      setError("Wake word không hoạt động. Bạn vẫn có thể nhấn microphone để nói.");
      if (["audio-capture", "not-allowed", "service-not-allowed"].includes(event.error)) {
        wakeEnabledRef.current = false;
        setWakeEnabled(false);
      }
    };
    recognition.onend = () => {
      if (recognitionRef.current === recognition) recognitionRef.current = null;
      if (wakeToCommandRef.current) {
        wakeToCommandRef.current = false;
        void startRecording();
        return;
      }
      setStatus("idle");
      if (wakeEnabledRef.current && !busyRef.current) window.setTimeout(startWake, 300);
    };
    try {
      recognition.start();
      setStatus("waiting_wake");
    } catch {
      recognitionRef.current = null;
      setStatus("idle");
    }
  }

  async function startRecording() {
    if (!supported || busyRef.current || recorderRef.current) return;
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    setError("");
    onTranscriptRef.current("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          autoGainControl: true,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        releaseMicrophone();
        void transcribe(blob);
      };
      recorder.start(250);
      setStatus("listening");
      recordingTimerRef.current = window.setTimeout(() => stopRecording(true), 60_000);
    } catch {
      releaseMicrophone();
      setStatus("idle");
      setError("Không mở được microphone. Hãy kiểm tra quyền truy cập của trình duyệt.");
    }
  }

  function stopRecording(submit: boolean) {
    if (recordingTimerRef.current !== null) window.clearTimeout(recordingTimerRef.current);
    recordingTimerRef.current = null;
    const recorder = recorderRef.current;
    if (!recorder) return;
    if (!submit) recorder.onstop = releaseMicrophone;
    if (recorder.state !== "inactive") recorder.stop();
    else releaseMicrophone();
  }

  function releaseMicrophone() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
  }

  async function transcribe(blob: Blob) {
    if (!blob.size) {
      setStatus("idle");
      setError("Không thu được âm thanh.");
      return;
    }
    setStatus("transcribing");
    const body = new FormData();
    body.append("audio", blob, "command.webm");
    try {
      const response = await fetch(`${API_URL}/api/asr`, { method: "POST", body });
      if (!response.ok) {
        const failure = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(failure?.detail || "Không thể nhận dạng đoạn ghi âm.");
      }
      const result = await response.json() as TranscriptionResponse;
      const transcript = result.text.trim();
      if (!transcript) throw new Error("Không nhận diện được nội dung giọng nói.");
      onTranscriptRef.current(transcript);
      setStatus("idle");
      await onCommandRef.current(transcript);
    } catch (cause) {
      setStatus("idle");
      setError(cause instanceof Error ? cause.message : "Không nhận dạng được tiếng Việt.");
    }
  }

  function toggleCommand() {
    if (status === "listening") stopRecording(true);
    else {
      wakeToCommandRef.current = Boolean(recognitionRef.current);
      if (recognitionRef.current) recognitionRef.current.stop();
      else void startRecording();
    }
  }

  function stopListening() {
    wakeEnabledRef.current = false;
    setWakeEnabled(false);
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    stopRecording(false);
    setStatus("idle");
  }

  function toggleWake() {
    const enabled = !wakeEnabledRef.current;
    wakeEnabledRef.current = enabled;
    setWakeEnabled(enabled);
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    if (!enabled) setStatus("idle");
  }

  async function speak(text: string) {
    stopSpeaking();
    const controller = new AbortController();
    speechRequestRef.current = controller;
    setSynthesizing(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/tts`, { ...jsonRequest("POST", { text }), signal: controller.signal });
      if (!response.ok) {
        const failure = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(failure?.detail || "Không tạo được giọng đọc.");
      }
      const url = URL.createObjectURL(await response.blob());
      const audio = new Audio(url);
      audioRef.current = audio;
      audioUrlRef.current = url;
      audio.onended = stopSpeaking;
      audio.onerror = () => { setError("Không phát được âm thanh ngoại tuyến."); stopSpeaking(); };
      await audio.play();
      setSpeaking(true);
    } catch (speechError) {
      if (!(speechError instanceof DOMException && speechError.name === "AbortError")) {
        setError(speechError instanceof Error ? speechError.message : "Không tạo được giọng đọc ngoại tuyến.");
      }
      stopSpeaking();
    } finally {
      if (speechRequestRef.current === controller) speechRequestRef.current = null;
      setSynthesizing(false);
    }
  }

  function stopSpeaking() {
    speechRequestRef.current?.abort();
    speechRequestRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = "";
    setSpeaking(false);
  }

  return {
    autoSpeak, error, speaking, synthesizing, status, supported, wakeEnabled, wakeSupported,
    setAutoSpeak, toggleCommand, speak, stopListening, stopSpeaking, toggleWake,
  };
}
