import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const home = readFileSync(new URL("../src/app/page.tsx", import.meta.url), "utf8");
const dashboard = readFileSync(new URL("../src/app/dashboard/page.tsx", import.meta.url), "utf8");
const history = readFileSync(new URL("../src/app/history/page.tsx", import.meta.url), "utf8");
const navigation = readFileSync(new URL("../src/components/navigation.tsx", import.meta.url), "utf8");
const apartment = readFileSync(
  new URL("../src/components/apartment/apartment-canvas.tsx", import.meta.url),
  "utf8",
);
const assistant = readFileSync(
  new URL("../src/components/assistant/assistant-panel.tsx", import.meta.url),
  "utf8",
);
const hook = readFileSync(new URL("../src/hooks/use-flatmate.ts", import.meta.url), "utf8");
const voiceHook = readFileSync(new URL("../src/hooks/use-browser-voice.ts", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");

assert.match(home, /TRẠNG THÁI TƯƠNG ĐƯƠNG KHÔNG 3D/);
assert.match(home, /AssistantPanel/);
assert.match(home, /Cảm biến trong nhà/);
assert.match(home, /Thiết bị thông minh/);
assert.match(home, /Bạn đang ở đâu/);
assert.match(home, /Mất kết nối dữ liệu trực tiếp/);
assert.doesNotMatch(home, /Nhìn căn hộ hiểu người/);
assert.doesNotMatch(home, /VỊ TRÍ HIỆN TẠI/);
assert.doesNotMatch(home, /Mở bảng điều khiển đầy đủ/);
assert.match(dashboard, /DeviceControls/);
assert.match(dashboard, /HistoryChart/);
assert.match(dashboard, /Số liệu có thể đã cũ/);
assert.doesNotMatch(dashboard, /scenario/i);
assert.match(history, /\/api\/conversations/);
assert.doesNotMatch(navigation, /href="\/preferences"/);
assert.match(navigation, /href="\/history"/);
assert.match(styles, /chart-tooltip/);
assert.match(apartment, /OrbitControls/);
assert.match(apartment, /ResponsiveCamera/);
assert.match(apartment, /size\.width <= 760/);
assert.match(apartment, /fallback=/);
assert.match(apartment, /WebglErrorBoundary/);
assert.match(apartment, /Tải lại mô hình/);
assert.match(apartment, /PHÒNG NGỦ/);
assert.match(apartment, /PHÒNG TẮM/);
assert.match(apartment, /SensorNode/);
assert.match(apartment, /SensorField/);
assert.match(apartment, /1 ô ≈ 1 mét/);
assert.match(apartment, /CanvasTexture/);
assert.match(apartment, /WindowPanel/);
assert.match(apartment, /ContactShadows/);
assert.match(apartment, /<Grid/);
assert.match(apartment, /ACESFilmicToneMapping/);
assert.match(apartment, /position=\{\[-0\.45, 0, 1\.85\]\} rotation=\{\[0, -Math\.PI \/ 2, 0\]\}/);
assert.match(apartment, /position=\{\[2\.42, 0, 1\.85\]\} rotation=\{\[0, -Math\.PI \/ 2, 0\]\}/);
assert.match(apartment, /<group position=\{\[0\.79, 0, -0\.04\]\}>/);
assert.match(apartment, /<Door position=\{\[2\.66, 0, 2\.6\]\} rotation=\{-Math\.PI \/ 2\}/);
assert.match(apartment, /id: "PC"/);
assert.match(apartment, /Đèn đầu giường/);
assert.match(assistant, /Hệ thống không hiển thị suy luận nội bộ/);
assert.match(assistant, /OPENAI_API_KEY/);
assert.match(assistant, /Bật mic để nói/);
assert.match(assistant, /Tắt mic và gửi/);
assert.match(assistant, /Wake word/);
assert.match(assistant, /Tự đọc/);
assert.match(assistant, /DEMO NHANH/);
assert.match(assistant, /Tôi chuẩn bị đi chơi, tắt hết thiết bị điện/);
assert.match(hook, /addEventListener\("trace"/);
assert.match(hook, /source: "text" \| "voice"/);
assert.match(hook, /trace\.request_id !== activeRequestRef\.current/);
assert.match(hook, /traceBufferRef/);
assert.match(voiceHook, /webkitSpeechRecognition/);
assert.match(voiceHook, /MediaRecorder/);
assert.match(voiceHook, /\/api\/asr/);
assert.match(voiceHook, /recognition\.lang = "en-US"/);
assert.doesNotMatch(voiceHook, /recognition\.lang = "vi-VN"/);
assert.match(voiceHook, /\/api\/tts/);
assert.match(voiceHook, /new Audio\(url\)/);
assert.doesNotMatch(voiceHook, /SpeechSynthesisUtterance/);
assert.match(styles, /prefers-reduced-motion/);
assert.match(styles, /@media \(max-width: 1200px\)/);
assert.match(styles, /min-height: 44px/);
assert.match(styles, /--page-shell: min\(1920px/);
assert.match(styles, /font-size: clamp\(16px/);

console.log("Frontend UI, voice, trace, privacy, and accessibility checks passed.");
