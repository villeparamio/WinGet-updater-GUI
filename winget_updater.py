import os
import sys
import traceback
from datetime import datetime

from gui_app import ensure_admin, build_gui


def crash_log_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


if __name__ == "__main__":
    try:
        ensure_admin()
        build_gui()
    except Exception:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_path = os.path.join(crash_log_dir(), f"crash_{stamp}.log")
        with open(crash_path, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
