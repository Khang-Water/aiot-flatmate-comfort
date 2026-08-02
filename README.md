# FlatMate Comfort

[![Triển khai trên Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Khang-Water/aiot-flatmate-comfort)

[Đọc báo cáo kỹ thuật tiếng Việt](https://khang-water.github.io/aiot-flatmate-comfort/)

FlatMate Comfort là đồ án AIoT môn NT532, mô phỏng căn hộ thông minh một phòng ngủ có khả năng cá nhân hóa. Python sinh dữ liệu cảm biến và trạng thái thiết bị; giao diện web tiếng Việt dựng bản sao số 3D theo kích thước, nhận yêu cầu văn bản hoặc giọng nói, hiển thị các bước xử lý của trợ lý, cung cấp bảng theo dõi và quản lý sở thích người dùng.

Hệ thống không sử dụng thiết bị vật lý. MQTT, ESP32, Home Assistant, cảnh báo an toàn, xác thực và tích hợp thiết bị thật nằm ngoài phạm vi phiên bản hiện tại.

## Giao diện

### Bản sao số 3D của căn hộ

![Bản sao số 3D của căn hộ một phòng ngủ](docs/screenshots/digital-twin.png)

### Bảng theo dõi và điều khiển

![Bảng theo dõi cảm biến và thiết bị](docs/screenshots/bang-dieu-khien.png)

### Lịch sử trợ lý

![Lịch sử yêu cầu và phản hồi của trợ lý](docs/screenshots/lich-su-hoi-thoai.png)

## Trạng thái hiện tại

Sản phẩm gồm bộ máy mô phỏng tất định, lịch sử SQLite, bộ nhớ sở thích có cấu trúc, cập nhật trạng thái qua SSE, bản sao số căn hộ một phòng ngủ, lớp phủ cảm biến và thiết bị, chọn ngữ cảnh hiện diện, bảng theo dõi 24 giờ, điều khiển có quy tắc bảo vệ, thu âm bằng `MediaRecorder`, ASR tiếng Việt cục bộ bằng faster-whisper, chế độ đánh thức `Hey FlatMate`, TTS ngoại tuyến bằng VieNeu v3 Turbo với Supertonic làm phương án dự phòng, lệnh minh họa, quản lý sở thích và lịch sử hội thoại.

Thao tác không hợp lệ hoặc yêu cầu trợ lý thất bại không làm thay đổi trạng thái căn hộ. Khi chưa cấu hình `OPENAI_API_KEY`, mô phỏng, bảng theo dõi, điều khiển thủ công, ASR và TTS vẫn hoạt động.

Kết quả kiểm tra hiện tại: 44 phép kiểm thử phía máy chủ đạt, 1 phép kiểm thử phụ thuộc môi trường được bỏ qua; Ruff, kiểm tra miền dữ liệu giao diện, TypeScript và bản dựng sản xuất đều đạt.

## Công nghệ

- Giao diện: Next.js, TypeScript, CSS thích ứng và React Three Fiber.
- API: Python 3.11, FastAPI và Pydantic.
- Cập nhật trực tiếp: Server-Sent Events.
- Lưu trữ: SQLite trên đĩa bền vững.
- Dữ liệu: tệp CSV sinh tất định và kịch bản JSON.
- Nhận dạng giọng nói: `MediaRecorder` và faster-whisper `small`, CPU `int8`.
- Tổng hợp giọng nói: VietNormalizer, VieNeu v3 Turbo ONNX `int8`, giọng `Mai Anh`; Supertonic làm phương án dự phòng.
- Trợ lý: OpenAI Responses API với công cụ hàm có cấu trúc.
- Triển khai: Docker và bản thiết kế Render.

## Tài liệu

- [Báo cáo kỹ thuật hoàn chỉnh](REPORT.md)
- [Báo cáo Word](deliverables/FlatMate-Comfort-NT532-Technical-Report.docx)
- [Đề bài NT532 đã chuyển sang Markdown](docs/source/NT532-Project-Instruction.md)
- [Sơ đồ kiến trúc có thể chỉnh sửa](docs/figures/flatmate-system-architecture.drawio)
- [Ảnh sơ đồ kiến trúc](docs/figures/flatmate-system-architecture.png)
- [Đặc tả sản phẩm](docs/product-spec.md)
- [Kiến trúc hệ thống](docs/architecture.md)
- [Luồng giao diện và tương tác](docs/ui-flows.md)
- [Hợp đồng API](docs/api-contract.md)
- [Thiết kế mô phỏng](docs/simulation-design.md)
- [Các giai đoạn triển khai](docs/phases.md)
- [Hướng dẫn triển khai](docs/deployment.md)

Đề xuất phần cứng ban đầu vẫn được giữ tại [plan.md](plan.md) để tham khảo. Phạm vi mô phỏng đã duyệt trong thư mục `docs/` được ưu tiên khi có nội dung khác nhau.

Báo cáo không tự suy đoán MSSV hoặc thông tin thành viên còn thiếu. Cần bổ sung các trường này trước khi nộp.

## Chạy trên máy cá nhân

Yêu cầu: Node.js 20 trở lên, npm, Python 3.11 trở lên và `uv`.

```bash
cp .env.example .env
make install
make dev
```

Các địa chỉ mặc định:

- `http://localhost:3000`: bản sao số 3D.
- `http://localhost:3000/dashboard`: bảng theo dõi và điều khiển.
- `http://localhost:3000/history`: lịch sử trợ lý.
- `http://localhost:8000`: FastAPI.
- `http://localhost:8000/docs`: tài liệu OpenAPI.

Chạy toàn bộ kiểm tra:

```bash
make check
```

Khi `make dev` đang chạy, kiểm tra API, quy tắc bảo vệ, SSE và các trang web:

```bash
make smoke
```

## Triển khai toàn bộ trên Render

`render.yaml` tạo một dịch vụ web Render dùng Docker. Next.js được xuất thành tệp tĩnh trong bước dựng; FastAPI phục vụ giao diện, API, SSE, ASR và TTS trên cùng một tên miền. SQLite cùng bộ nhớ đệm mô hình được lưu tại đĩa bền vững `/var/data`.

### Các bước triển khai

1. Nhấn nút **Triển khai trên Render** ở đầu README.
2. Đăng nhập Render và kết nối kho mã GitHub.
3. Nhập `OPENAI_API_KEY`, `OPENAI_BASE_URL` và `OPENAI_MODEL` theo cấu hình đang hoạt động. Nếu dùng OpenAI trực tiếp, có thể để trống `OPENAI_BASE_URL`.
4. Xác nhận bản thiết kế và chờ ảnh Docker được dựng.
5. Mở URL Render được cấp; điểm kiểm tra trạng thái nằm tại `/api/health`, tài liệu OpenAPI tại `/docs`.

**Cảnh báo chi phí:** bản thiết kế dùng gói `standard` và đĩa bền vững 10 GB vì faster-whisper, VieNeu và Supertonic không phù hợp gói miễn phí. Render sẽ hiển thị chi phí trước khi tạo dịch vụ. Không xác nhận thanh toán nếu chưa chấp nhận mức phí.

Lần gọi ASR hoặc TTS đầu tiên tải mô hình xuống đĩa bền vững nên có thể chậm. Các lần sau sử dụng bộ nhớ đệm tại `/var/data/cache`.

Không đưa `OPENAI_API_KEY` vào mã nguồn, ảnh Docker hoặc biến môi trường giao diện. Khóa bí mật chỉ được nhập trong bảng điều khiển Render.
