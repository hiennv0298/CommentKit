"""Mỗi lần chạy test dùng một thư mục dữ liệu trống riêng, đặt trước khi import commentkit."""
import os
import tempfile

os.environ["COMMENTKIT_HOME"] = tempfile.mkdtemp(prefix="commentkit-test-")
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)
