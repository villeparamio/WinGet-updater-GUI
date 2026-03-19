import os
import traceback

from gui_app import ensure_admin, build_gui


if __name__ == "__main__":
    try:
        ensure_admin()
        build_gui()
    except Exception:
        crash_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
        with open(crash_path, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
