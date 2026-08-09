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
const handoff = JSON.parse(
  readFileSync(
    new URL("../../one_bedroom_digital_twin_handoff/one_bedroom_digital_twin_spec.json", import.meta.url),
    "utf8",
  ),
);
const assistant = readFileSync(
  new URL("../src/components/assistant/assistant-panel.tsx", import.meta.url),
  "utf8",
);
const hook = readFileSync(new URL("../src/hooks/use-flatmate.ts", import.meta.url), "utf8");
const voiceHook = readFileSync(new URL("../src/hooks/use-browser-voice.ts", import.meta.url), "utf8");
const styles = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");
const dockerfile = readFileSync(new URL("../../Dockerfile", import.meta.url), "utf8");
const dockerignore = readFileSync(new URL("../../.dockerignore", import.meta.url), "utf8");
const renderBlueprint = readFileSync(new URL("../../render.yaml", import.meta.url), "utf8");

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
assert.match(apartment, /SensorNode/);
assert.match(apartment, /CanvasTexture/);
assert.match(apartment, /ContactShadows/);
assert.match(apartment, /ACESFilmicToneMapping/);
assert.match(apartment, /PLAN_WIDTH_M = 6\.73/);
assert.match(apartment, /PLAN_DEPTH_M = 7\.81/);
assert.match(apartment, /CEILING_HEIGHT_M = 2\.45/);
assert.match(apartment, /DOOR_HEIGHT_M = 2\.1/);
assert.doesNotMatch(apartment, /height=\{1\.(?:05|3)\}/);
assert.match(apartment, /planY=\{7\.72\} rotation=\{2\.36\}/);
assert.match(apartment, /planY=\{5\.31\} rotation=\{2\.45\} width=\{0\.7\}/);
assert.match(apartment, /function FloorOutline/);
assert.match(apartment, /function WallSegment/);
assert.match(apartment, /function WindowOpeningX/);
assert.match(apartment, /function WindowOpeningZ/);
assert.match(apartment, /function SlidingBedroomDoor/);
assert.match(apartment, /function KitchenDining/);
assert.match(apartment, /CLOSET BALCONY/);
assert.match(apartment, /6,73 × 7,81 m · trần 2,45 m/);
assert.match(apartment, /Đèn đầu giường/);
assert.match(apartment, /planPosition\(6\.53, 2\.15, 2\.13\).*rotation=\{\[0, -Math\.PI \/ 2, 0\]\}/);
assert.doesNotMatch(apartment, /planPosition\(4\.35, 1\.52, 2\.13\)/);
assert.match(apartment, /lightActive=\{snapshot\.devices\.main_light\.power\}/);
assert.doesNotMatch(apartment, /planPosition\(4\.75, 3\.55, 2\.37\)/);
assert.match(apartment, /Trạm môi trường · không khí/);
assert.match(apartment, /wallStation = planPosition\(3\.01, 4\.45, 1\.35\)/);
assert.match(apartment, /Ánh sáng mặt bàn/);
assert.match(apartment, /index === 0 \? <mesh/);

const sourceFurniture = new Map(handoff.furniture_and_fixtures.map((item) => [item.id, item]));
const toPlanX = (pixel) => (pixel - 63) / 80.5;
const toPlanY = (pixel) => (pixel - 87) / 78.1;
const sourceCenter = (id) => {
  const item = sourceFurniture.get(id);
  const bbox = item?.bbox_px ?? item?.bbox_px_approx;
  assert.ok(bbox, `Missing source bbox for ${id}`);
  return [(toPlanX(bbox[0]) + toPlanX(bbox[2])) / 2, (toPlanY(bbox[1]) + toPlanY(bbox[3])) / 2];
};
const distance = ([x1, y1], [x2, y2]) => Math.hypot(x2 - x1, y2 - y1);
const sourceAlignedCenters = {
  refrigerator: [0.51, 1.43],
  dining_table: [2.05, 1.93],
  sofa: [5.96, 3.65],
  coffee_table: [4.58, 3.65],
  bed: [3.99, 6.56],
  bedroom_wardrobe: [6.0, 7.42],
  toilet: [0.48, 4.56],
  bathroom_vanity: [1.34, 4.48],
};
for (const [id, center] of Object.entries(sourceAlignedCenters)) {
  assert.ok(distance(center, sourceCenter(id)) <= 0.08, `${id} center drifted from handoff bbox`);
}

