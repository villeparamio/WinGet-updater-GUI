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


THEMES = {
    "light": {
        "BG_APP": "#e9eef6",
        "BG_SURFACE": "#ffffff",
        "BG_SURFACE_ALT": "#f8fbff",
        "BG_ACCENT": "#dbeafe",
        "BORDER": "#b9c6d8",
        "TEXT_MAIN": "#0f172a",
        "TEXT_MUTED": "#334155",
        "TEXT_SOFT": "#64748b",
        "PRIMARY": "#1d4ed8",
        "PRIMARY_HI": "#2563eb",
        "PRIMARY_DISABLED": "#93c5fd",
        "SUCCESS": "#166534",
        "WARNING": "#a16207",
        "ERROR": "#b91c1c",
        "PILL_BG": "#dbeafe",
        "PILL_TEXT": "#1e3a8a",
        "PILL_WARN_BG": "#ffedd5",
        "PILL_WARN_TEXT": "#9a3412",
        "LOG_BG": "#f3f7fc",
        "LOG_FG": "#0f172a",
        "ENTRY_BG": "#ffffff",
        "ENTRY_FG": "#0f172a",
        "ENTRY_BORDER": "#94a3b8",
        "CANVAS_BG": "#ffffff",
        "PROGRESS_TROUGH": "#cbd5e1",
    },
    "dark": {
        "BG_APP": "#002b36",
        "BG_SURFACE": "#073642",
        "BG_SURFACE_ALT": "#0a3a46",
        "BG_ACCENT": "#0b3c49",
        "BORDER": "#586e75",
        "TEXT_MAIN": "#eee8d5",
        "TEXT_MUTED": "#93a1a1",
        "TEXT_SOFT": "#839496",
        "PRIMARY": "#268bd2",
        "PRIMARY_HI": "#2aa198",
        "PRIMARY_DISABLED": "#3c6f73",
        "SUCCESS": "#859900",
        "WARNING": "#b58900",
        "ERROR": "#dc322f",
        "PILL_BG": "#09414f",
        "PILL_TEXT": "#93a1a1",
        "PILL_WARN_BG": "#6b5200",
        "PILL_WARN_TEXT": "#fdf6e3",
        "LOG_BG": "#00212b",
        "LOG_FG": "#eee8d5",
        "ENTRY_BG": "#001f27",
        "ENTRY_FG": "#eee8d5",
        "ENTRY_BORDER": "#586e75",
        "CANVAS_BG": "#073642",
        "PROGRESS_TROUGH": "#204851",
    },
}


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
    theme_var = tk.StringVar(value="dark")

    style = ttk.Style()
    try:
        style.theme_use("vista")
    except Exception:
        try:
            style.theme_use("clam")
        except Exception:
            pass

    root.option_add("*Font", ("Segoe UI", 10))
    root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

    palette = THEMES[theme_var.get()]

    def c(name):
        return palette[name]

    def apply_theme():
        nonlocal palette
        palette = THEMES[theme_var.get()]
        root.configure(bg=c("BG_APP"))
        style.configure("TFrame", background=c("BG_APP"))
        style.configure("Surface.TFrame", background=c("BG_SURFACE"))
        style.configure("Header.TFrame", background=c("BG_APP"))
        style.configure("Card.TFrame", background=c("BG_SURFACE"))
        style.configure("Stats.TFrame", background=c("BG_ACCENT"))
        style.configure("TLabel", background=c("BG_APP"), foreground=c("TEXT_MAIN"), padding=0)
        style.configure("Surface.TLabel", background=c("BG_SURFACE"), foreground=c("TEXT_MAIN"))
        style.configure("Muted.TLabel", background=c("BG_APP"), foreground=c("TEXT_MUTED"))
        style.configure("SmallMuted.TLabel", background=c("BG_SURFACE"), foreground=c("TEXT_SOFT"))
        style.configure("CardTitle.TLabel", background=c("BG_SURFACE"), foreground=c("TEXT_MAIN"), font=("Segoe UI Semibold", 10))
        style.configure("AppTitle.TLabel", background=c("BG_APP"), foreground=c("TEXT_MAIN"), font=("Segoe UI Semibold", 18))
        style.configure("Hero.TLabel", background=c("BG_APP"), foreground=c("TEXT_MAIN"), font=("Segoe UI Semibold", 22))
        style.configure("HeroSub.TLabel", background=c("BG_APP"), foreground=c("TEXT_MUTED"), font=("Segoe UI", 10))
        style.configure("StatValue.TLabel", background=c("BG_ACCENT"), foreground=c("TEXT_MAIN"), font=("Segoe UI Semibold", 18))
        style.configure("StatLabel.TLabel", background=c("BG_ACCENT"), foreground=c("TEXT_MUTED"), font=("Segoe UI", 9))
        style.configure("Primary.TButton", padding=(14, 10), font=("Segoe UI Semibold", 10))
        style.configure("TButton", padding=(10, 8))
        try:
            style.configure("TEntry", fieldbackground=c("ENTRY_BG"), foreground=c("ENTRY_FG"))
        except Exception:
            pass
        try:
            style.configure("TCombobox", fieldbackground=c("ENTRY_BG"), foreground=c("ENTRY_FG"), arrowsize=14)
        except Exception:
            pass
        style.map("Primary.TButton", foreground=[("!disabled", "white")], background=[("!disabled", c("PRIMARY_HI")), ("disabled", c("PRIMARY_DISABLED"))])
        try:
            style.configure("Modern.Horizontal.TProgressbar", troughcolor=c("PROGRESS_TROUGH"), bordercolor=c("PROGRESS_TROUGH"), background=c("PRIMARY_HI"), lightcolor=c("PRIMARY_HI"), darkcolor=c("PRIMARY_HI"))
        except Exception:
            style.configure("Modern.Horizontal.TProgressbar", background=c("PRIMARY_HI"))

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

    apply_theme()

    root.title(f"Winget Updater {APP_VERSION} (by Villeparamio)")
    root.geometry("1220x860")
    root.minsize(980, 680)

    pkgs = []
    checks = []
    current_process = None
    cancel_flag = tk.BooleanVar(value=False)
    search_var = tk.StringVar()
    filter_var = tk.StringVar(value="all")
    show_log_var = tk.BooleanVar(value=False)
    status_var = tk.StringVar(value="Inicializando...")
    stats_total_var = tk.StringVar(value="0")
    stats_selected_var = tk.StringVar(value="0")
    stats_special_var = tk.StringVar(value="0")
    headline_var = tk.StringVar(value="Cargando lista de programas...")
    subtitle_var = tk.StringVar(value="Comprobando winget y preparando la interfaz")
    current_results = {"last": None}

    def set_current_process(proc):
        nonlocal current_process
        current_process = proc

    def append_log(msg):
        text_log.insert(tk.END, msg if msg.endswith("\n") else msg + "\n")
        text_log.see(tk.END)

    def log_ui(msg):
        text_log.after(0, lambda: append_log(msg))

    def set_status(msg):
        status_var.set(msg)

    def set_status_async(msg):
        root.after(0, lambda: set_status(msg))

    def sync_log_visibility():
        if show_log_var.get():
            if not frame_log.winfo_manager():
                frame_log.pack(fill=tk.BOTH, expand=False, padx=18, pady=(0, 14))
                btn_toggle_log.config(text="Ocultar log")
        else:
            if frame_log.winfo_manager():
                frame_log.pack_forget()
                btn_toggle_log.config(text="Mostrar log")

    def toggle_log():
        show_log_var.set(not show_log_var.get())
        sync_log_visibility()

    outer = ttk.Frame(root, style="Header.TFrame")
    outer.pack(fill=tk.BOTH, expand=True)

    header = ttk.Frame(outer, style="Header.TFrame")
    header.pack(fill=tk.X, padx=18, pady=(18, 12))

    header_left = ttk.Frame(header, style="Header.TFrame")
    header_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

    ttk.Label(header_left, text="WinGet Updater", style="Hero.TLabel").pack(anchor="w")
    ttk.Label(header_left, textvariable=subtitle_var, style="HeroSub.TLabel").pack(anchor="w", pady=(4, 0))

    header_actions = ttk.Frame(header, style="Header.TFrame")
    header_actions.pack(side=tk.RIGHT, anchor="ne")

    btn_refresh = ttk.Button(header_actions, text="Refrescar", width=12)
    btn_refresh.grid(row=0, column=0, padx=(0, 8))
    btn_save = ttk.Button(header_actions, text="Guardar log", width=14)
    btn_save.grid(row=0, column=1, padx=(0, 8))
    btn_toggle_log = ttk.Button(header_actions, text="Mostrar log", width=14, command=toggle_log)
    btn_toggle_log.grid(row=0, column=2, padx=(0, 8))
    btn_theme = ttk.Button(header_actions, text="Tema: oscuro", width=14)
    btn_theme.grid(row=0, column=3, padx=(0, 8))
    btn_update = tk.Button(
        header_actions,
        text="Actualizar seleccionados",
        width=24,
        bg=c("PRIMARY_HI"),
        fg=c("BG_APP") if theme_var.get() == "light" else c("BG_APP"),
        activebackground=c("PRIMARY"),
        activeforeground=c("TEXT_MAIN"),
        relief="flat",
        bd=0,
        padx=14,
        pady=10,
        font=("Segoe UI Semibold", 10),
        highlightthickness=0,
    )
    btn_update.grid(row=0, column=4)

    stats_row = ttk.Frame(outer, style="Header.TFrame")
    stats_row.pack(fill=tk.X, padx=18, pady=(0, 12))

    def make_stat(parent, value_var, label_text):
        frame = ttk.Frame(parent, style="Stats.TFrame", padding=(16, 12))
        frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Label(frame, textvariable=value_var, style="StatValue.TLabel").pack(anchor="w")
        ttk.Label(frame, text=label_text, style="StatLabel.TLabel").pack(anchor="w", pady=(2, 0))
        return frame

    make_stat(stats_row, stats_total_var, "Disponibles")
    make_stat(stats_row, stats_selected_var, "Seleccionados")
    make_stat(stats_row, stats_special_var, "Especiales / manuales")

    toolbar = ttk.Frame(outer, style="Header.TFrame")
    toolbar.pack(fill=tk.X, padx=18, pady=(0, 10))

    search_wrap = ttk.Frame(toolbar, style="Surface.TFrame", padding=(12, 10))
    search_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True)

    ttk.Label(search_wrap, text="Buscar", style="Surface.TLabel").pack(side=tk.LEFT)
    entry_search = ttk.Entry(search_wrap, textvariable=search_var, width=38)
    entry_search.pack(side=tk.LEFT, padx=(10, 12))

    ttk.Label(search_wrap, text="Vista", style="Surface.TLabel").pack(side=tk.LEFT)
    combo_filter = ttk.Combobox(
        search_wrap,
        textvariable=filter_var,
        state="readonly",
        width=24,
        values=[
            "all",
            "selected",
            "explicit",
            "unknown",
        ],
    )
    combo_filter.pack(side=tk.LEFT, padx=(10, 12))
    combo_filter.set("all")

    btn_all = ttk.Button(search_wrap, text="Seleccionar todo", width=16)
    btn_all.pack(side=tk.LEFT, padx=(6, 8))
    btn_none = ttk.Button(search_wrap, text="Seleccionar nada", width=16)
    btn_none.pack(side=tk.LEFT)

    subtitle_panel = ttk.Frame(outer, style="Header.TFrame")
    subtitle_panel.pack(fill=tk.X, padx=18, pady=(0, 8))
    ttk.Label(subtitle_panel, textvariable=headline_var, style="AppTitle.TLabel").pack(anchor="w")
    ttk.Label(subtitle_panel, textvariable=status_var, style="Muted.TLabel").pack(anchor="w", pady=(3, 0))

    list_container = ttk.Frame(outer, style="Surface.TFrame", padding=(0, 0, 0, 0))
    list_container.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 12))

    canvas = tk.Canvas(list_container, highlightthickness=0, bd=0, bg=c("CANVAS_BG"))
    vbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
    scroll = ttk.Frame(canvas, style="Surface.TFrame")
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

    footer = ttk.Frame(outer, style="Header.TFrame")
    footer.pack(fill=tk.X, padx=18, pady=(0, 12))

    footer_left = ttk.Frame(footer, style="Header.TFrame")
    footer_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

    progress = ttk.Progressbar(footer_left, mode="determinate", maximum=100, style="Modern.Horizontal.TProgressbar")
    progress.pack(fill=tk.X)
    ttk.Label(footer_left, textvariable=status_var, style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

    footer_right = ttk.Frame(footer, style="Header.TFrame")
    footer_right.pack(side=tk.RIGHT)
    btn_cancel = ttk.Button(footer_right, text="Cancelar actualización", state="disabled", width=20)
    btn_cancel.pack(side=tk.RIGHT)

    frame_log = ttk.Frame(outer, style="Surface.TFrame", padding=(12, 12))
    ttk.Label(frame_log, text="Log de ejecución", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
    text_log = scrolledtext.ScrolledText(
        frame_log,
        height=12,
        wrap=tk.WORD,
        relief="flat",
        borderwidth=0,
        font=("Consolas", 9),
        background=c("LOG_BG"),
        foreground=c("LOG_FG"),
        insertbackground=c("LOG_FG"),
    )
    text_log.pack(fill=tk.BOTH, expand=True)
    sync_log_visibility()


    def refresh_theme_widgets():
        canvas.configure(bg=c("CANVAS_BG"))
        text_log.configure(background=c("LOG_BG"), foreground=c("LOG_FG"), insertbackground=c("LOG_FG"))
        btn_update.configure(
            bg=c("PRIMARY_HI"),
            fg=c("BG_APP"),
            activebackground=c("PRIMARY"),
            activeforeground=c("TEXT_MAIN"),
        )
        btn_theme.config(text=f"Tema: {'oscuro' if theme_var.get() == 'dark' else 'claro'}")
        render_list()

    def toggle_theme():
        theme_var.set("light" if theme_var.get() == "dark" else "dark")
        apply_theme()
        refresh_theme_widgets()

    btn_theme.config(command=toggle_theme)

    def set_buttons_enabled(enabled: bool):
        state = "normal" if enabled else "disabled"
        for b in (btn_all, btn_none, btn_refresh, btn_update, btn_save, entry_search, combo_filter):
            try:
                b.config(state=state)
            except Exception:
                pass
        if enabled:
            try:
                btn_update.configure(
                    bg=c("PRIMARY_HI"),
                    fg=c("BG_APP"),
                    activebackground=c("PRIMARY"),
                    activeforeground=c("TEXT_MAIN"),
                )
            except Exception:
                pass
        else:
            try:
                btn_update.configure(
                    bg=c("PRIMARY_DISABLED"),
                    fg=c("TEXT_MUTED"),
                    activebackground=c("PRIMARY_DISABLED"),
                    activeforeground=c("TEXT_MUTED"),
                )
            except Exception:
                pass
        if enabled:
            combo_filter.config(state="readonly")
        else:
            combo_filter.config(state="disabled")

    def visible_items():
        q = search_var.get().strip().lower()
        mode = filter_var.get().strip().lower() or "all"
        items = []
        for var, pkg in checks:
            haystack = " ".join([
                pkg.get("Name", ""),
                pkg.get("Id", ""),
                pkg.get("Version", ""),
                pkg.get("Available", ""),
                pkg.get("Source", ""),
            ]).lower()

            if q and q not in haystack:
                continue
            if mode == "selected" and not var.get():
                continue
            if mode == "explicit" and not pkg.get("RequiresExplicitTarget"):
                continue
            if mode == "unknown" and (pkg.get("Version") or "").strip().lower() not in ("unknown", "desconocida", ""):
                continue
            items.append((var, pkg))
        return items

    def update_summary_ui():
        selected_count = sum(1 for var, _ in checks if var.get())
        explicit_count = sum(1 for _, pkg in checks if pkg.get("RequiresExplicitTarget"))
        unknown_count = sum(1 for _, pkg in checks if (pkg.get("Version") or "").strip().lower() in ("unknown", "desconocida", ""))
        stats_total_var.set(str(len(pkgs)))
        stats_selected_var.set(str(selected_count))
        stats_special_var.set(str(explicit_count + unknown_count))

        visible_count = len(visible_items())
        if pkgs:
            headline_var.set(f"{visible_count} visibles · {len(pkgs)} detectados")
            subtitle_var.set("Actualizaciones disponibles detectadas con winget")
        else:
            headline_var.set("Sin actualizaciones pendientes")
            subtitle_var.set("Todo parece estar al día")

        btn_update.config(text=f"Actualizar seleccionados ({selected_count})")

    def set_pkg_selected(var, _pkg, value):
        var.set(value)
        update_summary_ui()
        render_list()

    def make_chip(parent, text, fg=c("PILL_TEXT"), bg=c("PILL_BG")):
        lbl = tk.Label(parent, text=text, bg=bg, fg=fg, padx=8, pady=2, font=("Segoe UI", 8, "bold"), relief="flat")
        return lbl

    def render_list(*_args):
        for w in list(scroll.children.values()):
            w.destroy()

        items = visible_items()
        if not pkgs:
            empty = ttk.Frame(scroll, style="Card.TFrame", padding=(18, 18))
            empty.pack(fill=tk.X, padx=12, pady=12)
            ttk.Label(empty, text="No hay actualizaciones disponibles", style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(empty, text="Cuando winget encuentre paquetes actualizables aparecerán aquí.", style="SmallMuted.TLabel").pack(anchor="w", pady=(6, 0))
            _update_scrollregion()
            return

        if not items:
            empty = ttk.Frame(scroll, style="Card.TFrame", padding=(18, 18))
            empty.pack(fill=tk.X, padx=12, pady=12)
            ttk.Label(empty, text="No hay resultados para ese filtro", style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(empty, text="Prueba otra búsqueda o cambia la vista activa.", style="SmallMuted.TLabel").pack(anchor="w", pady=(6, 0))
            _update_scrollregion()
            return

        for idx, (var, pkg) in enumerate(items):
            card_outer = tk.Frame(scroll, bg=c("BORDER"), highlightthickness=0, bd=0)
            card_outer.pack(fill=tk.X, padx=10, pady=(4 if idx == 0 else 2, 2))

            card = tk.Frame(card_outer, bg=c("BG_SURFACE"), padx=12, pady=10)
            card.pack(fill=tk.X, padx=1, pady=1)

            top = tk.Frame(card, bg=c("BG_SURFACE"))
            top.pack(fill=tk.X)

            cb = ttk.Checkbutton(top, variable=var, command=update_summary_ui)
            cb.pack(side=tk.LEFT, anchor="n", pady=(1, 0))

            main = tk.Frame(top, bg=c("BG_SURFACE"))
            main.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

            tk.Label(main, text=pkg["Name"], bg=c("BG_SURFACE"), fg=c("TEXT_MAIN"), font=("Segoe UI Semibold", 10), anchor="w").pack(anchor="w")
            tk.Label(main, text=pkg["Id"], bg=c("BG_SURFACE"), fg=c("TEXT_SOFT"), font=("Segoe UI", 9), anchor="w").pack(anchor="w", pady=(1, 0))
            tk.Label(
                main,
                text=f"{pkg['Version']}  →  {pkg['Available']}   ·   {pkg.get('Source', '') or 'origen desconocido'}",
                bg=c("BG_SURFACE"),
                fg=c("TEXT_MUTED"),
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(anchor="w", pady=(4, 0))

            chips = tk.Frame(main, bg=c("BG_SURFACE"))
            chips.pack(anchor="w", pady=(6, 0))
            if pkg.get("RequiresExplicitTarget"):
                chip = make_chip(chips, "requiere destino explícito")
                chip.pack(side=tk.LEFT, padx=(0, 6))
            if (pkg.get("Version") or "").strip().lower() in ("unknown", "desconocida", ""):
                chip = make_chip(chips, "versión desconocida", fg=c("PILL_WARN_TEXT"), bg=c("PILL_WARN_BG"))
                chip.pack(side=tk.LEFT, padx=(0, 6))

            actions = tk.Frame(top, bg=c("BG_SURFACE"))
            actions.pack(side=tk.RIGHT, anchor="ne")
            ttk.Button(actions, text="Marcar", width=9, command=lambda v=var, p=pkg: set_pkg_selected(v, p, True)).pack(pady=(0, 4))
            ttk.Button(actions, text="Quitar", width=9, command=lambda v=var, p=pkg: set_pkg_selected(v, p, False)).pack()

            sep = tk.Frame(scroll, bg=c("BORDER"), height=1)
            sep.pack(fill=tk.X, padx=18, pady=(0, 2))

        _update_scrollregion()
        canvas.yview_moveto(0)

    def refresh_list_async():
        set_buttons_enabled(False)
        set_status("Actualizando listado...")
        append_log("Actualizando listado...")

        def refresh_task():
            new_pkgs = parse_winget_output() or []

            def apply():
                pkgs.clear()
                pkgs.extend(new_pkgs)
                checks.clear()
                for pkg in pkgs:
                    var = tk.BooleanVar(value=True)
                    var.trace_add("write", lambda *_: update_summary_ui())
                    checks.append((var, pkg))
                render_list()
                update_summary_ui()
                set_buttons_enabled(True)
                set_status("Listado actualizado")
                append_log("Listado actualizado.")

            root.after(0, apply)

        threading.Thread(target=refresh_task, daemon=True).start()

    refresh_theme_widgets()
    append_log("Inicializando...")
    set_buttons_enabled(False)

    def init_task():
        def proceed_after_install(ok: bool):
            if not ok:
                messagebox.showerror(
                    "Falta winget",
                    "No se pudo instalar/activar winget. Abre la Microsoft Store e instala 'App Installer'."
                )
                return

            set_status("Obteniendo lista de paquetes...")
            append_log("Obteniendo lista de paquetes...")

            def fetch_task():
                new_pkgs = parse_winget_output() or []

                def apply():
                    pkgs.clear()
                    pkgs.extend(new_pkgs)
                    checks.clear()
                    for pkg in pkgs:
                        var = tk.BooleanVar(value=True)
                        var.trace_add("write", lambda *_: update_summary_ui())
                        checks.append((var, pkg))
                    render_list()
                    update_summary_ui()
                    set_buttons_enabled(True)
                    set_status("Listo")
                    append_log("Listo.")

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

    search_var.trace_add("write", lambda *_: (render_list(), update_summary_ui()))
    filter_var.trace_add("write", lambda *_: (render_list(), update_summary_ui()))

    def do_update():
        selected = [p for v, p in checks if v.get()]
        if not selected:
            messagebox.showinfo("Nada seleccionado", "No has seleccionado ningún paquete.")
            return

        cancel_flag.set(False)
        btn_cancel.config(state="normal")
        set_buttons_enabled(False)
        progress.config(mode='determinate', maximum=len(selected), value=0)
        set_status(f"Actualizando {len(selected)} paquete(s)...")

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

                current_results["last"] = body
                progress.config(value=0)
                refresh_list_async()
                btn_cancel.config(state="disabled")
                set_status("Proceso finalizado")

                if installer_failed or failed:
                    root.after(200, lambda: messagebox.showwarning("Finalizado con incidencias", body))
                else:
                    root.after(200, lambda: messagebox.showinfo("Completado", body))

            progress.after(0, done_ui)

        def update_packages():
            total = len(selected)

            def ui_print(msg):
                text_log.after(0, lambda: append_log(msg))

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

                set_status_async(f"Actualizando {idx}/{total}: {pkg['Name']}")
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

        log_ui("⛔ Cancelando actualización...")
        set_status("Cancelando actualización...")

    btn_cancel.config(command=cancel_update)
    btn_update.config(command=do_update)
    btn_refresh.config(command=refresh_list_async)
    btn_save.config(command=lambda: save_log(text_log))

    root.mainloop()
