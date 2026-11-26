# Changelog

Mục của mỗi phiên bản là ghi chú phát hành trên trang GitHub Releases.
Thêm mục `## <phiên bản>` ở đây trước khi đẩy tag `v<phiên bản>`.

## 0.1.1

- **Tự cập nhật trong app.** CommentKit kiểm tra GitHub có bản mới không khi mở app và vài tiếng một lần, rồi hiện thanh báo kèm ghi chú phát hành. Với bản cài bằng bộ cài, nút **Cập nhật ngay** tải bộ cài mới, đối chiếu mã SHA-256, cài im lặng rồi mở lại CommentKit. Cửa sổ đang mở tự tải lại vào bản mới, không mở thêm cửa sổ thứ hai.
- Cửa sổ **Có gì mới** hiện ngay sau khi cập nhật.
- Bấm số phiên bản trên thanh trên cùng (hoặc nút **Kiểm tra bản mới** trong Cài đặt) để kiểm tra ngay.
- Có thể tắt việc tự kiểm tra trong **Cài đặt**.
- Cửa sổ mất kết nối với app (app đã tắt) giờ báo rõ và có nút **Đóng cửa sổ này**.
- Bản 0.1.0 chưa có tính năng tự cập nhật: lần này cần tải `CommentKit-Setup-0.1.1.exe` cài đè lên. Dữ liệu vẫn giữ nguyên. Từ bản sau, app tự cập nhật.

## 0.1.0

Bản phát hành đầu tiên.

- **Bộ cài Windows** (`CommentKit-Setup-0.1.0.exe`, cài cho người dùng hiện tại, không cần admin) và **bản portable zip**. Có sẵn FFmpeg đi kèm.
- **Cửa sổ app** có nút taskbar riêng và icon nét ở mọi kích thước, không bị gộp chung với Edge, PlaylistKit hay ClipKit.
- **Từ ảnh chụp ra video:** thả ảnh chụp Threads vào app (kéo thả, bấm chọn hoặc Ctrl+V), hoặc chép vào thư mục inbox. AI viết lại bài, che tên người dùng, thêm bình luận hài của dàn nhân vật, viết tiêu đề, mô tả và tag YouTube. Ảnh đã đọc chuyển sang `inbox/_done` nên không bị đọc lại.
- **Tự sáng tác:** AI nghĩ ra bài và bình luận mới theo chủ đề, không cần ảnh. Có thể tự làm vài video mỗi ngày.
- **Chọn AI:** Gemini (có gói miễn phí), ChatGPT (key OpenAI) hoặc Claude Code CLI, chọn riêng cho việc đọc ảnh và việc sáng tác.
- **Giọng đọc tiếng Việt** VieNeu-TTS, mỗi nhân vật một giọng, đọc ở tốc độ 1.2. Nút **Cài giọng đọc** cài tự động khi dùng lần đầu (khoảng 1 GB, chạy bằng CPU).
- **Video:** 1080×1920, nền gameplay lấy từ thư mục của bạn. Mỗi lúc một thẻ kiểu Threads, đổi thẻ đúng nhịp giọng đọc. Hình hoặc meme của bài được tự cắt ra khỏi ảnh chụp.