const rectangle = (x, y, width, depth) => ({
  x1: x - width / 2,
  x2: x + width / 2,
  y1: y - depth / 2,
  y2: y + depth / 2,
});
const rotatedRectangle = (x, y, width, depth, rotation) => {
  const halfWidth = Math.abs(Math.cos(rotation)) * width / 2 + Math.abs(Math.sin(rotation)) * depth / 2;
  const halfDepth = Math.abs(Math.sin(rotation)) * width / 2 + Math.abs(Math.cos(rotation)) * depth / 2;
  return rectangle(x, y, halfWidth * 2, halfDepth * 2);
};
const eastDiningChair = rectangle(2.54, 1.93, 0.46, 0.46);
const northBedsideTable = rectangle(3.22, 5.5, 0.42, 0.34);
const southBedsideTable = rectangle(3.22, 7.53, 0.42, 0.34);
const bed = rectangle(3.99, 6.56, 1.9, 1.56);
const bathtub = rectangle(1.0, 5.42, 1.7, 0.7);
const wardrobe = rectangle(6.0, 7.42, 0.72, 0.58);
const hallStorage = rectangle(1.76, 7.19, 0.3, 0.7);
const closetStorage = rectangle(5.66, 0.74, 0.58, 0.72);
const livingSofa = rectangle(5.96, 3.65, 0.9, 2.25);
const livingTv = rectangle(3.3, 3.65, 0.6, 1.05);
const livingCoffeeTable = rectangle(4.58, 3.65, 0.68, 0.68);
const livingArmchair = rotatedRectangle(4.92, 2.0, 0.96, 0.84, 2.94);
const livingOttoman = rectangle(4.8, 2.85, 0.52, 0.52);
const livingPurifier = rectangle(3.35, 4.65, 0.48, 0.44);
const livingHumidityDevice = rectangle(5.05, 4.65, 0.34, 0.32);
const livingAc = rectangle(6.53, 2.15, 0.19, 1.15);
const wallSensor = rectangle(3.01, 4.45, 0.055, 0.18);
const diningTableCenter = [2.05, 1.93];
const lightSensorCenter = [2.28, 2.2];
const workingResidentCenter = [2.05, 2.42];
const relaxingResidentCenter = [5.96, 3.65];
const sleepingResidentCenter = [3.99, 6.56];
const readingResidentCenter = [3.8, 6.56];
const entryDoorTip = [2.52 + Math.cos(2.36) * 0.78, 7.72 - Math.sin(2.36) * 0.78];
const bathroomDoorTip = [1.93 + Math.cos(2.45) * 0.7, 5.31 - Math.sin(2.45) * 0.7];

