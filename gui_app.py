import os
import sys
import time
import ctypes
import tempfile
import threading
import webbrowser
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QAction, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
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

APP_VERSION = "v1.2"
I18N_OBJ = I18N(Path(__file__).resolve().parent)
T = I18N_OBJ.t


LANGUAGE_NAMES = {
    "es": lambda: T("lang_es"),
    "en": lambda: T("lang_en"),
}

SOLARIZED_DARK_QSS = """
QMainWindow, QWidget#central {
    background: #002b36;
    color: #eee8d5;
    font-family: 'Segoe UI';
    font-size: 10pt;
}
QWidget {
    color: #eee8d5;
    font-family: 'Segoe UI';
    font-size: 10pt;
}
QLabel {
    background: transparent;
    border: none;
}
QFrame#surface, QScrollArea, QWidget#scrollContent {
    background: #073642;
    border: 1px solid #4f676e;
    border-radius: 10px;
}
QFrame#card {
    background: #073642;
    border: 1px solid #4f676e;
    border-radius: 10px;
}
QFrame#stat {
    background: #0b3c49;
    border: 1px solid #4f676e;
    border-radius: 10px;
}
QFrame#card QLabel, QFrame#stat QLabel, QFrame#surface QLabel, QWidget#scrollContent QLabel {
    background: transparent;
    border: none;
}
QLabel#hero {
    color: #eee8d5;
    font-size: 24pt;
    font-weight: 700;
}
QLabel#subtitle, QLabel#muted, QLabel#pkgMeta, QLabel#pkgId {
    color: #93a1a1;
}
QLabel#headline {
    color: #eee8d5;
    font-size: 18pt;
    font-weight: 600;
}
QLabel#statValue {
    color: #eee8d5;
    font-size: 18pt;
    font-weight: 700;
}
QLabel#statLabel {
    color: #93a1a1;
    font-size: 9pt;
}
QPushButton {
    background: #0a3a46;
    color: #eee8d5;
    border: 1px solid #4f676e;
    border-radius: 8px;
    padding: 7px 12px;
}
QPushButton:hover {
    background: #104553;
    border-color: #657b83;
}
QPushButton:pressed {
    background: #08303b;
    border-color: #839496;
}
QPushButton:disabled {
    background: #23424a;
    color: #657b83;
    border-color: #3d5961;
}
QPushButton#primaryButton {
    background: #2aa198;
    color: #002b36;
    border: 1px solid #2aa198;
    font-weight: 700;
}
QPushButton#primaryButton:hover {
    background: #35b8ae;
}
QPushButton#dangerButton {
    background-color: #dc322f;
    color: #fdf6e3;
    border: 1px solid #dc322f;
}
QPushButton#dangerButton:hover {
    background-color: #e45451;
}
QPushButton#dangerButton:pressed {
    background-color: #b92c2a;
}
QPushButton#dangerButton:disabled {
    background-color: #8b3a3a;
    color: #f3d9d6;
    border: 1px solid #a24a4a;
}
QLineEdit, QComboBox, QTextEdit {
    background: #073642;
    color: #eee8d5;
    selection-background-color: #268bd2;
    selection-color: #fdf6e3;
    padding: 8px 10px;
    border: 1px solid #586e75;
    border-radius: 10px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border: none;
    background: transparent;
}
QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}
QComboBox QAbstractItemView {
    background: #073642;
    color: #eee8d5;
    selection-background-color: #268bd2;
    border: 1px solid #586e75;
}
QScrollArea {
    border: 1px solid #4f676e;
    border-radius: 10px;
}
QScrollArea > QWidget > QWidget {
    background: #073642;
}
QScrollBar:vertical {
    background: #073642;
    width: 12px;
    margin: 8px 2px 8px 2px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #33545c;
    min-height: 28px;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover {
    background: #41666f;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    border: none;
    height: 0px;
}
QProgressBar {
    border: 1px solid #586e75;
    border-radius: 8px;
    background-color: #204851;
    text-align: center;
    color: #eee8d5;
    min-height: 18px;
}
QProgressBar::chunk {
    background-color: #2aa198;
    border-radius: 7px;
}
QCheckBox {
    spacing: 8px;
    background: transparent;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QCheckBox::indicator:unchecked {
    border: 1px solid #657b83;
    background: #002b36;
    border-radius: 4px;
}
QCheckBox::indicator:checked {
    border: 1px solid #2aa198;
    background: #2aa198;
    border-radius: 4px;
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


class QtTextAdapter:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def after(self, _delay, callback):
        callback()

    def insert(self, _index, text):
        self.text_edit.moveCursor(QTextCursor.End)
        self.text_edit.insertPlainText(text)

    def see(self, _index):
        self.text_edit.moveCursor(QTextCursor.End)
        self.text_edit.ensureCursorVisible()

    def index(self, spec):
        doc = self.text_edit.document()
        blocks = max(doc.blockCount(), 1)
        if spec == "end-1c":
            return f"{blocks}.0"
        if spec == "end-2l linestart":
            return f"{max(blocks - 1, 1)}.0"
        return f"{blocks}.0"

    def delete(self, _start, _end):
        text = self.text_edit.toPlainText().splitlines()
        if text:
            text = text[:-1]
        self.text_edit.setPlainText("\n".join(text) + ("\n" if text else ""))
        self.see("end")


class ClickableFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
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
    log = Signal(str)
    status = Signal(str)

    def __init__(self, selected, ask_close_retry, parent=None):
        super().__init__(parent)
        self.selected = selected
        self.ask_close_retry = ask_close_retry
        self.cancelled = False
        self.current_process = None
        self.text_adapter = None

    def cancel(self):
        self.cancelled = True
        try:
            if self.current_process and self.current_process.poll() is None:
                self.current_process.terminate()
        except Exception:
            pass

    def run(self):
        self.text_adapter = QtTextAdapter(self.parent().text_log)
        results = []

        def set_current_process(proc):
            self.current_process = proc

        total = len(self.selected)
        for idx, pkg in enumerate(self.selected, start=1):
            if self.cancelled:
                self.log.emit(T("log_operation_cancelled"))
                break

            self.status.emit(T("status_updating_item", index=idx, total=total, name=pkg["Name"]))
            self.log.emit(T("log_update_item", index=idx, total=total, name=pkg["Name"], version=pkg["Version"], available=pkg["Available"], id=pkg["Id"]))

            running = get_running_process_hints(pkg["Id"])
            if running:
                self.log.emit(T("log_blocking_processes", processes=", ".join(running)))

            can_upgrade, pre_status, pre_output = precheck_upgrade(pkg)
            if not can_upgrade:
                if pre_status in ("no_longer_pending", "not_applicable", "not_found"):
                    mapping = {
                        "no_longer_pending": (T("log_skip_no_longer_pending"), T("reason_no_longer_pending")),
                        "not_applicable": (T("log_skip_not_applicable"), T("reason_not_applicable")),
                        "not_found": (T("log_skip_not_found"), T("reason_not_found")),
                    }
                    msg, reason = mapping[pre_status]
                    self.log.emit(msg)
                    result = {"status": pre_status, "pkg": pkg, "log": None, "reason": reason, "returncode": 0, "raw_output": pre_output}
                    results.append(result)
                    self.package_done.emit(result)
                    continue

            result = perform_upgrade_attempt(pkg, self.text_adapter, type("CancelFlag", (), {"get": lambda _self: self.cancelled})(), set_current_process, use_exact=True)

            if result["status"] == "updated":
                self.log.emit(T("log_updated"))
            elif result["status"] == "updated_restart_required":
                self.log.emit(T("log_updated_restart_required"))
            elif result["status"] == "no_longer_pending":
                self.log.emit(T("log_resolved_no_longer_pending"))
            elif result["status"] == "already_installed":
                self.log.emit(T("log_resolved_already_installed"))
            elif result["status"] == "different_install_technology":
                self.log.emit(T("log_resolved_different_tech"))

            if (
                not pkg.get("RequiresExplicitTarget")
                and result["status"] in ("not_applicable", "not_found", "no_longer_pending")
                and should_retry_without_exact(result)
            ):
                self.log.emit(T("log_retry_without_exact"))
                retry_no_exact = perform_upgrade_attempt(pkg, self.text_adapter, type("CancelFlag", (), {"get": lambda _self: self.cancelled})(), set_current_process, use_exact=False)
                if retry_no_exact["status"] != "cancelled":
                    retry_no_exact["raw_output"] = (
                        "===== FIRST ATTEMPT (--exact) =====\n"
                        + (result.get("raw_output") or "")
                        + "\n===== RETRY WITHOUT --exact =====\n"
                        + (retry_no_exact.get("raw_output") or "")
                    )
                    result = retry_no_exact

            if result["status"] == "cancelled":
                self.log.emit(T("log_cancelled"))
                results.append(result)
                self.package_done.emit(result)
                self.finished_summary.emit(results)
                return

            running_after_fail = get_running_process_hints(pkg["Id"])
            if should_offer_close_retry(result, running_after_fail):
                procs_txt = ", ".join(running_after_fail)
                if self.ask_close_retry(pkg["Name"], procs_txt):
                    self.log.emit(T("log_closing_processes", processes=procs_txt))
                    for kr in kill_processes(running_after_fail):
                        self.log.emit(T("log_process_closed", process=kr["process"]) if kr["ok"] else T("log_process_not_closed", process=kr["process"]))
                    time.sleep(1.5)
                    self.log.emit(T("log_retry_once"))
                    retry_result = perform_upgrade_attempt(pkg, self.text_adapter, type("CancelFlag", (), {"get": lambda _self: self.cancelled})(), set_current_process)
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
        self.setMinimumSize(1040, 720)
        self.pkgs = []
        self.loader_thread = None
        self.update_thread = None
        self.current_lang = I18N_OBJ.lang
        self._build_ui()
        self.refresh_list_async(initial=True)

    def _build_ui(self):
        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        left = QVBoxLayout()
        hero = QLabel(T("app_name"))
        hero.setObjectName("hero")
        hero.setAttribute(Qt.WA_StyledBackground, False)
        self.subtitle = QLabel(T("subtitle_detected"))
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setAttribute(Qt.WA_StyledBackground, False)
        left.addWidget(hero)
        left.addWidget(self.subtitle)
        header.addLayout(left, 1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.btn_refresh = QPushButton(T("btn_refresh"))
        self.btn_refresh.setMinimumWidth(108)
        self.btn_save = QPushButton(T("btn_save_log"))
        self.btn_save.setMinimumWidth(122)
        self.btn_toggle_log = QPushButton(T("btn_show_log"))
        self.btn_toggle_log.setMinimumWidth(122)
        self.btn_update = QPushButton(T("btn_update_selected", count=0))
        self.btn_update.setObjectName("primaryButton")
        self.btn_update.setMinimumWidth(238)
        actions.addWidget(self.btn_refresh)
        actions.addWidget(self.btn_save)
        actions.addWidget(self.btn_toggle_log)
        actions.addWidget(self.btn_update)
        header.addLayout(actions)
        root.addLayout(header)

        stats = QGridLayout()
        self.stat_total = self._make_stat("0", T("stats_available"))
        self.stat_selected = self._make_stat("0", T("stats_selected"))
        self.stat_special = self._make_stat("0", T("stats_special"))
        stats.addWidget(self.stat_total[0], 0, 0)
        stats.addWidget(self.stat_selected[0], 0, 1)
        stats.addWidget(self.stat_special[0], 0, 2)
        root.addLayout(stats)

        toolbar_frame = QFrame(objectName="surface")
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(12, 10, 12, 10)
        toolbar.setSpacing(10)
        toolbar.addWidget(QLabel(T("label_search")))
        self.search = QLineEdit()
        self.search.setPlaceholderText(T("search_placeholder"))
        self.search.setMinimumWidth(360)
        toolbar.addWidget(self.search, 1)
        self.lbl_view = QLabel(T("label_view"))
        toolbar.addWidget(self.lbl_view)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([T("filter_all"), T("filter_selected"), T("filter_explicit"), T("filter_unknown")])
        self.filter_combo.setMinimumWidth(132)
        toolbar.addWidget(self.filter_combo)
        self.lbl_language = QLabel(T("label_language"))
        toolbar.addWidget(self.lbl_language)
        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumWidth(132)
        toolbar.addWidget(self.lang_combo)
        self.btn_all = QPushButton(T("btn_select_all"))
        self.btn_all.setMinimumWidth(140)
        self.btn_none = QPushButton(T("btn_select_none"))
        self.btn_none.setMinimumWidth(140)
        toolbar.addWidget(self.btn_all)
        toolbar.addWidget(self.btn_none)
        root.addWidget(toolbar_frame)

        self.headline = QLabel(T("headline_loading"))
        self.headline.setObjectName("headline")
        self.headline.setAttribute(Qt.WA_StyledBackground, False)
        root.addWidget(self.headline)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget(objectName="scrollContent")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(8)
        self.scroll_area.setWidget(self.scroll_content)
        root.addWidget(self.scroll_area, 1)

        footer_frame = QFrame()
        footer_frame.setStyleSheet("background: transparent; border: none;")
        footer_grid = QGridLayout(footer_frame)
        footer_grid.setContentsMargins(0, 0, 0, 0)
        footer_grid.setHorizontalSpacing(14)
        footer_grid.setVerticalSpacing(6)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(18)
        self.progress.setStyleSheet(
            "QProgressBar { background-color:#204851; border:1px solid #586e75; border-radius:8px; }"
            "QProgressBar::chunk { background-color:#2aa198; border-radius:7px; }"
        )
        footer_grid.addWidget(self.progress, 0, 0)

        self.btn_cancel = QPushButton(T("btn_cancel_update"))
        self.btn_cancel.setObjectName("dangerButton")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setMinimumWidth(190)
        self.btn_cancel.setFixedHeight(42)
        self.btn_cancel.setStyleSheet(
            "QPushButton { background-color:#dc322f; color:#fdf6e3; border:1px solid #dc322f; border-radius:8px; padding:7px 12px; }"
            "QPushButton:hover { background-color:#e45451; }"
            "QPushButton:pressed { background-color:#b92c2a; }"
            "QPushButton:disabled { background-color:#8b3a3a; color:#f3d9d6; border:1px solid #a24a4a; }"
        )
        footer_grid.addWidget(self.btn_cancel, 0, 1, alignment=Qt.AlignVCenter)

        self.footer_status = QLabel(T("status_ready"))
        self.footer_status.setObjectName("muted")
        self.footer_status.setAttribute(Qt.WA_StyledBackground, False)
        footer_grid.addWidget(self.footer_status, 1, 0, 1, 2)
        footer_grid.setColumnStretch(0, 1)
        footer_grid.setColumnStretch(1, 0)
        root.addWidget(footer_frame)

        self.log_panel = QFrame(objectName="surface")
        log_layout = QVBoxLayout(self.log_panel)
        log_layout.setContentsMargins(12, 12, 12, 12)
        log_layout.addWidget(QLabel(T("log_title")))
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setMinimumHeight(180)
        log_layout.addWidget(self.text_log)
        self.log_panel.hide()
        root.addWidget(self.log_panel)

        self.btn_refresh.clicked.connect(lambda: self.refresh_list_async(initial=False))
        self.btn_save.clicked.connect(self.save_log)
        self.btn_toggle_log.clicked.connect(self.toggle_log)
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
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        v = QLabel(value)
        v.setObjectName("statValue")
        v.setAttribute(Qt.WA_StyledBackground, False)
        t = QLabel(label)
        t.setObjectName("statLabel")
        t.setAttribute(Qt.WA_StyledBackground, False)
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
        self.text_log.moveCursor(QTextCursor.End)
        self.text_log.insertPlainText(msg if msg.endswith("\n") else msg + "\n")
        self.text_log.moveCursor(QTextCursor.End)

    def set_status(self, msg):
        self.footer_status.setText(msg)

    def toggle_log(self):
        visible = not self.log_panel.isVisible()
        self.log_panel.setVisible(visible)
        self.btn_toggle_log.setText(T("btn_hide_log") if visible else T("btn_show_log"))

    def change_language(self):
        code = self.lang_combo.currentData()
        if not code or code == self.current_lang:
            return
        self.current_lang = code
        I18N_OBJ.set_language(code)
        self.retranslate_ui()

    def retranslate_ui(self):
        self.setWindowTitle(T("app_title", version=APP_VERSION))
        self.subtitle.setText(T("subtitle_detected") if self.pkgs else T("subtitle_up_to_date"))
        self.btn_refresh.setText(T("btn_refresh"))
        self.btn_save.setText(T("btn_save_log"))
        self.btn_toggle_log.setText(T("btn_hide_log") if self.log_panel.isVisible() else T("btn_show_log"))
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
        for widget in (self.btn_refresh, self.btn_save, self.btn_update, self.btn_all, self.btn_none, self.search, self.filter_combo):
            widget.setEnabled(enabled)

    def visible_items(self):
        q = self.search.text().strip().lower()
        mode = self.filter_combo.currentText().strip().lower() or "all"
        items = []
        for pkg in self.pkgs:
            haystack = " ".join([pkg.get("Name", ""), pkg.get("Id", ""), pkg.get("Version", ""), pkg.get("Available", ""), pkg.get("Source", "")]).lower()
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
        self.headline.setText(T("headline_visible_detected", visible=visible_count, total=len(self.pkgs)) if self.pkgs else T("headline_none"))
        self.subtitle.setText(T("subtitle_detected") if self.pkgs else T("subtitle_up_to_date"))
        self.btn_update.setText(T("btn_update_selected", count=selected_count))

    def clear_scroll(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def make_chip(self, text, warn=False):
        label = QLabel(text)
        if warn:
            label.setStyleSheet("background:#5b4600;color:#fdf6e3;border-radius:8px;padding:2px 7px;font-size:8.5pt;")
        else:
            label.setStyleSheet("background:#09414f;color:#93a1a1;border-radius:8px;padding:2px 7px;font-size:8.5pt;")
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
        card = QFrame(objectName="card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        t = QLabel(title)
        t.setStyleSheet("font-weight:600;color:#eee8d5;")
        s = QLabel(subtitle)
        s.setObjectName("muted")
        layout.addWidget(t)
        layout.addWidget(s)
        return card

    def _package_card(self, pkg):
        card = ClickableFrame(objectName="card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        checkbox = QCheckBox()
        checkbox.setChecked(pkg.get("_selected", True))
        checkbox.stateChanged.connect(lambda state, p=pkg: self.on_pkg_checked(p, state))
        layout.addWidget(checkbox, 0, Qt.AlignTop)
        card.clicked.connect(lambda p=pkg, cb=checkbox: self.toggle_pkg_from_row(p, cb))

        main = QVBoxLayout()
        main.setSpacing(3)
        name = QLabel(pkg["Name"])
        name.setStyleSheet("font-weight:600;color:#eee8d5;font-size:10pt;background:transparent;border:none;")
        name.setAttribute(Qt.WA_StyledBackground, False)
        pkg_id = QLabel(pkg["Id"])
        pkg_id.setObjectName("pkgId")
        pkg_id.setAttribute(Qt.WA_StyledBackground, False)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        meta = QLabel(f"{pkg['Version']}  →  {pkg['Available']}   ·   {pkg.get('Source', '') or T('unknown_source')}")
        meta.setObjectName("pkgMeta")
        meta.setAttribute(Qt.WA_StyledBackground, False)
        meta_row.addWidget(meta)
        if pkg.get("RequiresExplicitTarget"):
            meta_row.addWidget(self.make_chip(T("chip_explicit")))
        if (pkg.get("Version") or "").strip().lower() in ("unknown", "desconocida", ""):
            meta_row.addWidget(self.make_chip(T("chip_unknown"), warn=True))
        meta_row.addStretch(1)

        main.addWidget(name)
        main.addWidget(pkg_id)
        main.addLayout(meta_row)
        layout.addLayout(main, 1)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        btn_mark = QPushButton(T("btn_mark"))
        btn_mark.setMinimumWidth(72)
        btn_mark.setFixedHeight(34)
        btn_unmark = QPushButton(T("btn_unmark"))
        btn_unmark.setMinimumWidth(72)
        btn_unmark.setFixedHeight(34)
        btn_mark.clicked.connect(lambda: self.set_one_selected(pkg, True))
        btn_unmark.clicked.connect(lambda: self.set_one_selected(pkg, False))
        actions.addWidget(btn_mark)
        actions.addWidget(btn_unmark)
        layout.addLayout(actions)
        return card

    def on_pkg_checked(self, pkg, state):
        pkg["_selected"] = state == Qt.Checked
        self.update_summary_ui()

    def toggle_pkg_from_row(self, pkg, checkbox):
        checkbox.blockSignals(True)
        checkbox.setChecked(not checkbox.isChecked())
        checkbox.blockSignals(False)
        pkg["_selected"] = checkbox.isChecked()
        self.update_summary_ui()

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

    def ask_close_retry(self, name, procs_txt):
        return QMessageBox.question(
            self,
            T("retry_close_title"),
            T("retry_close_prompt", name=name, processes=procs_txt),
        ) == QMessageBox.Yes

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
        self.update_thread = UpdateThread(selected, self.ask_close_retry, self)
        self.update_thread.log.connect(self.append_log)
        self.update_thread.status.connect(self.set_status)
        self.update_thread.package_done.connect(lambda _r: self.progress.setValue(self.progress.value() + 1))
        self.update_thread.finished_summary.connect(self.on_update_finished)
        self.update_thread.start()

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
            QMessageBox.warning(self, T("complete_with_issues_title"), body)
        else:
            QMessageBox.information(self, T("complete_title"), body)


def build_gui():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(SOLARIZED_DARK_QSS)
    window = MainWindow()
    window.show()
    app.exec()
