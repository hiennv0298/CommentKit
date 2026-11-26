# CommentKit

Tool tự làm YouTube Shorts "bình luận hài" từ ảnh chụp bài Threads, hoặc tự sáng tác truyện mới. Chạy trên Windows 10/11.

## Cài đặt
**Cách 1, một lệnh:** mở PowerShell, dán lệnh sau rồi Enter. Tool được cài vào `%USERPROFILE%\CommentKit`.
```powershell
irm https://raw.githubusercontent.com/hiennv0298/CommentKit/main/get.ps1 | iex
```
Muốn cài chỗ khác thì chạy `$env:COMMENTKIT_DIR = "D:\CommentKit"` trước. Chạy lại lệnh trên để cập nhật bản mới; `.env`, `config.local.json`, `inbox`, `backgrounds`, `output` được giữ nguyên.

**Cách 2, tải về:** `git clone https://github.com/hiennv0298/CommentKit.git` (hoặc tải ZIP và giải nén), rồi nhấp đúp `install.bat`.

Bộ cài tự làm các việc sau:
1. Cài Python 3.12 và ffmpeg bằng winget nếu máy chưa có.
2. Tạo `.venv` cho app và `.venv-tts` cho giọng đọc VieNeu-TTS (chạy bằng CPU, không cần GPU).
3. Tạo thư mục `inbox`, `backgrounds`, `output` và file `.env`.
4. Tạo shortcut **CommentKit** trên Desktop.
5. Dựng thử một video mẫu. Lần đầu tool tải model giọng đọc, khoảng 600 MB.

Tuỳ chọn khi chạy `install.ps1`:
- `-VieneuPython <python.exe>`: dùng lại VieNeu đã cài sẵn ở venv khác.
- `-HfHome <thư mục>`: đổi chỗ lưu model.
- `-SkipTest`: bỏ bước dựng thử.
- `-NoShortcut`: không tạo shortcut.

Ví dụ: `powershell -ExecutionPolicy Bypass -File install.ps1 -VieneuPython F:\VieNeu\.venv\Scripts\python.exe`

Sau khi cài: nhấp đúp **CommentKit** trên Desktop. Trong **Cài đặt**, chọn AI (Gemini miễn phí, ChatGPT hoặc Claude) và nhập key.

## Cách hoạt động

**Bạn làm:** lướt Threads, chụp màn hình bài hay (cả bài gốc lẫn bình luận), rồi thả ảnh vào thư mục `inbox`.
**Tool tự làm phần còn lại:**
1. Quét `inbox` (mặc định 30 giây một lần). Một ảnh lẻ thành một video, một thư mục con (nhiều ảnh của cùng một bài) cũng thành một video.
2. Claude (`claude -p`) tự đọc ảnh: viết lại bài, che tên người dùng, viết thêm bình luận hài, gán nhân vật và giọng, đặt tiêu đề, mô tả, tag. Bài nhạy cảm thì bỏ qua.
3. Nếu bài có hình hoặc meme, tool tự cắt hình đó ra khỏi ảnh chụp.
4. VieNeu-TTS đọc, mỗi nhân vật một giọng.
5. Dựng video 1080x1920: gameplay lấy ngẫu nhiên từ thư mục `backgrounds/` phủ kín màn hình, **mỗi lúc một thẻ Threads**, thẻ đổi đúng lúc giọng đọc tới câu đó.
6. Ảnh đã đọc được chuyển sang `inbox/_done/`, nên lần sau không đọc lại. Ảnh lỗi chuyển sang `inbox/_failed/`, bấm "Thử lại" trên UI để chạy lại.

Video ra ở `output/<thời gian>_<tên>/`: `video.mp4`, `video_thumb.jpg`, `script.json`, `metadata.json`.

## Tự sáng tác (không cần ảnh)
LLM tự nghĩ ra một bài Threads hư cấu và các bình luận theo chủ đề, rồi dựng video như bình thường.
- Trên UI: chọn chủ đề (hoặc để ngẫu nhiên, hoặc gõ chủ đề riêng) rồi bấm **Sáng tác**. Có thể bật "Tự sáng tác khi inbox trống", giới hạn số video mỗi ngày.
- Danh sách chủ đề nằm trong `config.json` → `compose.topics`. Các ý đã làm lưu ở `state/compose_history.json`, LLM được dặn không viết trùng.
- Mô tả video ghi "nội dung hư cấu".