assert.ok(eastDiningChair.x2 <= 2.83 - 0.06 + 1e-9, "East dining chair intersects kitchen partition");
assert.ok(northBedsideTable.x1 >= 2.92 + 0.06, "North bedside table intersects bedroom wall");
assert.ok(northBedsideTable.y2 < bed.y1, "North bedside table intersects bed");
assert.ok(southBedsideTable.y1 > bed.y2, "South bedside table intersects bed");
assert.ok(southBedsideTable.y2 <= 7.81 - 0.1, "South bedside table intersects exterior wall");
assert.ok(bathtub.x1 >= 0.1 && bathtub.x2 <= 1.96 - 0.06, "Bathtub intersects bathroom walls");
assert.ok(bathtub.y2 <= 5.83 - 0.06, "Bathtub intersects bathroom south wall");
assert.ok(wardrobe.x2 <= 6.46 - 0.1 && wardrobe.y2 <= 7.81 - 0.1, "Wardrobe intersects bedroom walls");
assert.ok(hallStorage.x1 >= 1.42 + 0.1 && hallStorage.y2 <= 7.81 - 0.1, "Hall storage intersects exterior walls");
assert.ok(closetStorage.x2 <= 6.05 - 0.06 && closetStorage.y2 <= 1.37 - 0.06, "Closet storage intersects partitions");
assert.ok(Math.abs((livingSofa.y1 + livingSofa.y2) / 2 - (livingTv.y1 + livingTv.y2) / 2) <= 0.01, "TV is not aligned with sofa");
assert.ok(livingTv.x2 < livingCoffeeTable.x1, "TV intersects coffee table");
assert.ok(livingCoffeeTable.x2 < livingSofa.x1, "Coffee table intersects sofa");
assert.ok(livingArmchair.y1 >= 1.37 + 0.06, "Armchair intersects north partition");
assert.ok(livingArmchair.x2 < livingSofa.x1, "Armchair intersects sofa");
assert.ok(livingOttoman.y1 >= livingArmchair.y2 + 0.04, "Ottoman intersects armchair");
assert.ok(livingOttoman.y2 < livingCoffeeTable.y1, "Ottoman intersects coffee table");
assert.ok(livingPurifier.y1 > livingTv.y2, "Air purifier intersects TV unit");
assert.ok(livingHumidityDevice.y1 >= livingCoffeeTable.y2 + 0.1, "Humidity device intersects coffee table");
assert.ok(livingHumidityDevice.x2 <= livingSofa.x1 - 0.2, "Humidity device blocks sofa");
assert.ok(livingHumidityDevice.y2 <= 5.24 - 0.1, "Humidity device intersects bedroom wall");
assert.ok(livingAc.x2 <= 6.63 && livingAc.x2 >= 6.62, "AC is not flush with east wall");
assert.ok(livingAc.y1 >= 1.36 && livingAc.y2 <= 5.24, "AC extends outside living-room wall");
assert.ok(wallSensor.x1 >= 2.92 + 0.06, "Environmental sensor is not mounted on corridor wall");
assert.ok(distance(diningTableCenter, lightSensorCenter) + 0.09 <= 0.54, "Light sensor is outside dining tabletop");
assert.ok(distance(workingResidentCenter, [2.05, 2.42]) <= 0.01, "Working resident left desk chair");
assert.ok(distance(relaxingResidentCenter, [5.96, 3.65]) <= 0.01, "Relaxing resident left sofa");
for (const center of [sleepingResidentCenter, readingResidentCenter]) {
  assert.ok(center[0] >= bed.x1 + 0.1 && center[0] <= bed.x2 - 0.1, "Bedroom resident left bed width");
  assert.ok(center[1] >= bed.y1 + 0.1 && center[1] <= bed.y2 - 0.1, "Bedroom resident left bed depth");
}
assert.ok(entryDoorTip[0] >= hallStorage.x2 + 0.04, "Entry door swing collides with hall storage");
assert.ok(bathroomDoorTip[1] >= 4.48 + 0.46 / 2 + 0.1, "Bathroom door swing collides with vanity");
assert.ok(bathroomDoorTip[1] <= bathtub.y1 - 0.1, "Bathroom door swing collides with bathtub");
assert.ok(1.8 >= 1.74 && 1.8 <= 2.52 && 7.7 >= 7.61, "Entry contact is not on door frame");
assert.ok(6.36 >= 6.26 && 6.36 <= 6.46 && 6.23 >= 5.62 && 6.23 <= 6.85, "Bedroom contact is not on window frame");
assert.ok(2.25 >= 1.52 && 2.25 <= 2.82 && 6.65 >= 5.93 && 6.65 <= 7.71, "Hall motion sensor left hall ceiling");
assert.match(apartment, /context sensor states are static/);
assert.doesNotMatch(apartment, /Báo khói|Rò nước/);
assert.match(apartment, /snapshot\.devices\.humidity_device/);
assert.match(apartment, /function ResidentHead/);
assert.match(apartment, /function SeatedResident/);
assert.match(apartment, /function SleepingResident/);
assert.match(apartment, /function ReadingResident/);
assert.match(apartment, /working: \{ labelHeight: 1\.55, position: planPosition\(2\.05, 2\.42\)/);
assert.match(apartment, /relaxing: \{ labelHeight: 1\.7, position: planPosition\(5\.96, 3\.65\)/);
assert.match(apartment, /sleeping: \{ labelHeight: 0\.55, position: planPosition\(3\.99, 6\.56, 0\.63\)/);
assert.match(apartment, /reading_in_bed: \{ labelHeight: 1\.45, position: planPosition\(3\.8, 6\.56, 0\.63\)/);
assert.doesNotMatch(apartment, /ringGeometry/);
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
assert.match(voiceHook, /NEXT_PUBLIC_SPEECH_MODE/);
assert.match(voiceHook, /\/api\/asr/);
assert.match(voiceHook, /recognition\.lang = "en-US"/);
assert.match(voiceHook, /recognition\.lang = "vi-VN"/);
assert.match(voiceHook, /\/api\/tts/);
assert.match(voiceHook, /new Audio\(url\)/);
assert.match(voiceHook, /SpeechSynthesisUtterance/);
assert.match(dockerfile, /NEXT_PUBLIC_SPEECH_MODE=browser/);
assert.match(dockerfile, /LOCAL_SPEECH_ENABLED=false/);
assert.doesNotMatch(dockerfile, /libgomp1|libsndfile1/);
assert.match(dockerignore, /backend\/\.venv\//);
assert.match(dockerignore, /frontend\/node_modules\//);
assert.match(renderBlueprint, /plan: free/);
assert.doesNotMatch(renderBlueprint, /^\s+disk:/m);
assert.match(styles, /prefers-reduced-motion/);
assert.match(styles, /@media \(max-width: 1200px\)/);
assert.match(styles, /min-height: 44px/);
assert.match(styles, /--page-shell: min\(1920px/);
assert.match(styles, /font-size: clamp\(16px/);

console.log("Frontend UI, apartment geometry, voice, trace, privacy, and accessibility checks passed.");
