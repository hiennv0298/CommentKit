# PyInstaller spec: two programs sharing one folder (dist\CommentKit).
#   commentkit.exe     command line, runs in a console
#   CommentKitApp.exe  opens the app window, no console window
# tts_vieneu.py is shipped as a plain file: it runs in the separate VieNeu Python the app installs on first use.
# Build with: python -m PyInstaller --noconfirm --clean --distpath dist --workpath build scripts\commentkit.spec
import os

from PyInstaller.utils.hooks import collect_data_files

SRC = os.path.join(SPECPATH, "..", "src")
datas = collect_data_files("commentkit", include_py_files=False)
datas += [(os.path.join(SRC, "commentkit", "tts_vieneu.py"), "commentkit")]
hidden = ["commentkit." + m for m in ("cli", "gui", "pipeline", "voice", "winapp", "llm", "write_script", "render", "crop", "paths")]

ICON = os.path.join(SRC, "commentkit", "webui", "commentkit.ico")
a = Analysis([os.path.join(SPECPATH, "commentkit_entry.py")], datas=datas, hiddenimports=hidden, pathex=[SRC],
             excludes=["commentkit.tts_vieneu", "numpy", "tkinter"])
pyz = PYZ(a.pure)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="commentkit", console=True, icon=ICON)
app = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CommentKitApp", console=False, icon=ICON)
coll = COLLECT(cli, app, a.binaries, a.datas, name="CommentKit")
