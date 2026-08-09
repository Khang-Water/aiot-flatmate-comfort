# Triển khai trên Render

FlatMate Comfort dùng một Render Free Web Service để chạy frontend tĩnh và FastAPI trên cùng origin. Speech được xử lý bởi Web Speech API trong trình duyệt; image máy chủ không cài faster-whisper, VieNeu hoặc Supertonic.

## Thành phần triển khai

- `Dockerfile`: build frontend với `NEXT_PUBLIC_SPEECH_MODE=browser`, rồi tạo runtime Python 3.11 không có optional extra `speech`.
- `.dockerignore`: allowlist build context, loại `backend/.venv`, `frontend/node_modules`, output build và file ngoài runtime.
- `render.yaml`: khai báo Render Free Web Service, health check và `LOCAL_SPEECH_ENABLED=false`.
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

## Tài nguyên

Blueprint chọn region Singapore và gói `free`. Browser chịu chi phí ASR/TTS nên backend không load model speech vào RAM.

Render Free không hỗ trợ persistent disk. Dữ liệu SQLite có thể mất sau deploy, restart hoặc thay instance; đây là giới hạn chấp nhận cho demo. Chuyển sang paid instance + disk khi cần giữ conversation, history và preference đã học.

Free service có thể spin down khi không hoạt động. Request đầu tiên sau đó phải chờ backend khởi động lại, nhưng không còn bước tải model speech.

## Kiểm tra sau triển khai

- Giao diện: `https://<ten-service>.onrender.com/`
- Health check: `https://<ten-service>.onrender.com/api/health`
- OpenAPI: `https://<ten-service>.onrender.com/docs`
- Dashboard: `https://<ten-service>.onrender.com/dashboard/`
- Lịch sử: `https://<ten-service>.onrender.com/history/`

Kiểm tra voice bằng Chrome hoặc Edge trên HTTPS. Nếu `SpeechRecognition` không khả dụng, giao diện báo lỗi và text input vẫn hoạt động. `speechSynthesis` dùng giọng Việt có sẵn trên browser/OS nên âm sắc có thể khác giữa thiết bị.

Không lưu `OPENAI_API_KEY` trong `.env.example`, frontend, Dockerfile hoặc Git. Secret chỉ được đặt trong Render Dashboard.
