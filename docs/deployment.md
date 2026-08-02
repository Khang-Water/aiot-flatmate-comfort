# Triển khai trên Render

FlatMate Comfort dùng một Render Web Service để chạy toàn bộ frontend và backend. Docker build static export của Next.js, sau đó chép kết quả vào image FastAPI. FastAPI phục vụ giao diện và API trên cùng origin nên không cần một frontend host riêng.

## Thành phần triển khai

- `Dockerfile`: build frontend bằng Node.js và runtime backend bằng Python 3.11.
- `render.yaml`: khai báo Web Service, health check, biến môi trường và persistent disk.
- `/var/data/flatmate.db`: SQLite database.
- `/var/data/cache/huggingface`: cache faster-whisper và VieNeu.
- `/var/data/cache/supertonic3`: cache Supertonic.

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

Blueprint chọn region Singapore, gói `standard` và persistent disk 10 GB. Cấu hình này cần thiết để giữ SQLite cùng model cache và cung cấp đủ RAM cho speech inference trên CPU.

**Cảnh báo chi phí:** đây là cấu hình trả phí. Render hiển thị chi phí trước khi tạo service. Chỉ xác nhận khi đã chấp nhận mức phí.

## Kiểm tra sau triển khai

- Giao diện: `https://<ten-service>.onrender.com/`
- Health check: `https://<ten-service>.onrender.com/api/health`
- OpenAPI: `https://<ten-service>.onrender.com/docs`
- Dashboard: `https://<ten-service>.onrender.com/dashboard/`
- Lịch sử: `https://<ten-service>.onrender.com/history/`

ASR và TTS tải model ở lần sử dụng đầu tiên. Quá trình này có thể mất vài phút nhưng chỉ lặp lại khi persistent cache bị xóa.

Không lưu `OPENAI_API_KEY` trong `.env.example`, frontend, Dockerfile hoặc Git. Secret chỉ được đặt trong Render Dashboard.
