# winget_updater_tk.py
import webbrowser, tempfile
import subprocess, tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import re, json, threading, ctypes, sys, os

# ===== Escalada de privilegios (UAC) =====
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def ensure_admin():
    if is_admin():
        return
    # Relanza con privilegios elevados
    if getattr(sys, "frozen", False):
        # Ejecutable compilado (PyInstaller)
        exe = sys.executable
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        cwd = os.getcwd()
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1)
    else:
        # Script .py
        exe = sys.executable
        script = os.path.abspath(__file__)
        params = f'"{script}" ' + " ".join(f'"{a}"' for a in sys.argv[1:])
        cwd = os.getcwd()
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1)
    sys.exit(0)

def save_log(text_widget):
    path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Texto", "*.txt")])
    if not path:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(text_widget.get("1.0", tk.END))
    messagebox.showinfo("Guardado", f"Log guardado en:\n{path}")

# ===== winget install if not exists =====
def has_winget():
    try:
        r = subprocess.run(["winget", "-v"], capture_output=True, text=True)
        return r.returncode == 0 and bool(r.stdout.strip())
    except FileNotFoundError:
        return False

def try_install_winget(text_widget=None):
    """
    Intenta instalar winget descargando el App Installer desde aka.ms/getwinget.
    Si falla (dependencias UI.Xaml/VCLibs), abre la Microsoft Store como fallback.
    Devuelve True si tras el proceso winget está disponible.
    """
    def log(msg):
        if text_widget:
            text_widget.insert(tk.END, msg + ("\n" if not msg.endswith("\n") else ""))
            text_widget.see(tk.END)
        else:
            print(msg)

    log("⚠ winget no está disponible. Intentando instalar Microsoft App Installer (winget)...")

    # Descarga del bundle oficial (redirige a la última versión)
    bundle_path = os.path.join(tempfile.gettempdir(), "AppInstaller.msixbundle")
    ps = [
        "powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "Invoke-WebRequest -Uri https://aka.ms/getwinget -OutFile '{}' -UseBasicParsing".format(bundle_path)
    ]
    r = subprocess.run(ps, capture_output=True, text=True)
    if r.returncode != 0:
        log("No se pudo descargar el instalador automáticamente.\nAbriendo Microsoft Store…")
        webbrowser.open("ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1")
        return False

    # Instalación del bundle
    ps_install = [
        "powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "Try { Add-AppxPackage -Path '{}' -ForceApplicationShutdown -ForceUpdateFromAnyVersion -Verbose; exit 0 } Catch { $_ | Out-String; exit 1 }".format(bundle_path)
    ]
    r2 = subprocess.run(ps_install, capture_output=True, text=True)
    if r2.returncode != 0:
        log("La instalación silenciosa falló (posibles dependencias Microsoft.UI.Xaml / VCLibs).\nAbriendo Microsoft Store…")
        webbrowser.open("ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1")
        return False

    # Verificación final
    ok = has_winget()
    log("✅ winget instalado correctamente." if ok else "❌ winget sigue sin estar disponible.")
    return ok

def ensure_winget_available(text_widget):
    """
    Comprueba winget; si no está, pregunta al usuario e intenta instalarlo.
    Devuelve True si winget está listo; False si no.
    """
    if has_winget():
        return True
    resp = messagebox.askyesno(
        "Instalar winget",
        "Este equipo no tiene winget.\n¿Quieres que intente instalarlo automáticamente (App Installer)?"
    )
    if not resp:
        return False
    return try_install_winget(text_widget)

# ===== Helpers winget / GUI =====
def _hidden_startupinfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si

def run_hidden(cmd, **kwargs):
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return subprocess.run(
        cmd,
        startupinfo=si,
        creationflags=subprocess.CREATE_NO_WINDOW,
        **kwargs
    )

