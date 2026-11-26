# Changelog

Mục của mỗi phiên bản là ghi chú phát hành trên trang GitHub Releases.
Thêm mục `## <phiên bản>` ở đây trước khi đẩy tag `v<phiên bản>`.

## 0.1.4

- **Tự tìm giọng đọc đã cài.** Khi chưa có giọng đọc dùng được, app tự tìm VieNeu có sẵn trên máy (bản CommentKit đã cài, Python trên máy, các venv như `F:\ZAPP\F_VideoStudio\.venv`) cùng thư mục model đã tải, rồi dùng luôn, không bắt cài lại. Thanh báo có thêm nút **Tìm bản đã cài**.
- **Sửa lỗi CommentKit nằm chung nút taskbar với PlaylistKit.** Edge tự đặt ID taskbar cho cửa sổ chế độ app theo tên máy trong địa chỉ (không tính cổng), nên mọi app chạy trên `127.0.0.1` bị gộp chung một nút, và ID riêng của CommentKit bị Edge ghi đè. Giờ cửa sổ mở ở `http://commentkit.localhost:<cổng>/`, và app gán lại ID riêng `hiennv0298.CommentKit` mỗi khi Edge đổi nó.
- Sửa lỗi hai bản CommentKit cùng nghe một cổng: trên Windows, tiến trình thứ hai bind chồng lên cổng đang dùng mà không báo lỗi. Giờ app kiểm tra cổng trước, cổng bận thì dùng cổng khác.
- Từ bản này trở đi, cập nhật xong cửa sổ cũ (địa chỉ 127.0.0.1) vẫn tự tải lại được; mở lại CommentKit thì cửa sổ mới dùng địa chỉ mới.

## 0.1.3

- **Ảnh chụp thả vào cùng lúc là một bài.** Chép hoặc kéo nhiều ảnh vào thư mục inbox một lượt (cách nhau dưới 20 giây) thì tool gộp thành một video, xếp theo tên (Screenshot_1, Screenshot_2, Screenshot_10...). Trước đây mỗi ảnh lẻ thành một video riêng.
- **AI tự nhận ra ảnh nào là bài gốc**, ảnh nào là bình luận. Nếu các ảnh là những bài khác nhau, AI chọn bài hài nhất.
- **Hình trong bình luận** (meme, ảnh mèo...) giờ được cắt ra và hiện trong thẻ bình luận, như hình của bài gốc. Một ảnh chụp có nhiều hình thì tool cắt được từng hình.
- **Khoảng một nửa số câu viết kiểu Gen Z**: teencode, viết tắt ("k bt j", "nma", "cx", "r"...). Nửa còn lại viết đúng chính tả, nhất là nhân vật lớn tuổi. Giọng đọc vẫn đọc câu đầy đủ, đúng chính tả. Không dùng từ tục.
- Handle in dưới thẻ đổi thành **@Zapp-moments**.
- Xoá video và xoá video nền giờ hỏi lại bằng hộp thoại của app thay cho hộp hỏi mặc định của trình duyệt.
- Trên giao diện, chế độ "Mỗi ảnh 1 video" lưu mỗi ảnh vào một thư mục riêng nên không bị gộp. Các ảnh thả cùng lúc giữ đúng thứ tự theo tên.

## 0.1.2

- **Nút Xoá video** trên mỗi video đã làm: cả thư mục của video (video, thumbnail, kịch bản) vào Thùng rác của Windows, khôi phục lại được.
- Bản đầu tiên cập nhật được ngay trong app: từ 0.1.1, bấm **Cập nhật ngay** trên thanh báo màu vàng.
- Mở CommentKit lần nữa khi app đang chạy ẩn (`COMMENTKIT_NO_WINDOW`) không còn bật thêm cửa sổ.

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