## Chọn Claude, ChatGPT hay Gemini
Trong **Cài đặt** chọn riêng cho từng việc: đọc ảnh chụp và tự sáng tác.
- **Claude:** dùng Claude Code CLI đã đăng nhập.
- **ChatGPT:** dùng OpenAI API key, nhập trong Cài đặt (lưu vào `.env` là `OPENAI_API_KEY`). Model mặc định là `gpt-4o`, đổi được trong Cài đặt.
- **Gemini:** dùng Google Gemini API key, có gói miễn phí (giới hạn lượt/phút và lượt/ngày; ở gói miễn phí Google có thể dùng dữ liệu gửi lên để cải thiện sản phẩm). Lấy key ở aistudio.google.com/apikey, nhập trong Cài đặt (lưu vào `.env` là `GEMINI_API_KEY`). Model mặc định là `gemini-flash-latest`. Bị giới hạn lượt/phút thì tool tự chờ rồi thử lại; hết lượt trong ngày thì tool tự tạm dừng.
Bấm "Kiểm tra Claude", "Kiểm tra OpenAI" hoặc "Kiểm tra Gemini" để thử kết nối.

## Mở giao diện
Nhấp đúp `start-ui.bat`, trình duyệt sẽ mở http://127.0.0.1:8765. Trên giao diện bạn có thể:
- Kéo thả ảnh, hoặc dán bằng Ctrl+V. Chọn "các ảnh cùng 1 bài → 1 video" hoặc "mỗi ảnh 1 video".
- Bật/tắt chế độ tự động, bấm "Quét ngay", kiểm tra Claude đã đăng nhập chưa.
- Thêm/xoá video nền (gameplay).
- Xem video đã làm, chép tiêu đề và mô tả để đăng.
- Đổi đường dẫn thư mục inbox, nền, output (ví dụ trỏ inbox vào một thư mục Google Drive đồng bộ từ điện thoại).

Chạy không cần UI: `.venv\Scripts\python.exe run.py` (xử lý hết inbox rồi thoát), `run.py --compose "chủ đề" --provider openai` (sáng tác 1 video).

## Cần có
- **Một AI để viết kịch bản:** Gemini (key miễn phí), ChatGPT (key trả phí), hoặc Claude Code CLI đã đăng nhập (chạy `claude` rồi `/login`). Nếu AI báo lỗi key hoặc chưa đăng nhập, tool tự tạm dừng và giữ nguyên ảnh trong inbox.
- **Video nền gameplay** trong `backgrounds/`. Nên dùng gameplay bạn tự quay hoặc video ghi rõ được dùng tự do. Chưa có video nền thì tool dùng nền tối.
- VieNeu-TTS: bộ cài tự cài vào `.venv-tts`. Đường dẫn lưu trong `config.local.json` → `tts`.

## Tuỳ chỉnh (`config.json`)
Chỉnh riêng cho máy mình thì ghi vào `config.local.json`: file này đè lên `config.json` và không bị ghi đè khi cập nhật. Model OpenAI/Gemini đổi trên UI cũng được lưu vào đây.
- `channel_name`, `channel_handle`: tên kênh và handle in dưới thẻ.
- `characters`: nhân vật, giọng VieNeu và tính cách.
- `video.max_comments`, `video.target_sec`: số bình luận và độ dài video.
- `video.bgm`: đường dẫn nhạc nền (không bắt buộc).

## Ghi chú
- `src/threads_api.py` là phần tìm bài qua Threads API, đang để dành. Hiện app chưa có quyền `threads_keyword_search` nên chưa dùng được.
- Chưa có bước tự upload lên YouTube.
- Khi đăng, bật mục công bố "nội dung đã chỉnh sửa hoặc tổng hợp" vì video dùng giọng AI.
