# CommentKit

Tool làm YouTube Shorts "bình luận hài" trên Windows. Mỗi video đi từ ảnh chụp bài Threads, hoặc từ một truyện AI tự sáng tác. Bài đăng và bình luận hiện lần lượt từng thẻ trên nền gameplay, mỗi nhân vật có một giọng đọc AI tiếng Việt riêng.

## Cài đặt

1. Tải **`CommentKit-Setup-<phiên bản>.exe`** ở mục [Releases](https://github.com/hiennv0298/CommentKit/releases/latest) rồi chạy. Bộ cài chỉ cài cho người dùng hiện tại, không cần quyền admin, vào `%LOCALAPPDATA%\Programs\CommentKit`. Có cả bản **portable zip**: giải nén rồi chạy `CommentKitApp.exe`.
2. Mở **CommentKit** ở Start menu hoặc Desktop.
3. Nếu máy đã có VieNeu-TTS (ví dụ cài cho tool khác), CommentKit tự tìm thấy và dùng luôn. Nếu chưa có, bấm **Cài giọng đọc** trên thanh màu vàng. CommentKit tải một Python riêng và VieNeu-TTS kèm model, khoảng 1 GB, vào thư mục dữ liệu. Việc này chỉ làm một lần, mất vài phút.
4. Mở **Cài đặt**, chọn AI và nhập key:
   - **Gemini**: có gói miễn phí. Lấy key ở [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
   - **ChatGPT**: key OpenAI API còn credit.
   - **Claude**: dùng Claude Code CLI nếu máy đã cài và đăng nhập (`claude`, rồi `/login`).

   Có thể chọn AI khác nhau cho việc đọc ảnh và việc sáng tác. Bấm **Kiểm tra** để thử kết nối.
5. Thêm vài video gameplay ở mục **Video nền**. Nên dùng video tự quay hoặc video được dùng tự do. Chưa có video nền thì tool dùng nền tối.

Dữ liệu của bạn nằm ở `%LOCALAPPDATA%\CommentKit`: key (`.env`), `config.local.json`, `inbox`, `backgrounds`, `output` và giọng đọc. Cập nhật hay gỡ CommentKit không đụng tới thư mục này.

**Cập nhật:** CommentKit tự kiểm tra bản mới trên GitHub khi mở app và vài tiếng một lần. Có bản mới thì một thanh báo hiện ra. Với bản cài bằng bộ cài, bấm **Cập nhật ngay**: app tải bộ cài mới, đối chiếu mã SHA-256 trong `SHA256SUMS.txt`, cài im lặng rồi tự mở lại, cửa sổ đang mở tự chuyển sang bản mới. Bản portable thì nút này mở trang Releases để tải. Bấm số phiên bản trên thanh trên cùng để kiểm tra ngay; tắt việc tự kiểm tra trong Cài đặt. App chỉ gửi một yêu cầu tới GitHub, không gửi gì về bạn.

## Cách dùng

**Từ ảnh chụp:** lướt Threads, chụp màn hình bài hay cùng các bình luận, rồi thả ảnh vào app (kéo thả, bấm chọn, hoặc dán bằng Ctrl+V). Chọn "các ảnh cùng 1 bài → 1 video" hoặc "mỗi ảnh 1 video". Cũng có thể chép thẳng ảnh vào thư mục inbox: các ảnh chép vào cùng một lượt (cách nhau dưới 20 giây) là một bài, xếp theo tên; một thư mục con cũng là một bài. AI tự nhận ra ảnh nào là bài gốc, ảnh nào là bình luận.

Khi bật **Tự động**, CommentKit quét inbox 30 giây một lần. Với mỗi bài, tool làm các bước sau:
1. AI đọc ảnh: viết lại bài bằng lời của nó, thay mọi tên người dùng bằng tên che bịa ngẫu nhiên, viết lại các bình luận hay, thêm bình luận của riêng nó, gán mỗi câu cho một nhân vật, đặt tiêu đề, mô tả và tag. Khoảng một nửa số câu viết kiểu Gen Z (teencode, viết tắt), giọng đọc vẫn đọc câu đầy đủ. Bài nhạy cảm thì bỏ qua.
2. Nếu bài gốc hoặc bình luận có hình/meme, tool tự cắt hình đó ra khỏi ảnh chụp và gắn vào đúng thẻ.
3. VieNeu-TTS đọc từng câu bằng giọng của nhân vật đó.
4. Dựng video 1080×1920: gameplay phủ kín màn hình, mỗi lúc một thẻ, đổi thẻ đúng lúc giọng đọc tới câu đó.
5. Ảnh đã đọc chuyển sang `inbox/_done`, nên không bị đọc lại. Ảnh lỗi chuyển sang `inbox/_failed`, bấm **Thử lại** để chạy lại.

**Tự sáng tác:** chọn chủ đề (để ngẫu nhiên, hoặc gõ chủ đề riêng) rồi bấm **Sáng tác**. Tool cũng có thể tự sáng tác khi inbox trống, có giới hạn số video mỗi ngày. Các ý đã làm được ghi nhớ để không lặp lại.

Mỗi video nằm trong một thư mục riêng trong `output/`: `video.mp4`, ảnh thumbnail, `script.json` và `metadata.json`. Trên app, nút **Chép tiêu đề** và **Chép mô tả** chép sẵn chữ để đăng YouTube. Nút **Xoá** chuyển cả thư mục của video vào Thùng rác.

Đóng cửa sổ là CommentKit thoát. Nếu đang làm dở một video, tool làm xong rồi mới thoát. Chế độ tự động chỉ chạy khi cửa sổ đang mở.

## Dòng lệnh

Bộ cài có tuỳ chọn thêm `commentkit` vào PATH:

```
commentkit                     mở cửa sổ app
commentkit run                 xử lý inbox một lần rồi thoát
commentkit compose "chủ đề"    sáng tác 1 video
commentkit script X.json       dựng video từ kịch bản có sẵn
commentkit install-voices      cài giọng đọc VieNeu
commentkit doctor              kiểm tra ffmpeg, giọng đọc và key
```

`run` và `compose` nhận thêm `--provider gemini|openai|claude`.

## Tuỳ chỉnh

Ghi phần chỉnh riêng vào `config.local.json` trong thư mục dữ liệu. File này đè lên cấu hình mặc định và không bị ghi đè khi cập nhật.
- `channel_name`, `channel_handle`: tên kênh để AI viết, và handle in dưới thẻ.
- `characters`: dàn nhân vật, mỗi nhân vật có giọng VieNeu, tính cách và hiệu ứng giọng (không bắt buộc).
- `video.max_comments`, `video.target_sec`: số bình luận và độ dài video.
- `tts.speed`: tốc độ đọc (mặc định 1.2).
- `compose.topics`: danh sách chủ đề tự sáng tác.
- `video.bgm`, `video.bgm_volume`: nhạc nền (không bắt buộc).

Ví dụ:
```json
{ "channel_handle": "Zapp-moments", "tts": { "speed": 1.1 } }
```

## Đăng lên YouTube

CommentKit có thể tự đăng video vừa làm xong lên kênh của bạn, hoặc đăng từng video bằng nút **Đăng YouTube**. Tool dùng YouTube Data API dưới chính tài khoản của bạn, nên cần một OAuth client của Google Cloud. Việc này miễn phí, chỉ làm một lần, mất khoảng 5 phút.

**1. Tạo OAuth client** (dùng tài khoản Google đang sở hữu kênh):
1. Vào [console.cloud.google.com](https://console.cloud.google.com/), tạo một project mới, ví dụ `CommentKit`.
2. **APIs & Services → Library**, tìm **YouTube Data API v3**, bấm **Enable**.
3. **Google Auth Platform → Branding**: điền tên app (ví dụ `CommentKit`) và email hỗ trợ. Ở mục **Audience**, chọn **External**.
4. Vẫn trong **Audience**, bấm **Publish app** để chuyển sang *In production*. Nếu để chế độ *Testing* thì quyền đăng video hết hạn sau 7 ngày và phải kết nối lại. Hoặc giữ *Testing* và thêm email của bạn vào **Test users**.
5. **Clients → Create client → Application type: Desktop app**, đặt tên, bấm **Create**, rồi **Download JSON**. Bạn được file `client_secret_….json`.

**2. Kết nối trong CommentKit:**
1. Ở mục **YouTube**, bấm **Nạp file client_secret.json** và chọn file vừa tải.
2. Bấm **Kết nối YouTube**. Trình duyệt mở trang đăng nhập Google: chọn tài khoản và kênh, cho phép quyền đăng video. Nếu Google báo *"Google hasn't verified this app"*, bấm **Advanced → Go to CommentKit (unsafe)**. Đây là app của chính bạn tạo ở bước trên.
3. Quay lại CommentKit, mục YouTube hiện tên kênh. Chọn:
   - **Tự đăng video mới làm xong**: bật để video làm xong được đăng luôn.
   - **Chế độ hiển thị**: Riêng tư, Không công khai, Công khai, hoặc **Hẹn giờ theo khung giờ**. Hẹn giờ thì mỗi video lấy khung trống gần nhất trong danh sách, ví dụ `11:30, 20:00`, nên mỗi ngày đăng đều 2 clip.

Video đăng lên có sẵn tiêu đề, mô tả, hashtag, tag, thể loại *Hài*, ngôn ngữ tiếng Việt, *Không dành cho trẻ em*, và mục công bố **nội dung tổng hợp** (vì dùng giọng AI). Trên mỗi video trong app có link tới video đã đăng.

**Giới hạn của Google, cần biết:**
- **Project chưa qua kiểm duyệt thì video đăng qua API bị khoá ở chế độ riêng tư**, kể cả khi bạn chọn Công khai. Muốn đăng công khai hoặc hẹn giờ tự động, gửi [form kiểm duyệt YouTube API](https://support.google.com/youtube/contact/yt_api_form) (miễn phí, thường mất vài tuần). Trong lúc chờ, cứ để tool tải lên ở chế độ riêng tư rồi bạn tự bật công khai trong YouTube Studio.
- **Hạn mức mặc định khoảng 6 video/ngày** (10.000 đơn vị, mỗi lần tải lên tốn 1.600). Hết hạn mức thì tool dừng đăng, hôm sau bấm **Đăng YouTube** lại.
- File `client_secret` và quyền đăng nhập được lưu ở `%LOCALAPPDATA%\CommentKit\.youtube\`. Bấm **Ngắt kết nối** để thu hồi quyền.

## Trước khi đăng

- Bật mục công bố **nội dung đã chỉnh sửa hoặc tổng hợp** trên YouTube, vì video dùng giọng AI. Nếu đăng bằng CommentKit thì mục này đã được bật sẵn.
- Mô tả video đã ghi sẵn là nội dung dựng lại hoặc hư cấu, tên người dùng đã ẩn và giọng đọc là AI.
- Ở gói miễn phí của Gemini, Google có thể dùng dữ liệu gửi lên, kể cả ảnh chụp, để cải thiện sản phẩm.

## Chạy từ mã nguồn

```
git clone https://github.com/hiennv0298/CommentKit.git
cd CommentKit
run.cmd
```
Lần đầu chạy, `run.cmd` tạo `.venv` và cài thư viện. Khi chạy từ mã nguồn, thư mục dữ liệu chính là thư mục dự án. Máy cần có ffmpeg trong PATH (`winget install Gyan.FFmpeg`).

Đóng gói bộ cài bằng `powershell -ExecutionPolicy Bypass -File scripts\build.ps1`, cần Inno Setup 6 (`winget install JRSoftware.InnoSetup`). Đẩy tag `v*` lên GitHub thì GitHub Actions tự đóng gói và gắn vào Release. Vẽ lại icon bằng `python scripts/make_icons.py`.

## Giấy phép

MIT. VieNeu-TTS được tải về lúc cài giọng đọc, theo giấy phép riêng của nó (Apache 2.0).
