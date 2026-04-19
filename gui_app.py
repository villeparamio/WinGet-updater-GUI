import os
import sys
import time
import ctypes
import tempfile
import threading
import webbrowser
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from i18n import I18N
from winget_core import (
    parse_winget_output,
    precheck_upgrade,
    perform_upgrade_attempt,
    should_retry_without_exact,
    get_running_process_hints,
    should_offer_close_retry,
    kill_processes,
)

APP_VERSION = "v1.3"
I18N_OBJ = I18N(Path(__file__).resolve().parent)
T = I18N_OBJ.t


LANGUAGE_NAMES = {
    "es": lambda: T("lang_es"),
    "en": lambda: T("lang_en"),
}


SOLARIZED_DARK_QSS = """
/*
    Solarized Dark palette
    ----------------------
    base03  #002b36   app background
    base02  #073642   surface / cards
    base01  #586e75   borders, disabled text
    base00  #657b83
    base0   #839496   body text
    base1   #b8c4c4   secondary text (bumped from #93a1a1 for contrast)
    base2   #eee8d5   primary text
    yellow  #b58900   explicit target
    orange  #cb4b16   warning
    red     #dc322f   danger / cancel
    blue    #268bd2   selection
    cyan    #2aa198   primary action / progress
    green   #859900   success
*/

QMainWindow, QDialog {
    background-color: #002b36;
}
QWidget#central {
    background-color: #002b36;
}

QLabel, QCheckBox {
    color: #eee8d5;
    background: transparent;
    font-family: 'Segoe UI';
    font-size: 10pt;
}

QLabel#hero {
    color: #eee8d5;
    font-size: 22pt;
    font-weight: 700;
}
QLabel#subtitle {
    color: #b8c4c4;
    font-size: 10pt;
}
QLabel#muted, QLabel#pkgMeta, QLabel#pkgId, QLabel#footerStatus, QLabel#logLabel {
    color: #b8c4c4;
}
QLabel#pkgName {
    color: #eee8d5;
    font-weight: 600;
    font-size: 11pt;
}
QLabel#statValue {
    color: #eee8d5;
    font-size: 22pt;
    font-weight: 700;
}
QLabel#statLabel {
    color: #b8c4c4;
    font-size: 9pt;
}
QLabel#chip {
    background-color: #0b3c49;
    color: #b8c4c4;
    border: 1px solid #1e566a;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 9pt;
}
QLabel#chipExplicit {
    background-color: #3a2600;
    color: #f0c050;
    border: 1px solid #6b4500;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#chipWarn {
    background-color: #3d1f00;
    color: #f5a05a;
    border: 1px solid #7a3e00;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 9pt;
}
QLabel#dialogIconWarn {
    color: #cb4b16;
    font-size: 30pt;
    background: transparent;
}
QLabel#dialogIconInfo {
    color: #2aa198;
    font-size: 30pt;
    background: transparent;
}

QFrame#surface {
    background-color: #073642;
    border: 1px solid #0e4553;
    border-radius: 10px;
}
QFrame#logPanel {
    background-color: #073642;
    border: 1px solid #0e4553;
    border-radius: 10px;
}
QFrame#stat {
    background-color: #073642;
    border: 1px solid #0e4553;
    border-radius: 10px;
}

QFrame#card {
    background-color: #073642;
    border: 1px solid #0e4553;
    border-left: 3px solid #586e75;
    border-radius: 8px;
}
QFrame#card:hover {
    background-color: #0a3e4b;
    border-color: #19546a;
}
QFrame#card[cardState="selected"] {
    border-left: 3px solid #2aa198;
}
QFrame#card[cardState="muted"] {
    border-left: 3px solid #586e75;
}
QFrame#card[cardState="explicit"] {
    border-left: 3px solid #b58900;
}

QPushButton {
    background-color: #0a3a46;
    color: #eee8d5;
    border: 1px solid #4f676e;
    border-radius: 8px;
    padding: 7px 14px;
    font-family: 'Segoe UI';
    font-size: 10pt;
}
QPushButton:hover {
    background-color: #104553;
    border-color: #657b83;
}
QPushButton:pressed {
    background-color: #08303b;
}
QPushButton:disabled {
    background-color: #0b333b;
    color: #586e75;
    border-color: #2d4a52;
}

QPushButton#primaryButton {
    background-color: #2aa198;
    color: #002b36;
    border: 1px solid #2aa198;
    font-weight: 700;
}
QPushButton#primaryButton:hover {
    background-color: #36b8ae;
    border-color: #36b8ae;
}
QPushButton#primaryButton:pressed {
    background-color: #1e8a82;
    border-color: #1e8a82;
}
QPushButton#primaryButton:disabled {
    background-color: #1e5f5b;
    color: #5a8984;
    border-color: #1e5f5b;
}

QPushButton#dangerButton {
    background-color: #dc322f;
    color: #fdf6e3;
    border: 1px solid #dc322f;
    font-weight: 600;
}
QPushButton#dangerButton:hover {
    background-color: #e45451;
    border-color: #e45451;
}
QPushButton#dangerButton:pressed {
    background-color: #b92c2a;
}
QPushButton#dangerButton:disabled {
    background-color: #4a1f1e;
    color: #8a5a59;
    border-color: #4a1f1e;
}

QPushButton#chipButton {
    background-color: #0b3c49;
    color: #b8c4c4;
    border: 1px solid #1e566a;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 9pt;
}
QPushButton#chipButton:hover {
    background-color: #104553;
    color: #eee8d5;
    border-color: #2f6b7e;
}

QLineEdit, QComboBox {
    background-color: #002b36;
    color: #eee8d5;
    selection-background-color: #268bd2;
    selection-color: #fdf6e3;
    padding: 7px 10px;
    border: 1px solid #4f676e;
    border-radius: 8px;
    font-family: 'Segoe UI';
    font-size: 10pt;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #2aa198;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #93a1a1;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background-color: #073642;
    color: #eee8d5;
    selection-background-color: #268bd2;
    selection-color: #fdf6e3;
    border: 1px solid #4f676e;
    padding: 4px;
    outline: 0;
}

QScrollArea {
    background-color: #041e26;
    border: 1px solid #0e4553;
    border-radius: 10px;
}
QWidget#scrollContent {
    background-color: #041e26;
}
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 6px 2px 6px 2px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #33545c;
    min-height: 32px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #456770;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
    height: 0px;
    width: 0px;
}

QProgressBar {
    background-color: #0b3c49;
    border: 1px solid #4f676e;
    border-radius: 10px;
    text-align: center;
    color: #eee8d5;
    font-weight: 600;
    min-height: 22px;
}
QProgressBar::chunk {
    background-color: #2aa198;
    border-radius: 9px;
}

QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
}
QCheckBox::indicator:unchecked {
    border: 1.5px solid #657b83;
    background-color: #002b36;
}
QCheckBox::indicator:unchecked:hover {
    border-color: #93a1a1;
}
QCheckBox::indicator:checked {
    border: 1.5px solid #2aa198;
    background-color: #2aa198;
}

QTextEdit#logView {
    background-color: #001e26;
    color: #b8c4c4;
    border: 1px solid #0e4553;
    border-radius: 8px;
    padding: 8px 10px;
    font-family: 'Cascadia Mono', 'Consolas', 'Courier New', monospace;
    font-size: 9.5pt;
    selection-background-color: #268bd2;
    selection-color: #fdf6e3;
}

QMessageBox {
    background-color: #002b36;
    color: #eee8d5;
}
QMessageBox QLabel {
    color: #eee8d5;
    background: transparent;
}
"""


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def ensure_admin():
    if is_admin():
        return

    if getattr(sys, "frozen", False):
        exe = sys.executable
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        cwd = os.getcwd()
    else:
        exe = sys.executable
        script = os.path.abspath(sys.argv[0])
        params = " ".join(f'"{a}"' for a in [script, *sys.argv[1:]])
        cwd = os.path.dirname(script) or os.getcwd()

    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1)
    if rc <= 32:
        QMessageBox.critical(None, T("error_admin_title"), T("error_admin_body", code=rc))
        return
    sys.exit(0)