def run(cmd):
    try:
        r = run_hidden(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.stdout
    except Exception as e:
        return str(e)

def parse_winget_output():
    def call(scope):
        return run([
            "winget","upgrade",
            "--disable-interactivity",
            "--accept-source-agreements",
            "--scope", scope
        ]) or ""

    d = {}
    d.update(_parse_upgrade_table_by_columns(call("user")))
    d.update(_parse_upgrade_table_by_columns(call("machine")))

    # (opcional) filtra filas obviamente malas
    def looks_ver(v): return bool(re.match(r"^v?\d+(?:\.\d+){1,4}", v))
    out = [v for v in d.values() if looks_ver(v["Version"]) and looks_ver(v["Available"])]
    out = sorted(out, key=lambda x: x["Name"].lower())
    return out

def _parse_upgrade_table_by_columns(text: str):
    """
    Parser robusto por offsets de columnas para 'winget upgrade' localizado (ES/EN).
    Devuelve dict {Id: {Name, Id, Version, Available}}.
    """
    header_re = re.compile(
        r"^((Nombre|Name)\s+Id\s+(Versi[oó]n|Version)\s+(Disponible|Available)\s+(Origen|Source))",
        re.I
    )
    explicit_re = re.compile(r"^(Los siguientes paquetes tienen|The following packages have)", re.I)
    footer_re = re.compile(r"(actualizaciones disponibles|updates available)", re.I)

    lines = text.splitlines()
    # 1) localizar cabecera y offsets
    hdr_idx = None
    for i, ln in enumerate(lines):
        if header_re.search(ln):
            hdr_idx = i
            header_line = ln
            break
    if hdr_idx is None:
        return {}

    # calcula inicios de columnas por posiciones del header
    # (busca las palabras clave y usa sus índices)
    def col_start(word):
        m = re.search(re.escape(word), header_line, re.I)
        return m.start() if m else None

    starts = [
        0,
        col_start("Id"),
        col_start("Versión") or col_start("Version"),
        col_start("Disponible") or col_start("Available"),
        col_start("Origen") or col_start("Source"),
    ]
    # sanity: deben existir y estar en orden
    if any(s is None for s in starts) or sorted(starts) != starts:
        return {}

    # calcula cortes [s:e) de cada col
    cuts = [(starts[i], starts[i+1]) for i in range(len(starts)-1)] + [(starts[-1], None)]

    def slice_cols(s):
        cols = []
        for a, b in cuts:
            cols.append(s[a:b].rstrip() if b is not None else s[a:].rstrip())
        return cols  # [Name, Id, Version, Available, Source]

    pkgs = {}
    cur_name = None
    cur_row  = None

    # 2) recorre filas desde la primera línea bajo el separador de guiones
    # busca la línea de guiones (----) tras el header
    sep_idx = None
    for i in range(hdr_idx+1, len(lines)):
        if set(lines[i].strip()) <= set("-"):
            sep_idx = i
            break
    if sep_idx is None:
        return {}

    for ln in lines[sep_idx+1:]:
        s = ln.rstrip()
        if not s:
            continue
        if explicit_re.match(s):
            # cortamos antes del segundo bloque
            break
        if footer_re.search(s):
            # ignoramos pies
            continue
        if re.match(r"^\s*[-\\|/]\s*$", s):
            continue

        cols = slice_cols(s)
        # normaliza
        name, pid, inst, avail, src = [c.strip() for c in cols]

        if pid:
            # fila nueva o continuación ya resuelta
            if cur_row:
                # volcar pendiente
                pkgs[cur_row["Id"]] = cur_row
                cur_row = None
                cur_name = None

            cur_row = {"Name": name, "Id": pid, "Version": inst, "Available": avail} \
                      if name or pid else None
            cur_name = name or ""
        else:
            # continuación de nombre envuelto (Id vacío)
            if cur_row is not None:
                cur_name = (cur_name + " " + name).strip()
                cur_row["Name"] = cur_name

    # vuelca la última si quedó pendiente
    if cur_row:
        pkgs[cur_row["Id"]] = cur_row

    return pkgs

def update_packages(selected, text_widget, progress, on_pkg_done, on_all_done, cancel_flag, set_current_process):
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
                    end   = text_widget.index("end-1c")
                    text_widget.delete(start, end)
                    text_widget.insert(start, msg if msg.endswith("\n") else msg + "\n")
                text_widget.see(tk.END)
            except Exception:
                text_widget.insert(tk.END, msg if msg.endswith("\n") else msg + "\n")
                text_widget.see(tk.END)
        text_widget.after(0, _do)

    RE_FAILS = [
        r'Error del instalador', r'Installer error',
        r'operaci[oó]n.*fall[oó]', r'failed\b',
        r'different install technology', r'tecnolog[ií]a de instalaci[oó]n.*diferente',
        r'Desinstale el paquete e instale', r'Uninstall the package and install',
    ]

    for pkg in selected:
        if cancel_flag.get():
            ui_print("⛔ Operación cancelada por el usuario.\n")
            break

        update_packages._printed_progress = False
        ui_print(f"🔄 {pkg['Name']} ({pkg['Version']} → {pkg['Available']}) [{pkg['Id']}]")

        cmd = ["winget", "upgrade", "--id", pkg["Id"], "--silent",
               "--accept-package-agreements", "--accept-source-agreements"]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            startupinfo=_hidden_startupinfo(),
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        # ⬅️ expone el proceso actual para el botón "Cancelar"
        set_current_process(proc)

        failed = False
        reason = ""
        log_path = None

        for raw in proc.stdout:
            if cancel_flag.get():
                try:
                    proc.terminate()
                except Exception:
                    pass
                ui_print("⛔ Cancelado por el usuario.\n")
                on_all_done()
                return

            line = raw.rstrip("\r\n")
            if not line or re.match(r"^\s*[-\\|/]\s*$", line):
                continue

            # progreso (misma línea)
            is_size_prog = re.search(r'(\d+(?:\.\d+)?)\s*(KB|MB|GB)\s*/\s*(\d+(?:\.\d+)?)\s*(KB|MB|GB)', line, re.I)
            is_bar = re.match(r'^\s*[█▓▒░]+\s+\d', line)
            if is_size_prog or is_bar:
                if not getattr(update_packages, "_printed_progress", False):
                    ui_print(line); update_packages._printed_progress = True
                else:
                    ui_replace_last_line(line)
                continue

            # detectar ruta de log
            mlog = re.search(r'log[^:]*:\s*(.+WinGet-.*?\.log)', line, re.I)
            if mlog:
                log_path = mlog.group(1).strip()

            # detectar fallos por texto
            if any(re.search(pat, line, re.I) for pat in RE_FAILS):
                failed = True
                if not reason:
                    reason = line.strip()

            # filtra ruido de licencias y muestra el resto
            if not re.search(r'(licencia|license|Microsoft no es responsable)', line, re.I):
                ui_print(line)

        proc.wait()

        if proc.returncode and not failed:
            failed = True
            reason = reason or f"Proceso terminó con código {proc.returncode}"

        on_pkg_done(not failed, pkg, log_path, reason)

    on_all_done()

def build_gui():
    root = tk.Tk()
    def resource_path(relpath):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, relpath)

    # Intenta .ico; si falla, usa .png con iconphoto y guarda referencia
    try:
        root.iconbitmap(resource_path("winget_updater.ico"))
    except Exception:
        try:
            icon_png = tk.PhotoImage(file=resource_path("winget_updater.png"))
            root.iconphoto(True, icon_png)
            root._icon_ref = icon_png  # <<< evita que el GC lo elimine
        except Exception:
            pass
    root.title("Winget Updater (by Villeparamio)")
    root.geometry("1000x700")

    frame_top = ttk.Frame(root); frame_top.pack(fill=tk.X, pady=5)
    btn_all = ttk.Button(frame_top, text="Seleccionar todo")
    btn_none = ttk.Button(frame_top, text="Seleccionar nada")
    btn_refresh = ttk.Button(frame_top, text="Refrescar")
    btn_update = ttk.Button(frame_top, text="Actualizar seleccionados")
    btn_save = ttk.Button(frame_top, text="Guardar log")
    for b in (btn_all, btn_none, btn_refresh, btn_update, btn_save):
        b.pack(side=tk.LEFT, padx=5)
    btn_cancel = ttk.Button(frame_top, text="Cancelar actualización", state="disabled")
    btn_cancel.pack(side=tk.RIGHT, padx=5)

    # Label dinámico de estado/lista
    lbl_hint = ttk.Label(root, text="Cargando lista de programas...")
    lbl_hint.pack(fill=tk.X, padx=12, pady=(6, 0), anchor="w")

    # === Lista con canvas + scrollbar ===
    frame_list = ttk.Frame(root)
    frame_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    canvas = tk.Canvas(frame_list)
    vbar = ttk.Scrollbar(frame_list, orient="vertical", command=canvas.yview)
    scroll = ttk.Frame(canvas)

    scroll.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll, anchor="nw")
    canvas.configure(yscrollcommand=vbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)

    # 👇 NUEVO: contador entre la lista (arriba) y la consola (abajo)
    lbl_count = ttk.Label(root, text="")
    lbl_count.pack(fill=tk.X, padx=12, pady=(0, 0), anchor="w")

    # Consola/log
    text_log = scrolledtext.ScrolledText(root, height=12)
    text_log.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

    # helper para habilitar/deshabilitar botones
    def set_buttons_enabled(enabled: bool):
        state = "normal" if enabled else "disabled"
        for b in (btn_all, btn_none, btn_refresh, btn_update, btn_save):
            b.config(state=state)

    # al arrancar, deshabilitados
    set_buttons_enabled(False)

    progress = ttk.Progressbar(root, length=600, mode='determinate', maximum=100)
    progress.pack(pady=5)

    # estructura donde guardamos paquetes y checkboxes
    pkgs = []
    checks = []

    def render_list():
        # limpia la columna y vuelve a crear los checkboxes con pkgs
        for w in list(scroll.children.values()):
            w.destroy()
        checks.clear()

        # contador
        n = len(pkgs)
        if n == 0:
            lbl_hint.config(text="Todos los programas disponibles están actualizados.")
            lbl_count.config(text="Tienes 0 programas con actualización disponible")
            return

        lbl_hint.config(text="Seleccione los programas que desea actualizar:")
        lbl_count.config(text=f"Tienes {n} programa{'s' if n != 1 else ''} con actualización disponible")

        for pkg in pkgs:
            var = tk.BooleanVar(value=True)
            label = f"{pkg['Name']}  [{pkg['Id']}]  {pkg['Version']} → {pkg['Available']}"
            ttk.Checkbutton(scroll, text=label, variable=var).pack(anchor="w")
            checks.append((var, pkg))

    def refresh_list_async():
        set_buttons_enabled(False)
        text_log.insert(tk.END, "Actualizando listado...\n"); text_log.see(tk.END)
        def refresh_task():
            new_pkgs = parse_winget_output() or []
            def apply():
                pkgs.clear()
                pkgs.extend(new_pkgs)
                render_list()
                set_buttons_enabled(True)
                text_log.insert(tk.END, "Listado actualizado.\n"); text_log.see(tk.END)
            root.after(0, apply)
        threading.Thread(target=refresh_task, daemon=True).start()

    # --- INIT EN BACKGROUND ---
    text_log.insert(tk.END, "Inicializando...\n"); text_log.see(tk.END)

    def init_task():
        # 1) comprobar winget (en segundo plano solo la parte pesada)
        def proceed_after_install(ok: bool):
            if not ok:
                messagebox.showerror("Falta winget", "No se pudo instalar/activar winget. Abre la Microsoft Store e instala 'App Installer'.")
                return
            # 2) obtener listado
            lbl_hint.config(text="Cargando lista de programas...")
            text_log.insert(tk.END, "Obteniendo lista de paquetes...\n"); text_log.see(tk.END)
            def fetch_task():
                new_pkgs = parse_winget_output() or []
                def apply():
                    pkgs.clear()
                    pkgs.extend(new_pkgs)
                    render_list()
                    set_buttons_enabled(True)
                    text_log.insert(tk.END, "Listo.\n"); text_log.see(tk.END)
                root.after(0, apply)
            threading.Thread(target=fetch_task, daemon=True).start()

        # Primero, comprobar winget sin bloquear UI:
        if has_winget():
            root.after(0, lambda: proceed_after_install(True))
        else:
            # Preguntar SIEMPRE en el hilo principal:
            def ask_install():
                resp = messagebox.askyesno(
                    "Instalar winget",
                    "Este equipo no tiene winget.\n¿Quieres que intente instalarlo automáticamente (App Installer)?"
                )
                if not resp:
                    proceed_after_install(False)
                    return
                # Instalar en background y luego continuar:
                def do_install():
                    ok = try_install_winget(text_log)
                    root.after(0, lambda: proceed_after_install(ok))
                threading.Thread(target=do_install, daemon=True).start()
            root.after(0, ask_install)

    threading.Thread(target=init_task, daemon=True).start()

    btn_all.config(command=lambda: [var.set(True) for var,_ in checks])
    btn_none.config(command=lambda: [var.set(False) for var,_ in checks])

    cancel_flag = tk.BooleanVar(value=False)
    current_process = None

    def set_current_process(proc):
        nonlocal current_process
        current_process = proc

    def do_update():
        selected = [p for v,p in checks if v.get()]
        if not selected:
            messagebox.showinfo("Nada seleccionado", "No has seleccionado ningún paquete.")
            return

        results = []  # guardará dicts {ok, pkg, log}

        cancel_flag.set(False)
        btn_cancel.config(state="normal")

        set_buttons_enabled(False)
        progress.config(mode='determinate', maximum=len(selected), value=0)

        def on_pkg_done(ok, pkg, log_path, reason):
            progress.after(0, lambda: progress.config(value=progress['value'] + 1))
            results.append({"ok": ok, "pkg": pkg, "log": log_path, "reason": reason})

        def on_all_done():
            def done_ui():
                # prepara resumen
                oks   = [r for r in results if r["ok"]]
                fails = [r for r in results if not r["ok"]]

                if fails:
                    title = "Finalizado con errores"  # <<< faltaba
                    body = (
                        f"Actualizados: {len(oks)}/{len(results)}\n\nFallidos:\n" +
                        "\n".join(
                            f"- {r['pkg']['Name']} [{r['pkg']['Id']}]\n"
                            f"  Motivo: {r.get('reason','(desconocido)')}"
                            + (f"\n  Log: {r['log']}" if r.get('log') else "")
                            for r in fails
                        )
                    )
                    show = lambda: messagebox.showwarning(title, body)
                else:
                    title = "Completado"
                    body  = f"Actualizados: {len(oks)}/{len(results)}"
                    show  = lambda: messagebox.showinfo(title, body)

                # limpia barra y REFRESCA YA (esto repintará la lista y reactivará botones)
                progress.config(value=0)
                refresh_list_async()

                # muestra el messagebox DESPUÉS de refrescar
                root.after(200, show)   # 200 ms suele bastar para que el UI pinte el refresh

                btn_cancel.config(state="disabled")

            progress.after(0, done_ui)

        threading.Thread(
            target=lambda: update_packages(
                selected, text_log, progress, on_pkg_done, on_all_done, cancel_flag, set_current_process
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

    # engancha el botón de cancelar a su handler
    btn_cancel.config(command=cancel_update)

    btn_update.config(command=do_update)
    btn_refresh.config(command=refresh_list_async)
    btn_save.config(command=lambda: save_log(text_log))

    root.mainloop()

if __name__ == "__main__":
    ensure_admin()   # <<< importante
    build_gui()