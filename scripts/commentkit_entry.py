"""Entry point PyInstaller builds commentkit.exe and CommentKitApp.exe from.
CommentKitApp.exe (no console) always opens the app window; commentkit.exe takes commands."""
import sys
from pathlib import Path

from commentkit.cli import main

if __name__ == "__main__":
    if Path(sys.executable).stem.lower() == "commentkitapp":
        sys.exit(main(["gui"]))
    sys.exit(main())
