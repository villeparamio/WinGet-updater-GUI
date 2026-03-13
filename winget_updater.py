import re
import os
import sys
import ctypes
import tempfile
import threading
import webbrowser
import subprocess
import tkinter as tk
from process_hints import PROCESS_HINTS
from tkinter import ttk, messagebox, scrolledtext, filedialog

APP_VERSION = "v1.1"

# =========================
# Privilegios
# =========================

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
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1)
    else:
        exe = sys.executable
        script = os.path.abspath(__file__)
        params = f'"{script}" ' + " ".join(f'"{a}"' for a in sys.argv[1:])
        cwd = os.getcwd()
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1)

    sys.exit(0)


# =========================
# Utilidades GUI / log
# =========================

def save_log(text_widget):
    path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Texto", "*.txt")]
    )
    if not path:
        return

    with open(path, "w", encoding="utf-8") as f:
        f.write(text_widget.get("1.0", tk.END))

    messagebox.showinfo("Guardado", f"Log guardado en:\n{path}")


def _hidden_startupinfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    return si


def run_hidden(cmd, **kwargs):
    return subprocess.run(
        cmd,
        startupinfo=_hidden_startupinfo(),
        creationflags=subprocess.CREATE_NO_WINDOW,
        **kwargs
    )


def run(cmd):
    try:
        r = run_hidden(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return r.stdout or ""
    except Exception as e:
        return str(e)

def kill_process(image_name):
    try:
        r = run_hidden(
            ["taskkill", "/F", "/IM", image_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, str(e)


def kill_processes(process_names):
    results = []
    for p in process_names:
        ok, out = kill_process(p)
        results.append({"process": p, "ok": ok, "output": out})
    return results


def should_offer_close_retry(result, running_processes):
    if not running_processes:
        return False

    if result.get("status") != "installer_failed":
        return False

    txt = (
        (result.get("raw_output") or "") + "\n" +
        (result.get("reason") or "")
    ).lower()

    patterns = [
        "otra aplicación está usando los archivos modificados por el instalador",
        "application is using the files modified by the installer",
        "salga de las aplicaciones e inténtelo de nuevo",
        "close the applications and try again",
        "código de salida: 6",
        "exit code: 6",
        "código de salida: 1",
        "exit code: 1",
        "error del instalador con el código de salida"
    ]

    return any(p in txt for p in patterns)

# =========================
# winget availability
# =========================

def has_winget():
    try:
        r = subprocess.run(["winget", "-v"], capture_output=True, text=True)
        return r.returncode == 0 and bool((r.stdout or "").strip())
    except FileNotFoundError:
        return False


def try_install_winget(text_widget=None):
    def log(msg):
        if text_widget:
            text_widget.insert(tk.END, msg + ("\n" if not msg.endswith("\n") else ""))
            text_widget.see(tk.END)
        else:
            print(msg)

    log("⚠ winget no está disponible. Intentando instalar Microsoft App Installer (winget)...")

    bundle_path = os.path.join(tempfile.gettempdir(), "AppInstaller.msixbundle")
    ps = [
        "powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "Invoke-WebRequest -Uri https://aka.ms/getwinget -OutFile '{}' -UseBasicParsing".format(bundle_path)
    ]
    r = subprocess.run(ps, capture_output=True, text=True)
    if r.returncode != 0:
        log("No se pudo descargar el instalador automáticamente. Abriendo Microsoft Store…")
        webbrowser.open("ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1")
        return False

    ps_install = [
        "powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "Try { Add-AppxPackage -Path '{}' -ForceApplicationShutdown -ForceUpdateFromAnyVersion -Verbose; exit 0 } Catch { $_ | Out-String; exit 1 }".format(bundle_path)
    ]
    r2 = subprocess.run(ps_install, capture_output=True, text=True)
    if r2.returncode != 0:
        log("La instalación silenciosa falló (posibles dependencias Microsoft.UI.Xaml / VCLibs). Abriendo Microsoft Store…")
        webbrowser.open("ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1")
        return False

    ok = has_winget()
    log("✅ winget instalado correctamente." if ok else "❌ winget sigue sin estar disponible.")
    return ok


# =========================
# Patrones y clasificación
# =========================

RE_SUCCESS = [
    r"Instalado correctamente",
    r"Se instaló correctamente",
    r"Successfully installed",
]

RE_RESTART_REQUIRED = [
    r"Reinicie la aplicación para completar la actualización",
    r"Restart the application to complete the upgrade",
]

RE_NOT_APPLICABLE = [
    r"No se ha encontrado ninguna actualización aplicable",
    r"No applicable upgrade found",
    r"does not apply to your system or requirements",
    r"no se aplica a su sistema o requisitos",
]

RE_NOT_FOUND = [
    r"No se encontró ningún paquete que coincida con los criterios de entrada",
    r"No package found matching input criteria",
    r"No installed package found matching input criteria",
]

RE_INSTALLER_FAILS = [
    r"Error del instalador",
    r"Installer error",
    r"operaci[oó]n.*fall[oó]",
    r"\bfailed\b",
    r"different install technology",
    r"tecnolog[ií]a de instalaci[oó]n.*diferente",
    r"Desinstale el paquete e instale",
    r"Uninstall the package and install",
    r"Otra aplicación está usando los archivos modificados por el instalador",
    r"application is using the files modified by the installer",
]

RE_ALREADY_NO_UPDATES = [
    r"No se ha encontrado ninguna actualización disponible",
    r"No available upgrade found",
    r"No hay versiones más recientes del paquete disponibles",
]

RE_PROGRESS_SIZE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(KB|MB|GB)\s*/\s*(\d+(?:\.\d+)?)\s*(KB|MB|GB)', re.I
)

RE_PROGRESS_BAR = re.compile(r'^\s*[█▓▒░]+\s+\d')
RE_SPINNER = re.compile(r'^\s*[-\\|/]\s*$')
RE_LOG_PATH = re.compile(r'log[^:]*:\s*(.+WinGet-.*?\.log)', re.I)


def matches_any(text, patterns):
    return any(re.search(p, text, re.I) for p in patterns)


def classify_winget_result(output: str, returncode: int):
    if matches_any(output, RE_SUCCESS) and matches_any(output, RE_RESTART_REQUIRED):
        return "updated_restart_required", "Actualizado correctamente; hay que reiniciar la aplicación"

    if matches_any(output, RE_SUCCESS):
        return "updated", "Actualizado correctamente"

    if matches_any(output, RE_NOT_APPLICABLE):
        return "not_applicable", "La actualización no aplica a este sistema o requisitos"

    if matches_any(output, RE_NOT_FOUND):
        return "not_found", "winget no encuentra un paquete instalado que coincida con el ID"

    if matches_any(output, RE_INSTALLER_FAILS):
        line = first_matching_line(output, RE_INSTALLER_FAILS)
        return "installer_failed", line or "Fallo del instalador"

    if matches_any(output, RE_ALREADY_NO_UPDATES):
        return "no_longer_pending", "Winget ya no considera este paquete pendiente de actualización"

    if returncode == 0:
        return "ok_but_unclear", "winget devolvió éxito pero la salida no es concluyente"

    return "failed", f"Proceso terminó con código {returncode}"


def first_matching_line(output: str, patterns):
    for line in output.splitlines():
        if matches_any(line, patterns):
            return line.strip()
    return ""

def should_retry_without_exact(result):
    txt = (
        (result.get("raw_output") or "") + "\n" +
        (result.get("reason") or "")
    ).lower()

    patterns = [
        "no se ha encontrado ninguna actualización disponible",
        "no hay versiones más recientes del paquete disponibles",
        "no applicable upgrade found",
        "no available upgrade found",
        "no package found matching input criteria",
        "no installed package found matching input criteria",
        "no se encontró ningún paquete que coincida con los criterios de entrada",
    ]

    return any(p in txt for p in patterns)

# =========================
# Detección de procesos abiertos
# =========================


def is_process_running(image_name):
    try:
        r = run_hidden(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        out = (r.stdout or "").lower()
        return image_name.lower() in out
    except Exception:
        return False


def get_running_process_hints(pkg_id):
    procs = PROCESS_HINTS.get(pkg_id, [])
    return [p for p in procs if is_process_running(p)]


# =========================
# Parseo de winget upgrade
# =========================

def parse_winget_output():
    out = run([
        "winget",
        "upgrade",
        "--include-unknown",
        "--accept-source-agreements",
        "--disable-interactivity"
    ]) or ""

    lines = out.splitlines()
    pkgs = []

    header_idx = None
    sep_idx = None

    # Buscar cabecera principal
    for i, line in enumerate(lines):
        if re.search(r'^(Nombre|Name)\s+', line, re.I) and re.search(r'\b(Id)\b', line, re.I):
            header_idx = i
            break

    if header_idx is None:
        return []

    # Buscar línea de separación ------
    for i in range(header_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped and set(stripped) <= {"-"}:
            sep_idx = i
            break

    if sep_idx is None:
        return []

    header_line = lines[header_idx]

    # Sacar posiciones de columnas según la cabecera visible
    def find_col(patterns):
        for p in patterns:
            m = re.search(p, header_line, re.I)
            if m:
                return m.start()
        return None

    pos_id = find_col([r"\bId\b"])
    pos_version = find_col([r"Versi[oó]n", r"\bVersion\b"])
    pos_available = find_col([r"Disponible", r"\bAvailable\b"])
    pos_source = find_col([r"Origen", r"\bSource\b"])

    if None in (pos_id, pos_version, pos_available, pos_source):
        return []

    # Leer solo la tabla principal, hasta la siguiente sección explicativa
    for line in lines[sep_idx + 1:]:
        s = line.rstrip()
        if not s:
            continue

        low = s.lower()

        # Fin de la tabla principal
        if (
            low.startswith("los siguientes paquetes tienen una actualización disponible")
            or low.startswith("the following packages have an upgrade available")
            or "requieren un destino explícito" in low
            or "require explicit targeting" in low
            or "paquete(s) tienen números de versión" in low
            or "packages have version numbers that cannot be determined" in low
            or "paquetes están anclados" in low
            or "packages are pinned" in low
            or re.match(r'^\d+\s+actualizaciones disponibles', low)
            or re.match(r'^\d+\s+upgrades available', low)
        ):
            break

        # Saltar separadores raros
        if re.match(r'^\s*[-\\|/]\s*$', s):
            continue

        # Cortes por columnas
        name = s[:pos_id].rstrip()
        pid = s[pos_id:pos_version].rstrip()
        installed = s[pos_version:pos_available].rstrip()
        available = s[pos_available:pos_source].rstrip()
        source = s[pos_source:].rstrip()

        name = name.strip()
        pid = pid.strip()
        installed = installed.strip()
        available = available.strip()
        source = source.strip()

        if not pid or not available:
            continue

        pkgs.append({
            "Name": name,
            "Id": pid,
            "Version": installed if installed else "Unknown",
            "Available": available,
            "Scope": "auto",
            "Source": source,
        })

    # Deduplicado por ID
    dedup = {}
    for p in pkgs:
        dedup[p["Id"]] = p

    return sorted(dedup.values(), key=lambda x: x["Name"].lower())


# =========================
# Precheck
# =========================

def precheck_upgrade(pkg):
    cmd = [
        "winget",
        "upgrade",
        "--id", pkg["Id"],
        "--disable-interactivity",
        "--accept-source-agreements"
    ]

    if pkg_has_unknown_version(pkg):
        cmd.append("--include-unknown")

    out = run(cmd) or ""
    low = out.lower()

    if (
        "no se ha encontrado ninguna actualización disponible" in low or
        "no hay versiones más recientes del paquete disponibles" in low or
        "no available upgrade found" in low
    ):
        return False, "no_longer_pending", out

    if (
        "no applicable upgrade found" in low or
        "no se ha encontrado ninguna actualización aplicable" in low or
        "does not apply to your system or requirements" in low or
        "no se aplica a su sistema o requisitos" in low or
        "la configuración del sistema actual no admite la instalación de este paquete" in low or
        "the current system configuration is not supported by this package" in low
    ):
        return False, "not_applicable", out

    if (
        "no package found matching input criteria" in low or
        "no installed package found matching input criteria" in low or
        "no se encontró ningún paquete que coincida con los criterios de entrada" in low
    ):
        return False, "not_found", out

    return True, "upgradable", out

def pkg_has_unknown_version(pkg):
    v = (pkg.get("Version") or "").strip().lower()
    return v in ("unknown", "desconocida", "")

def perform_upgrade_attempt(pkg, text_widget, cancel_flag, set_current_process, use_exact=True):
    def ui_print(msg):
        text_widget.after(0, lambda: (
            text_widget.insert(tk.END, msg if msg.endswith("\n") else msg + "\n"),
            text_widget.see(tk.END)
        ))

    def ui_replace_last_line(msg):
        def _do():
            try:
                line_count = int(float(text_widget.index("end-1c").split(".")[0]))
                if line_count < 2:
                    text_widget.insert(tk.END, msg if msg.endswith("\n") else msg + "\n")
                else:
                    start = text_widget.index("end-2l linestart")
                    end = text_widget.index("end-1c")
                    text_widget.delete(start, end)
                    text_widget.insert(start, msg if msg.endswith("\n") else msg + "\n")
                text_widget.see(tk.END)
            except Exception:
                text_widget.insert(tk.END, msg if msg.endswith("\n") else msg + "\n")
                text_widget.see(tk.END)
        text_widget.after(0, _do)

    cmd = ["winget", "upgrade", "--id", pkg["Id"]]

    if use_exact:
        cmd.append("--exact")

    if pkg_has_unknown_version(pkg):
        cmd.append("--include-unknown")

    cmd += [
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements"
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=_hidden_startupinfo(),
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    set_current_process(proc)

    log_path = None
    output_lines = []
    printed_progress = False
    cancelled = False

    for raw in proc.stdout:
        if cancel_flag.get():
            try:
                proc.terminate()
            except Exception:
                pass
            cancelled = True
            break

        output_lines.append(raw)
        line = raw.rstrip("\r\n")

        if not line:
            continue
        if RE_SPINNER.match(line):
            continue

        if RE_PROGRESS_SIZE.search(line) or RE_PROGRESS_BAR.match(line):
            if not printed_progress:
                ui_print(line)
                printed_progress = True
            else:
                ui_replace_last_line(line)
            continue

        mlog = RE_LOG_PATH.search(line)
        if mlog:
            log_path = mlog.group(1).strip()

        if not re.search(r"(licencia|license|microsoft no es responsable)", line, re.I):
            ui_print(line)

    if cancelled:
        return {
            "status": "cancelled",
            "pkg": pkg,
            "log": log_path,
            "reason": "Cancelado por el usuario",
            "returncode": -1,
            "raw_output": "".join(output_lines),
        }

    proc.wait()
    full_output = "".join(output_lines)
    status, reason = classify_winget_result(full_output, proc.returncode)

    return {
        "status": status,
        "pkg": pkg,
        "log": log_path,
        "reason": reason,
        "returncode": proc.returncode,
        "raw_output": full_output,
    }

# =========================
# Actualización
# =========================

def update_packages(selected, text_widget, progress, on_pkg_done, on_all_done, cancel_flag, set_current_process, root):
    total = len(selected)

    def ui_print(msg):
        text_widget.after(0, lambda: (
            text_widget.insert(tk.END, msg if msg.endswith("\n") else msg + "\n"),
            text_widget.see(tk.END)
        ))

    def ask_yes_no(title, message):
        result = {"value": False}
        done = threading.Event()

        def _ask():
            result["value"] = messagebox.askyesno(title, message)
            done.set()

        root.after(0, _ask)
        done.wait()
        return result["value"]

    for idx, pkg in enumerate(selected, start=1):
        if cancel_flag.get():
            ui_print("⛔ Operación cancelada por el usuario.\n")
            break

        ui_print(f"[{idx}/{total}] 🔄 {pkg['Name']} ({pkg['Version']} → {pkg['Available']}) [{pkg['Id']}]")

        running = get_running_process_hints(pkg["Id"])
        if running:
            ui_print(f"⚠ Posibles procesos abiertos que pueden bloquear la instalación: {', '.join(running)}")

        can_upgrade, pre_status, pre_output = precheck_upgrade(pkg)

        if not can_upgrade:
            if pre_status == "no_longer_pending":
                ui_print("↪ Saltado: winget ya no lo considera pendiente de actualización.")
                on_pkg_done({
                    "status": "no_longer_pending",
                    "pkg": pkg,
                    "log": None,
                    "reason": "Winget ya no considera este paquete pendiente de actualización",
                    "returncode": 0,
                    "raw_output": pre_output,
                })
                continue

            if pre_status == "not_applicable":
                ui_print("↪ Saltado: la actualización no aplica actualmente a este sistema o instalación.")
                on_pkg_done({
                    "status": "not_applicable",
                    "pkg": pkg,
                    "log": None,
                    "reason": "La actualización no aplica actualmente",
                    "returncode": 0,
                    "raw_output": pre_output,
                })
                continue

            if pre_status == "not_found":
                ui_print("↪ Saltado: winget no localiza un paquete instalado que coincida con el ID.")
                on_pkg_done({
                    "status": "not_found",
                    "pkg": pkg,
                    "log": None,
                    "reason": "winget no encuentra coincidencia instalada para el ID",
                    "returncode": 0,
                    "raw_output": pre_output,
                })
                continue

        # Primer intento
        result = perform_upgrade_attempt(pkg, text_widget, cancel_flag, set_current_process, use_exact=True)

        if result["status"] in ("not_applicable", "not_found") and should_retry_without_exact(result):
            ui_print("↻ Reintentando sin --exact por posible problema de coincidencia estricta...")
            retry_no_exact = perform_upgrade_attempt(
                pkg, text_widget, cancel_flag, set_current_process, use_exact=False
            )

            if retry_no_exact["status"] != "cancelled":
                retry_no_exact["raw_output"] = (
                    "===== FIRST ATTEMPT (--exact) =====\n"
                    + (result.get("raw_output") or "")
                    + "\n===== RETRY WITHOUT --exact =====\n"
                    + (retry_no_exact.get("raw_output") or "")
                )
                result = retry_no_exact

        if result["status"] == "cancelled":
            ui_print("⛔ Cancelado por el usuario.\n")
            on_pkg_done(result)
            on_all_done()
            return

        # Si falla por archivos en uso, ofrecer cierre y reintento
        running_after_fail = get_running_process_hints(pkg["Id"])
        if should_offer_close_retry(result, running_after_fail):
            procs_txt = ", ".join(running_after_fail)
            resp = ask_yes_no(
                "Cerrar aplicación y reintentar",
                f"La actualización de:\n\n{pkg['Name']}\n\n"
                f"ha fallado porque hay archivos en uso.\n\n"
                f"Procesos detectados:\n{procs_txt}\n\n"
                f"Esto puede cerrar la aplicación de golpe y perder trabajo no guardado.\n\n"
                f"¿Quieres cerrar esos procesos y reintentar una vez?"
            )

            if resp:
                ui_print(f"⚠ Cerrando procesos para reintento: {procs_txt}")
                kill_results = kill_processes(running_after_fail)

                for kr in kill_results:
                    if kr["ok"]:
                        ui_print(f"   - Cerrado: {kr['process']}")
                    else:
                        ui_print(f"   - No se pudo cerrar: {kr['process']}")

                try:
                    import time
                    time.sleep(1.5)
                except Exception:
                    pass

                ui_print("🔁 Reintentando instalación una vez...")
                retry_result = perform_upgrade_attempt(pkg, text_widget, cancel_flag, set_current_process)

                if retry_result["status"] == "cancelled":
                    ui_print("⛔ Cancelado por el usuario.\n")
                    on_pkg_done(retry_result)
                    on_all_done()
                    return

                retry_result["raw_output"] = (
                    "===== FIRST ATTEMPT =====\n"
                    + (result.get("raw_output") or "")
                    + "\n===== RETRY ATTEMPT =====\n"
                    + (retry_result.get("raw_output") or "")
                )
                result = retry_result

        on_pkg_done(result)

    on_all_done()


# =========================
# GUI
# =========================

def build_gui():
    root = tk.Tk()

    style = ttk.Style()
    try:
        style.theme_use("vista")
    except Exception:
        try:
            style.theme_use("clam")
        except Exception:
            pass

    root.option_add("*Font", ("Segoe UI", 10))
    style.configure("TButton", padding=6)
    style.configure("TLabel", padding=2)
    style.configure("TCheckbutton", padding=2)

    def resource_path(relpath):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, relpath)

    try:
        root.iconbitmap(resource_path("winget_updater.ico"))
    except Exception:
        try:
            icon_png = tk.PhotoImage(file=resource_path("winget_updater.png"))
            root.iconphoto(True, icon_png)
            root._icon_ref = icon_png
        except Exception:
            pass

    root.title(f"Winget Updater {APP_VERSION} (by Villeparamio)")
    root.geometry("1100x760")
    root.minsize(900, 600)

    frame_top = ttk.Frame(root)
    frame_top.pack(fill=tk.X, pady=6, padx=8)

    btn_all = ttk.Button(frame_top, text="Seleccionar todo", width=18)
    btn_none = ttk.Button(frame_top, text="Seleccionar nada", width=18)
    btn_refresh = ttk.Button(frame_top, text="Refrescar", width=12)
    btn_update = ttk.Button(frame_top, text="Actualizar seleccionados", width=24)
    btn_save = ttk.Button(frame_top, text="Guardar log", width=14)

    for b in (btn_all, btn_none, btn_refresh, btn_update, btn_save):
        b.pack(side=tk.LEFT, padx=4)

    btn_cancel = ttk.Button(frame_top, text="Cancelar actualización", state="disabled", width=20)
    btn_cancel.pack(side=tk.RIGHT, padx=4)

    lbl_hint = ttk.Label(root, text="Cargando lista de programas...")
    lbl_hint.pack(fill=tk.X, padx=12, pady=(6, 0), anchor="w")

    frame_list = ttk.Frame(root)
    frame_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    canvas = tk.Canvas(frame_list, highlightthickness=0, bd=0)
    vbar = ttk.Scrollbar(frame_list, orient="vertical", command=canvas.yview)
    scroll = ttk.Frame(canvas)

    scroll_window = canvas.create_window((0, 0), window=scroll, anchor="nw")

    def _update_scrollregion(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _resize_inner_frame(event):
        canvas.itemconfigure(scroll_window, width=event.width)

    scroll.bind("<Configure>", _update_scrollregion)
    canvas.bind("<Configure>", _resize_inner_frame)
    canvas.configure(yscrollcommand=vbar.set)

    def _on_mousewheel_windows(event):
        canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_mousewheel_linux_up(event):
        canvas.yview_scroll(-1, "units")

    def _on_mousewheel_linux_down(event):
        canvas.yview_scroll(1, "units")

    def bind_mousewheel(_event=None):
        canvas.bind_all("<MouseWheel>", _on_mousewheel_windows)
        canvas.bind_all("<Button-4>", _on_mousewheel_linux_up)
        canvas.bind_all("<Button-5>", _on_mousewheel_linux_down)

    def unbind_mousewheel(_event=None):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", bind_mousewheel)
    canvas.bind("<Leave>", unbind_mousewheel)
    scroll.bind("<Enter>", bind_mousewheel)
    scroll.bind("<Leave>", unbind_mousewheel)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)

    lbl_count = ttk.Label(root, text="")
    lbl_count.pack(fill=tk.X, padx=12, pady=(0, 0), anchor="w")

    text_log = scrolledtext.ScrolledText(root, height=14, wrap=tk.WORD)
    text_log.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

    def set_buttons_enabled(enabled: bool):
        state = "normal" if enabled else "disabled"
        for b in (btn_all, btn_none, btn_refresh, btn_update, btn_save):
            b.config(state=state)

    set_buttons_enabled(False)

    progress = ttk.Progressbar(root, length=700, mode='determinate', maximum=100)
    progress.pack(pady=6, padx=10, fill=tk.X)

    pkgs = []
    checks = []
    current_process = None
    cancel_flag = tk.BooleanVar(value=False)

    def set_current_process(proc):
        nonlocal current_process
        current_process = proc

    def render_list():
        for w in list(scroll.children.values()):
            w.destroy()
        checks.clear()

        n = len(pkgs)
        if n == 0:
            lbl_hint.config(text="Todos los programas disponibles están actualizados.")
            lbl_count.config(text="Tienes 0 programas con actualización disponible")
            _update_scrollregion()
            return

        lbl_hint.config(text="Seleccione los programas que desea actualizar:")
        lbl_count.config(text=f"Tienes {n} programa{'s' if n != 1 else ''} con actualización disponible")

        for pkg in pkgs:
            var = tk.BooleanVar(value=True)
            label = f"{pkg['Name']}  [{pkg['Id']}]  {pkg['Version']} → {pkg['Available']}  [{pkg.get('Source','')}]"
            cb = ttk.Checkbutton(scroll, text=label, variable=var)
            cb.pack(anchor="w", fill=tk.X, padx=2, pady=1)
            cb.bind("<Enter>", bind_mousewheel)
            cb.bind("<Leave>", unbind_mousewheel)
            checks.append((var, pkg))

        _update_scrollregion()
        canvas.yview_moveto(0)

    def refresh_list_async():
        set_buttons_enabled(False)
        text_log.insert(tk.END, "Actualizando listado...\n")
        text_log.see(tk.END)

        def refresh_task():
            new_pkgs = parse_winget_output() or []

            def apply():
                pkgs.clear()
                pkgs.extend(new_pkgs)
                render_list()
                set_buttons_enabled(True)
                text_log.insert(tk.END, "Listado actualizado.\n")
                text_log.see(tk.END)

            root.after(0, apply)

        threading.Thread(target=refresh_task, daemon=True).start()

    text_log.insert(tk.END, "Inicializando...\n")
    text_log.see(tk.END)

    def init_task():
        def proceed_after_install(ok: bool):
            if not ok:
                messagebox.showerror(
                    "Falta winget",
                    "No se pudo instalar/activar winget. Abre la Microsoft Store e instala 'App Installer'."
                )
                return

            lbl_hint.config(text="Cargando lista de programas...")
            text_log.insert(tk.END, "Obteniendo lista de paquetes...\n")
            text_log.see(tk.END)

            def fetch_task():
                new_pkgs = parse_winget_output() or []

                def apply():
                    pkgs.clear()
                    pkgs.extend(new_pkgs)
                    render_list()
                    set_buttons_enabled(True)
                    text_log.insert(tk.END, "Listo.\n")
                    text_log.see(tk.END)

                root.after(0, apply)

            threading.Thread(target=fetch_task, daemon=True).start()

        if has_winget():
            root.after(0, lambda: proceed_after_install(True))
        else:
            def ask_install():
                resp = messagebox.askyesno(
                    "Instalar winget",
                    "Este equipo no tiene winget.\n¿Quieres que intente instalarlo automáticamente (App Installer)?"
                )
                if not resp:
                    proceed_after_install(False)
                    return

                def do_install():
                    ok = try_install_winget(text_log)
                    root.after(0, lambda: proceed_after_install(ok))

                threading.Thread(target=do_install, daemon=True).start()

            root.after(0, ask_install)

    threading.Thread(target=init_task, daemon=True).start()

    btn_all.config(command=lambda: [var.set(True) for var, _ in checks])
    btn_none.config(command=lambda: [var.set(False) for var, _ in checks])

    def do_update():
        selected = [p for v, p in checks if v.get()]
        if not selected:
            messagebox.showinfo("Nada seleccionado", "No has seleccionado ningún paquete.")
            return

        cancel_flag.set(False)
        btn_cancel.config(state="normal")
        set_buttons_enabled(False)
        progress.config(mode='determinate', maximum=len(selected), value=0)

        results = []

        def on_pkg_done(result):
            results.append(result)
            progress.after(0, lambda: progress.config(value=progress['value'] + 1))

        def on_all_done():
            def done_ui():
                updated = [r for r in results if r["status"] in ("updated", "updated_restart_required")]
                restart_required = [r for r in results if r["status"] == "updated_restart_required"]
                not_applicable = [r for r in results if r["status"] == "not_applicable"]
                not_found = [r for r in results if r["status"] == "not_found"]
                no_longer_pending = [r for r in results if r["status"] == "no_longer_pending"]
                installer_failed = [r for r in results if r["status"] == "installer_failed"]
                cancelled = [r for r in results if r["status"] == "cancelled"]
                failed = [r for r in results if r["status"] in ("failed", "ok_but_unclear")]

                resolved = updated + no_longer_pending                

                summary = []
                summary.append(f"Resueltos sin actualización pendiente: {len(resolved)}/{len(results)}")
                summary.append(f"Actualizados correctamente: {len(updated)}")

                if restart_required:
                    summary.append(f"Requieren reinicio de app: {len(restart_required)}")

                if not_applicable:
                    summary.append(f"No aplicables: {len(not_applicable)}")

                if no_longer_pending:
                    summary.append(f"Ya no pendientes en winget: {len(no_longer_pending)}")                

                if not_found:
                    summary.append(f"No encontrados por winget: {len(not_found)}")

                if installer_failed:
                    summary.append(f"Fallos de instalador: {len(installer_failed)}")

                if failed:
                    summary.append(f"Fallos genéricos: {len(failed)}")

                if cancelled:
                    summary.append(f"Cancelados: {len(cancelled)}")

                detail_blocks = []

                if installer_failed:
                    detail_blocks.append(
                        "Fallos de instalador:\n" + "\n".join(
                            f"- {r['pkg']['Name']} [{r['pkg']['Id']}] ({r['pkg']['Scope']})\n"
                            f"  Motivo: {r['reason']}" +
                            (f"\n  Log: {r['log']}" if r.get("log") else "")
                            for r in installer_failed
                        )
                    )

                if not_found:
                    detail_blocks.append(
                        "No encontrados por winget:\n" + "\n".join(
                            f"- {r['pkg']['Name']} [{r['pkg']['Id']}] ({r['pkg']['Scope']})"
                            for r in not_found
                        )
                    )

                if not_applicable:
                    detail_blocks.append(
                        "No aplicables:\n" + "\n".join(
                            f"- {r['pkg']['Name']} [{r['pkg']['Id']}] ({r['pkg']['Scope']})"
                            for r in not_applicable
                        )
                    )

                if no_longer_pending:
                    detail_blocks.append(
                        "Ya no pendientes en winget:\n" + "\n".join(
                            f"- {r['pkg']['Name']} [{r['pkg']['Id']}] ({r['pkg']['Scope']})"
                            for r in no_longer_pending
                        )
                    )                    

                if failed:
                    detail_blocks.append(
                        "Fallos genéricos:\n" + "\n".join(
                            f"- {r['pkg']['Name']} [{r['pkg']['Id']}] ({r['pkg']['Scope']})\n"
                            f"  Motivo: {r['reason']}"
                            for r in failed
                        )
                    )

                body = "\n".join(summary)
                if detail_blocks:
                    body += "\n\n" + "\n\n".join(detail_blocks)

                progress.config(value=0)
                refresh_list_async()
                btn_cancel.config(state="disabled")

                if installer_failed or failed:
                    root.after(200, lambda: messagebox.showwarning("Finalizado con incidencias", body))
                else:
                    root.after(200, lambda: messagebox.showinfo("Completado", body))

            progress.after(0, done_ui)

        threading.Thread(
            target=lambda: update_packages(
                selected=selected,
                text_widget=text_log,
                progress=progress,
                on_pkg_done=on_pkg_done,
                on_all_done=on_all_done,
                cancel_flag=cancel_flag,
                set_current_process=set_current_process,
                root=root
            ),
            daemon=True
        ).start()

    def cancel_update():
        cancel_flag.set(True)
        try:
            if current_process and current_process.poll() is None:
                current_process.terminate()
        except Exception:
            pass

        text_log.after(0, lambda: (
            text_log.insert(tk.END, "⛔ Cancelando actualización...\n"),
            text_log.see(tk.END)
        ))

    btn_cancel.config(command=cancel_update)
    btn_update.config(command=do_update)
    btn_refresh.config(command=refresh_list_async)
    btn_save.config(command=lambda: save_log(text_log))

    root.mainloop()


if __name__ == "__main__":
    ensure_admin()
    build_gui()