def has_winget():
    try:
        r = subprocess.run(["winget", "-v"], capture_output=True, text=True)
        return r.returncode == 0 and bool((r.stdout or "").strip())
    except FileNotFoundError:
        return False


def try_install_winget(log_fn=None):
    def log(msg):
        if log_fn:
            log_fn(msg)
        else:
            print(msg)

    log(T("winget_install_start"))
    bundle_path = os.path.join(tempfile.gettempdir(), "AppInstaller.msixbundle")
    ps = [
        "powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        f"Invoke-WebRequest -Uri https://aka.ms/getwinget -OutFile '{bundle_path}' -UseBasicParsing"
    ]
    r = subprocess.run(ps, capture_output=True, text=True)
    if r.returncode != 0:
        log(T("winget_install_download_failed"))
        webbrowser.open("ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1")
        return False

    ps_install = [
        "powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        f"Try {{ Add-AppxPackage -Path '{bundle_path}' -ForceApplicationShutdown -ForceUpdateFromAnyVersion -Verbose; exit 0 }} Catch {{ $_ | Out-String; exit 1 }}"
    ]
    r2 = subprocess.run(ps_install, capture_output=True, text=True)
    if r2.returncode != 0:
        log(T("winget_install_failed"))
        webbrowser.open("ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1")
        return False

    ok = has_winget()
    log(T("winget_install_ok") if ok else T("winget_still_missing"))
    return ok


class ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.position().toPoint())
            while child is not None:
                if isinstance(child, (QCheckBox, QPushButton)):
                    super().mousePressEvent(event)
                    return
                child = child.parentWidget()
            self.clicked.emit()
        super().mousePressEvent(event)


class LoaderThread(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            self.loaded.emit(parse_winget_output() or [])
        except Exception as e:
            self.failed.emit(str(e))


class UpdateThread(QThread):
    package_done = Signal(dict)
    finished_summary = Signal(list)
    log_line = Signal(str)
    log_progress = Signal(str)
    status = Signal(str)
    close_retry_requested = Signal(str, str)

    def __init__(self, selected, parent=None):
        super().__init__(parent)
        self.selected = selected
        self.cancelled = False
        self.current_process = None
        self._close_retry_event = threading.Event()
        self._close_retry_answer = False

    def cancel(self):
        self.cancelled = True
        try:
            if self.current_process and self.current_process.poll() is None:
                self.current_process.terminate()
        except Exception:
            pass

    def provide_close_retry_answer(self, answer):
        self._close_retry_answer = bool(answer)
        self._close_retry_event.set()

    def _ask_close_retry_blocking(self, name, procs_txt):
        self._close_retry_event.clear()
        self._close_retry_answer = False
        self.close_retry_requested.emit(name, procs_txt)
        self._close_retry_event.wait()
        return self._close_retry_answer

    def _set_current_process(self, proc):
        self.current_process = proc

    def _is_cancelled(self):
        return self.cancelled

    def _run_upgrade(self, pkg, use_exact=True):
        return perform_upgrade_attempt(
            pkg,
            self.log_line.emit,
            self.log_progress.emit,
            self._is_cancelled,
            self._set_current_process,
            use_exact=use_exact,
        )

    def run(self):
        results = []
        total = len(self.selected)

        for idx, pkg in enumerate(self.selected, start=1):
            if self.cancelled:
                self.log_line.emit(T("log_operation_cancelled"))
                break

            self.status.emit(T("status_updating_item", index=idx, total=total, name=pkg["Name"]))
            self.log_line.emit(T("log_update_item",
                                 index=idx, total=total, name=pkg["Name"],
                                 version=pkg["Version"], available=pkg["Available"], id=pkg["Id"]))

            running = get_running_process_hints(pkg["Id"])
            if running:
                self.log_line.emit(T("log_blocking_processes", processes=", ".join(running)))

            can_upgrade, pre_status, pre_output = precheck_upgrade(pkg)
            if not can_upgrade and pre_status in ("no_longer_pending", "not_applicable", "not_found"):
                mapping = {
                    "no_longer_pending": (T("log_skip_no_longer_pending"), T("reason_no_longer_pending")),
                    "not_applicable": (T("log_skip_not_applicable"), T("reason_not_applicable")),
                    "not_found": (T("log_skip_not_found"), T("reason_not_found")),
                }
                msg, reason = mapping[pre_status]
                self.log_line.emit(msg)
                result = {
                    "status": pre_status, "pkg": pkg, "log": None,
                    "reason": reason, "returncode": 0, "raw_output": pre_output,
                }
                results.append(result)
                self.package_done.emit(result)
                continue

            result = self._run_upgrade(pkg, use_exact=True)

            status_msgs = {
                "updated": T("log_updated"),
                "updated_restart_required": T("log_updated_restart_required"),
                "no_longer_pending": T("log_resolved_no_longer_pending"),
                "already_installed": T("log_resolved_already_installed"),
                "different_install_technology": T("log_resolved_different_tech"),
            }
            if result["status"] in status_msgs:
                self.log_line.emit(status_msgs[result["status"]])

            if (not pkg.get("RequiresExplicitTarget")
                    and result["status"] in ("not_applicable", "not_found", "no_longer_pending")
                    and should_retry_without_exact(result)):
                self.log_line.emit(T("log_retry_without_exact"))
                retry_no_exact = self._run_upgrade(pkg, use_exact=False)
                if retry_no_exact["status"] != "cancelled":
                    retry_no_exact["raw_output"] = (
                        "===== FIRST ATTEMPT (--exact) =====\n"
                        + (result.get("raw_output") or "")
                        + "\n===== RETRY WITHOUT --exact =====\n"
                        + (retry_no_exact.get("raw_output") or "")
                    )
                    result = retry_no_exact

            if result["status"] == "cancelled":
                self.log_line.emit(T("log_cancelled"))
                results.append(result)
                self.package_done.emit(result)
                self.finished_summary.emit(results)
                return

            running_after_fail = get_running_process_hints(pkg["Id"])
            if should_offer_close_retry(result, running_after_fail):
                procs_txt = ", ".join(running_after_fail)
                if self._ask_close_retry_blocking(pkg["Name"], procs_txt):
                    self.log_line.emit(T("log_closing_processes", processes=procs_txt))
                    for kr in kill_processes(running_after_fail):
                        self.log_line.emit(
                            T("log_process_closed", process=kr["process"]) if kr["ok"]
                            else T("log_process_not_closed", process=kr["process"])
                        )
                    time.sleep(1.5)
                    self.log_line.emit(T("log_retry_once"))
                    retry_result = self._run_upgrade(pkg, use_exact=True)
                    if retry_result["status"] != "cancelled":
                        retry_result["raw_output"] = (
                            "===== FIRST ATTEMPT =====\n"
                            + (result.get("raw_output") or "")
                            + "\n===== RETRY ATTEMPT =====\n"
                            + (retry_result.get("raw_output") or "")
                        )
                        result = retry_result

            results.append(result)
            self.package_done.emit(result)

        self.finished_summary.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(T("app_title", version=APP_VERSION))
        self.resize(1280, 900)
        self.setMinimumSize(1040, 760)
        self.pkgs = []
        self.loader_thread = None
        self.update_thread = None
        self.current_lang = I18N_OBJ.lang
        self._last_was_progress = False
        self._build_ui()
        self.refresh_list_async(initial=True)

    def _build_ui(self):
        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        # --- Header ---
        header = QHBoxLayout()
        header.setSpacing(16)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        hero = QLabel(T("app_name"))
        hero.setObjectName("hero")
        self.subtitle = QLabel(T("subtitle_detected"))
        self.subtitle.setObjectName("subtitle")
        title_box.addWidget(hero)
        title_box.addWidget(self.subtitle)
        header.addLayout(title_box, 1)

        self.btn_refresh = QPushButton(T("btn_refresh"))
        self.btn_refresh.setMinimumWidth(110)
        self.btn_save = QPushButton(T("btn_save_log"))
        self.btn_save.setMinimumWidth(120)
        self.btn_update = QPushButton(T("btn_update_selected", count=0))
        self.btn_update.setObjectName("primaryButton")
        self.btn_update.setMinimumWidth(230)
        header.addWidget(self.btn_refresh, 0, Qt.AlignVCenter)
        header.addWidget(self.btn_save, 0, Qt.AlignVCenter)
        header.addWidget(self.btn_update, 0, Qt.AlignVCenter)
        root.addLayout(header)

        # --- Stats ---
        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.stat_total = self._make_stat("0", T("stats_available"))
        self.stat_selected = self._make_stat("0", T("stats_selected"))
        self.stat_special = self._make_stat("0", T("stats_special"))
        stats.addWidget(self.stat_total[0], 1)
        stats.addWidget(self.stat_selected[0], 1)
        stats.addWidget(self.stat_special[0], 1)
        root.addLayout(stats)

        # --- Toolbar ---
        toolbar_frame = QFrame(objectName="surface")
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 10, 12, 10)
        toolbar.setSpacing(10)

        self.search = QLineEdit()
        self.search.setPlaceholderText(T("search_placeholder"))
        self.search.setMinimumWidth(280)
        toolbar.addWidget(self.search, 1)

        self.lbl_view = QLabel(T("label_view"))
        self.lbl_view.setObjectName("muted")
        toolbar.addWidget(self.lbl_view)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([T("filter_all"), T("filter_selected"), T("filter_explicit"), T("filter_unknown")])
        self.filter_combo.setMinimumWidth(130)
        toolbar.addWidget(self.filter_combo)

        self.lbl_language = QLabel(T("label_language"))
        self.lbl_language.setObjectName("muted")
        toolbar.addWidget(self.lbl_language)
        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumWidth(120)
        toolbar.addWidget(self.lang_combo)

        self.btn_all = QPushButton(T("btn_select_all"))
        self.btn_none = QPushButton(T("btn_select_none"))
        toolbar.addWidget(self.btn_all)
        toolbar.addWidget(self.btn_none)
        root.addWidget(toolbar_frame)

        # --- Package list ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget(objectName="scrollContent")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(8)
        self.scroll_area.setWidget(self.scroll_content)
        root.addWidget(self.scroll_area, 3)

        # --- Progress row ---
        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%v / %m")
        progress_row.addWidget(self.progress, 1)

        self.btn_cancel = QPushButton(T("btn_cancel_update"))
        self.btn_cancel.setObjectName("dangerButton")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setMinimumWidth(180)
        progress_row.addWidget(self.btn_cancel)
        root.addLayout(progress_row)

        self.footer_status = QLabel(T("status_ready"))
        self.footer_status.setObjectName("footerStatus")
        root.addWidget(self.footer_status)

        # --- Log (always visible) ---
        log_frame = QFrame(objectName="logPanel")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(12, 10, 12, 12)
        log_layout.setSpacing(6)
        log_title = QLabel(T("log_title"))
        log_title.setObjectName("logLabel")
        log_layout.addWidget(log_title)
        self.text_log = QTextEdit()
        self.text_log.setObjectName("logView")
        self.text_log.setReadOnly(True)
        self.text_log.setMinimumHeight(170)
        log_layout.addWidget(self.text_log)
        root.addWidget(log_frame, 2)

        # --- Connections ---
        self.btn_refresh.clicked.connect(lambda: self.refresh_list_async(initial=False))
        self.btn_save.clicked.connect(self.save_log)
        self.btn_update.clicked.connect(self.start_update)
        self.btn_cancel.clicked.connect(self.cancel_update)
        self.btn_all.clicked.connect(lambda: self.set_all_selected(True))
        self.btn_none.clicked.connect(lambda: self.set_all_selected(False))
        self.search.textChanged.connect(self.render_list)
        self.filter_combo.currentTextChanged.connect(self.render_list)
        self.lang_combo.currentIndexChanged.connect(self.change_language)

        self._set_enabled(False)
        self.append_log(T("log_initializing"))
        self.populate_language_combo()

        icon_path = Path(__file__).with_name("winget_updater.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _make_stat(self, value, label):
        frame = QFrame(objectName="stat")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        v = QLabel(value)
        v.setObjectName("statValue")
        t = QLabel(label)
        t.setObjectName("statLabel")
        layout.addWidget(v)
        layout.addWidget(t)
        return frame, v, t

    def populate_language_combo(self):
        self.lang_combo.blockSignals(True)
        self.lang_combo.clear()
        for code in I18N_OBJ.available_languages():
            label = LANGUAGE_NAMES.get(code, lambda c=code: c)()
            self.lang_combo.addItem(label, code)
        idx = self.lang_combo.findData(self.current_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.blockSignals(False)

    def append_log(self, msg):
        self._last_was_progress = False
        cursor = self.text_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(msg if msg.endswith("\n") else msg + "\n")
        self.text_log.setTextCursor(cursor)
        self.text_log.ensureCursorVisible()

    def replace_progress(self, msg):
        cursor = self.text_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        if self._last_was_progress:
            cursor.deletePreviousChar()
            cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
        cursor.insertText(msg + "\n")
        self._last_was_progress = True
        self.text_log.setTextCursor(cursor)
        self.text_log.ensureCursorVisible()

    def set_status(self, msg):
        self.footer_status.setText(msg)

    def change_language(self):
        code = self.lang_combo.currentData()
        if not code or code == self.current_lang:
            return
        self.current_lang = code
        I18N_OBJ.set_language(code)
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(T("app_title", version=APP_VERSION))
        self.btn_refresh.setText(T("btn_refresh"))
        self.btn_save.setText(T("btn_save_log"))
        self.btn_cancel.setText(T("btn_cancel_update"))
        self.btn_all.setText(T("btn_select_all"))
        self.btn_none.setText(T("btn_select_none"))
        self.stat_total[2].setText(T("stats_available"))
        self.stat_selected[2].setText(T("stats_selected"))
        self.stat_special[2].setText(T("stats_special"))
        self.lbl_view.setText(T("label_view"))
        self.lbl_language.setText(T("label_language"))
        self.search.setPlaceholderText(T("search_placeholder"))
        current_filter = self.filter_combo.currentIndex()
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItems([T("filter_all"), T("filter_selected"), T("filter_explicit"), T("filter_unknown")])
        self.filter_combo.setCurrentIndex(max(current_filter, 0))
        self.filter_combo.blockSignals(False)
        self.populate_language_combo()
        self.update_summary_ui()
        self.render_list()

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, T("save_dialog_title"), "", "Texto (*.txt)")
        if not path:
            return
        Path(path).write_text(self.text_log.toPlainText(), encoding="utf-8")
        QMessageBox.information(self, T("saved_title"), T("saved_message", path=path))

    def _set_enabled(self, enabled):
        for widget in (self.btn_refresh, self.btn_save, self.btn_update,
                       self.btn_all, self.btn_none, self.search, self.filter_combo):
            widget.setEnabled(enabled)

    def visible_items(self):
        q = self.search.text().strip().lower()
        mode = self.filter_combo.currentText().strip().lower() or "all"
        items = []
        for pkg in self.pkgs:
            haystack = " ".join([pkg.get("Name", ""), pkg.get("Id", ""),
                                 pkg.get("Version", ""), pkg.get("Available", ""),
                                 pkg.get("Source", "")]).lower()
            if q and q not in haystack:
                continue
            if mode == "selected" and not pkg.get("_selected", True):
                continue
            if mode == "explicit" and not pkg.get("RequiresExplicitTarget"):
                continue
            if mode == "unknown" and (pkg.get("Version") or "").strip().lower() not in ("unknown", "desconocida", ""):
                continue
            items.append(pkg)
        return items

    def update_summary_ui(self):
        selected_count = sum(1 for pkg in self.pkgs if pkg.get("_selected", True))
        explicit_count = sum(1 for pkg in self.pkgs if pkg.get("RequiresExplicitTarget"))
        unknown_count = sum(1 for pkg in self.pkgs if (pkg.get("Version") or "").strip().lower() in ("unknown", "desconocida", ""))
        self.stat_total[1].setText(str(len(self.pkgs)))
        self.stat_selected[1].setText(str(selected_count))
        self.stat_special[1].setText(str(explicit_count + unknown_count))
        visible_count = len(self.visible_items())
        if self.pkgs:
            self.subtitle.setText(T("headline_visible_detected", visible=visible_count, total=len(self.pkgs)))
        else:
            self.subtitle.setText(T("subtitle_up_to_date"))
        self.btn_update.setText(T("btn_update_selected", count=selected_count))

    def clear_scroll(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def make_chip(self, text, object_name="chip"):
        label = QLabel(text)
        label.setObjectName(object_name)
        return label

    def render_list(self):
        self.clear_scroll()
        items = self.visible_items()
        if not self.pkgs:
            self.scroll_layout.addWidget(self._empty_card(T("empty_no_updates_title"), T("empty_no_updates_body")))
            self.scroll_layout.addStretch(1)
            self.update_summary_ui()
            return
        if not items:
            self.scroll_layout.addWidget(self._empty_card(T("empty_no_results_title"), T("empty_no_results_body")))
            self.scroll_layout.addStretch(1)
            self.update_summary_ui()
            return

        for pkg in items:
            self.scroll_layout.addWidget(self._package_card(pkg))
        self.scroll_layout.addStretch(1)
        self.update_summary_ui()

    def _empty_card(self, title, subtitle):
        card = QFrame(objectName="surface")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("pkgName")
        s = QLabel(subtitle)
        s.setObjectName("muted")
        layout.addWidget(t)
        layout.addWidget(s)
        return card

    def _card_state(self, pkg):
        if pkg.get("RequiresExplicitTarget"):
            return "explicit"
        if pkg.get("_selected", True):
            return "selected"
        return "muted"

    def _apply_card_state(self, card, pkg):
        card.setProperty("cardState", self._card_state(pkg))
        card.style().unpolish(card)
        card.style().polish(card)

    def _package_card(self, pkg):
        card = ClickableFrame()
        card.setObjectName("card")
        card.setProperty("cardState", self._card_state(pkg))

        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        checkbox = QCheckBox()
        checkbox.setChecked(pkg.get("_selected", True))
        checkbox.stateChanged.connect(lambda state, p=pkg, c=card: self.on_pkg_checked(p, state, c))
        layout.addWidget(checkbox, 0, Qt.AlignVCenter)
        card.clicked.connect(lambda p=pkg, cb=checkbox: self.toggle_pkg_from_row(p, cb))

        info = QVBoxLayout()
        info.setSpacing(3)
        name = QLabel(pkg["Name"])
        name.setObjectName("pkgName")
        pkg_id = QLabel(pkg["Id"])
        pkg_id.setObjectName("pkgId")
        info.addWidget(name)
        info.addWidget(pkg_id)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        meta = QLabel(f"{pkg['Version']}  →  {pkg['Available']}   ·   {pkg.get('Source', '') or T('unknown_source')}")
        meta.setObjectName("pkgMeta")
        meta_row.addWidget(meta)
        if pkg.get("RequiresExplicitTarget"):
            meta_row.addWidget(self.make_chip(T("chip_explicit"), "chipExplicit"))
        if (pkg.get("Version") or "").strip().lower() in ("unknown", "desconocida", ""):
            meta_row.addWidget(self.make_chip(T("chip_unknown"), "chipWarn"))
        meta_row.addStretch(1)
        info.addLayout(meta_row)

        layout.addLayout(info, 1)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        btn_mark = QPushButton(T("btn_mark"))
        btn_mark.setObjectName("chipButton")
        btn_unmark = QPushButton(T("btn_unmark"))
        btn_unmark.setObjectName("chipButton")
        btn_mark.clicked.connect(lambda: self.set_one_selected(pkg, True))
        btn_unmark.clicked.connect(lambda: self.set_one_selected(pkg, False))
        actions.addWidget(btn_mark)
        actions.addWidget(btn_unmark)
        layout.addLayout(actions, 0)

        return card

    def on_pkg_checked(self, pkg, state, card=None):
        pkg["_selected"] = int(state) != 0
        if card is not None:
            self._apply_card_state(card, pkg)
        self.update_summary_ui()

    def toggle_pkg_from_row(self, pkg, checkbox):
        checkbox.setChecked(not checkbox.isChecked())

    def set_one_selected(self, pkg, value):
        pkg["_selected"] = value
        self.update_summary_ui()
        self.render_list()

    def set_all_selected(self, value):
        for pkg in self.pkgs:
            pkg["_selected"] = value
        self.update_summary_ui()
        self.render_list()

    def refresh_list_async(self, initial=False):
        self._set_enabled(False)
        self.set_status(T("status_fetching_list") if initial else T("status_refreshing_list"))
        self.append_log(T("log_fetching_list") if initial else T("log_refreshing_list"))

        if not has_winget():
            if QMessageBox.question(self, T("install_winget_title"), T("install_winget_prompt")) != QMessageBox.Yes:
                QMessageBox.critical(self, T("winget_missing_title"), T("winget_missing_body"))
                return
            if not try_install_winget(self.append_log):
                QMessageBox.critical(self, T("winget_missing_title"), T("winget_missing_body"))
                return

        self.loader_thread = LoaderThread(self)
        self.loader_thread.loaded.connect(self.on_loaded)
        self.loader_thread.failed.connect(lambda msg: QMessageBox.critical(self, T("error_title"), msg))
        self.loader_thread.start()

    def on_loaded(self, pkgs):
        self.pkgs = pkgs
        for pkg in self.pkgs:
            pkg.setdefault("_selected", True)
        self.render_list()
        self._set_enabled(True)
        self.set_status(T("status_ready"))
        self.append_log(T("log_list_updated") if self.pkgs else T("status_ready"))

    def show_result_dialog(self, title, body, warning=False):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setModal(True)
        dlg.setMinimumWidth(520)
        dlg.setMaximumWidth(640)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(14)

        icon_label = QLabel("⚠" if warning else "ℹ")
        icon_label.setObjectName("dialogIconWarn" if warning else "dialogIconInfo")
        icon_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        top.addWidget(icon_label, 0, Qt.AlignTop)

        text_label = QLabel(body)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top.addWidget(text_label, 1)

        layout.addLayout(top)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok_btn = QPushButton("OK")
        ok_btn.setMinimumWidth(90)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(dlg.accept)
        buttons.addWidget(ok_btn)
        layout.addLayout(buttons)

        dlg.exec()

    def start_update(self):
        selected = [pkg for pkg in self.pkgs if pkg.get("_selected", True)]
        if not selected:
            QMessageBox.information(self, T("select_none_title"), T("select_none_body"))
            return

        self._set_enabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setMaximum(len(selected))
        self.progress.setValue(0)
        self.set_status(T("status_updating_count", count=len(selected)))

        self.update_thread = UpdateThread(selected, self)
        self.update_thread.log_line.connect(self.append_log)
        self.update_thread.log_progress.connect(self.replace_progress)
        self.update_thread.status.connect(self.set_status)
        self.update_thread.package_done.connect(lambda _r: self.progress.setValue(self.progress.value() + 1))
        self.update_thread.finished_summary.connect(self.on_update_finished)
        self.update_thread.close_retry_requested.connect(self._on_close_retry_requested)
        self.update_thread.start()

    def _on_close_retry_requested(self, name, procs_txt):
        ans = QMessageBox.question(
            self,
            T("retry_close_title"),
            T("retry_close_prompt", name=name, processes=procs_txt),
        ) == QMessageBox.Yes
        if self.update_thread is not None:
            self.update_thread.provide_close_retry_answer(ans)

    def cancel_update(self):
        if self.update_thread:
            self.update_thread.cancel()
            self.append_log(T("log_cancel_requested"))
            self.set_status(T("status_cancelling"))

    def on_update_finished(self, results):
        updated = [r for r in results if r["status"] in ("updated", "updated_restart_required")]
        restart_required = [r for r in results if r["status"] == "updated_restart_required"]
        already_installed = [r for r in results if r["status"] == "already_installed"]
        not_applicable = [r for r in results if r["status"] == "not_applicable"]
        not_found = [r for r in results if r["status"] == "not_found"]
        no_longer_pending = [r for r in results if r["status"] == "no_longer_pending"]
        different_install_technology = [r for r in results if r["status"] == "different_install_technology"]
        installer_failed = [r for r in results if r["status"] == "installer_failed"]
        cancelled = [r for r in results if r["status"] == "cancelled"]
        failed = [r for r in results if r["status"] in ("failed", "ok_but_unclear")]
        resolved = updated + no_longer_pending + already_installed

        summary = [
            T("summary_resolved", resolved=len(resolved), total=len(results)),
            T("summary_updated", count=len(updated)),
        ]
        if restart_required: summary.append(T("summary_restart_required", count=len(restart_required)))
        if already_installed: summary.append(T("summary_already_installed", count=len(already_installed)))
        if not_applicable: summary.append(T("summary_not_applicable", count=len(not_applicable)))
        if no_longer_pending: summary.append(T("summary_no_longer_pending", count=len(no_longer_pending)))
        if not_found: summary.append(T("summary_not_found", count=len(not_found)))
        if different_install_technology: summary.append(T("summary_different_tech", count=len(different_install_technology)))
        if installer_failed: summary.append(T("summary_installer_failed", count=len(installer_failed)))
        if failed: summary.append(T("summary_failed", count=len(failed)))
        if cancelled: summary.append(T("summary_cancelled", count=len(cancelled)))
        body = "\n".join(summary)

        self.progress.setValue(0)
        self.btn_cancel.setEnabled(False)
        self._set_enabled(True)
        self.set_status(T("status_finished"))
        self.refresh_list_async(initial=False)
        if installer_failed or failed:
            self.show_result_dialog(T("complete_with_issues_title"), body, warning=True)
        else:
            self.show_result_dialog(T("complete_title"), body, warning=False)


def build_gui():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(SOLARIZED_DARK_QSS)
    window = MainWindow()
    window.show()
    app.exec()
