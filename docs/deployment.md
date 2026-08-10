# Triển khai trên Render

FlatMate Comfort dùng một Render Free Web Service để chạy frontend tĩnh và FastAPI trên cùng origin. Trình duyệt xử lý ASR bằng `SpeechRecognition`; backend tạo TTS tiếng Việt bằng Piper medium. Image không cài faster-whisper, VieNeu hoặc Supertonic.

## Thành phần triển khai

- `Dockerfile`: build frontend với browser ASR và backend TTS, rồi tạo runtime Python 3.11 chỉ có optional extra `piper`.
- `.dockerignore`: allowlist build context, loại `backend/.venv`, `frontend/node_modules`, output build và file ngoài runtime.
- `render.yaml`: bật backend TTS, tắt backend ASR, chọn `vi_VN-vais1000-medium`, giới hạn 800 ký tự mỗi request và đặt timeout mỗi lượt gọi LLM là 120 giây.
- `/app/models/vi_VN-vais1000-medium.onnx`: model 63.2 MB được bundle khi build và xác minh SHA-256.
- `/tmp/flatmate.db`: SQLite tạm thời trong instance.

## Triển khai bằng Blueprint

Mở:

<https://render.com/deploy?repo=https://github.com/Khang-Water/aiot-flatmate-comfort>

Render yêu cầu nhập các giá trị không được lưu trong repository:

```text
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
```

Nếu dùng OpenAI trực tiếp, có thể để trống `OPENAI_BASE_URL`. `OPENAI_MODEL` phải là model mà API key hiện tại có quyền sử dụng.
Blueprint đặt `OPENAI_API_MODE=chat_completions` để tương thích gateway Vilao/Gemini. Localhost giữ mặc định `responses` cho 9Router.
`OPENAI_TIMEOUT_SECONDS=120` áp dụng cho từng lượt model request; giá trị này tránh backend đóng kết nối sớm khi gateway phản hồi chậm.

## Tài nguyên

Blueprint chọn region Singapore và gói `free` với 512 MB RAM, 0.1 CPU. Browser chịu ASR; backend lazy-load Piper. Docker smoke test bị giới hạn đúng 512 MB và 0.1 CPU đo toàn service 254.3 MiB RSS, request đầu 17.12 giây và request warm 1.49 giây, không OOM.

Render Free không hỗ trợ persistent disk. Dữ liệu SQLite có thể mất sau deploy, restart hoặc thay instance; đây là giới hạn chấp nhận cho demo. Chuyển sang paid instance + disk khi cần giữ conversation, history và preference đã học.

Free service có thể spin down khi không hoạt động. Request đầu tiên sau đó phải chờ backend khởi động lại và lazy-load model; model đã nằm trong image nên không tải từ mạng lúc runtime.

## Kiểm tra sau triển khai

- Giao diện: `https://<ten-service>.onrender.com/`
- Health check: `https://<ten-service>.onrender.com/api/health`
- OpenAPI: `https://<ten-service>.onrender.com/docs`
- Dashboard: `https://<ten-service>.onrender.com/dashboard/`
- Lịch sử: `https://<ten-service>.onrender.com/history/`

Kiểm tra voice bằng Chrome hoặc Edge trên HTTPS. Nếu `SpeechRecognition` không khả dụng, giao diện báo lỗi và text input vẫn hoạt động. TTS gọi `/api/tts`, không phụ thuộc voice cài trên browser/OS. Response hợp lệ có `X-TTS-Engine: piper-1.6.0-onnx-cpu` và `X-TTS-Voice: vi_VN-vais1000-medium`.

Không lưu `OPENAI_API_KEY` trong `.env.example`, frontend, Dockerfile hoặc Git. Secret chỉ được đặt trong Render Dashboard.

Piper dùng GPL-3.0; voice repository dùng MIT và dataset VAIS-1000 dùng CC BY 4.0. Attribution nằm trong [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) và được copy vào Docker image.
