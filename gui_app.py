import os
import sys
import time
import ctypes
import tempfile
import threading
import webbrowser
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

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
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Error al elevar permisos",
                f"No se pudo solicitar privilegios de administrador. Código ShellExecuteW: {rc}\n\n"
                f"Ejecutable: {exe}\n"
                f"Parámetros: {params}"
            )
            root.destroy()
        except Exception:
            print(f"No se pudo solicitar privilegios de administrador. Código ShellExecuteW: {rc}")
            print(f"Ejecutable: {exe}")
            print(f"Parámetros: {params}")
        return

    sys.exit(0)


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
            extra = " [requiere destino explícito]" if pkg.get("RequiresExplicitTarget") else ""
            label = f"{pkg['Name']}  [{pkg['Id']}]  {pkg['Version']} → {pkg['Available']}  [{pkg.get('Source','')}]" + extra
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
                    f"Resueltos sin actualización pendiente: {len(resolved)}/{len(results)}",
                    f"Actualizados correctamente: {len(updated)}",
                ]

                if restart_required:
                    summary.append(f"Requieren reinicio de app: {len(restart_required)}")
                if already_installed:
                    summary.append(f"Ya estaban en la misma versión o una superior: {len(already_installed)}")
                if not_applicable:
                    summary.append(f"No aplicables: {len(not_applicable)}")
                if no_longer_pending:
                    summary.append(f"Ya no pendientes en winget: {len(no_longer_pending)}")
                if not_found:
                    summary.append(f"No encontrados por winget: {len(not_found)}")
                if different_install_technology:
                    summary.append(f"Requieren desinstalar e instalar de nuevo: {len(different_install_technology)}")
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
                if already_installed:
                    detail_blocks.append(
                        "Misma versión o superior ya instalada:\n" + "\n".join(
                            f"- {r['pkg']['Name']} [{r['pkg']['Id']}] ({r['pkg']['Scope']})"
                            for r in already_installed
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
                if different_install_technology:
                    detail_blocks.append(
                        "Requieren desinstalar e instalar de nuevo:\n" + "\n".join(
                            f"- {r['pkg']['Name']} [{r['pkg']['Id']}] ({r['pkg']['Scope']})\n"
                            f"  Motivo: {r['reason']}"
                            for r in different_install_technology
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

        def update_packages():
            total = len(selected)

            def ui_print(msg):
                text_log.after(0, lambda: (
                    text_log.insert(tk.END, msg if msg.endswith("\n") else msg + "\n"),
                    text_log.see(tk.END)
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

                result = perform_upgrade_attempt(pkg, text_log, cancel_flag, set_current_process, use_exact=True)

                if result["status"] == "updated":
                    ui_print("✅ Actualizado correctamente.")
                elif result["status"] == "updated_restart_required":
                    ui_print("✅ Actualizado correctamente. Es necesario reiniciar la aplicación.")
                elif result["status"] == "no_longer_pending":
                    ui_print("↪ Resuelto: winget ya no lo considera pendiente de actualización.")
                elif result["status"] == "already_installed":
                    ui_print("↪ Resuelto: el instalador indica que ya está instalada la misma versión o una más nueva.")
                elif result["status"] == "different_install_technology":
                    ui_print("↪ No se puede actualizar en sitio: la versión nueva usa una tecnología de instalación distinta.")

                if (
                    not pkg.get("RequiresExplicitTarget")
                    and result["status"] in ("not_applicable", "not_found", "no_longer_pending")
                    and should_retry_without_exact(result)
                ):
                    ui_print("↻ Reintentando sin --exact por posible problema de coincidencia estricta...")
                    retry_no_exact = perform_upgrade_attempt(pkg, text_log, cancel_flag, set_current_process, use_exact=False)
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
                        time.sleep(1.5)
                        ui_print("🔁 Reintentando instalación una vez...")
                        retry_result = perform_upgrade_attempt(pkg, text_log, cancel_flag, set_current_process)

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

        threading.Thread(target=update_packages, daemon=True).start()

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
