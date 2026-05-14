import re
import subprocess
from process_hints import PROCESS_HINTS


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
    r"the current system configuration is not supported by this package",
    r"la configuración del sistema actual no admite la instalación de este paquete",
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
    r"Otra aplicación está usando los archivos modificados por el instalador",
    r"application is using the files modified by the installer",
]

RE_DIFFERENT_INSTALL_TECH = [
    r"different install technology",
    r"tecnolog[ií]a de instalaci[oó]n.*diferente",
    r"Desinstale el paquete e instale",
    r"Uninstall the package and install",
]

RE_ALREADY_INSTALLED = [
    r"Newer or same version is already installed",
    r"ya est[aá] instalada la misma versi[oó]n o una m[aá]s nueva",
    r"same version or a newer version is already installed",
    r"InitializeSetup returned False; aborting",
    r"Exiting with custom exit code: 1002",
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
        **kwargs,
    )


def run(cmd):
    r = run_hidden(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout or "", r.stderr or ""


def matches_any(text, patterns):
    return any(re.search(p, text, re.I) for p in patterns)


def first_matching_line(output: str, patterns):
    for line in output.splitlines():
        if matches_any(line, patterns):
            return line.strip()
    return ""


def classify_winget_result(output: str, returncode: int):
    if matches_any(output, RE_SUCCESS) and matches_any(output, RE_RESTART_REQUIRED):
        return "updated_restart_required", "Actualizado correctamente; hay que reiniciar la aplicación"

    if matches_any(output, RE_SUCCESS):
        return "updated", "Actualizado correctamente"

    if matches_any(output, RE_ALREADY_INSTALLED):
        return "already_installed", "El instalador indica que ya está instalada la misma versión o una más nueva"

    if matches_any(output, RE_NOT_APPLICABLE):
        return "not_applicable", "La actualización no aplica a este sistema o requisitos"

    if matches_any(output, RE_NOT_FOUND):
        return "not_found", "winget no encuentra un paquete instalado que coincida con el ID"

    if matches_any(output, RE_DIFFERENT_INSTALL_TECH):
        line = first_matching_line(output, RE_DIFFERENT_INSTALL_TECH)
        return "different_install_technology", line or "La versión nueva usa una tecnología de instalación diferente; requiere desinstalar e instalar"

    if matches_any(output, RE_INSTALLER_FAILS):
        line = first_matching_line(output, RE_INSTALLER_FAILS)
        return "installer_failed", line or "Fallo del instalador"

    if matches_any(output, RE_ALREADY_NO_UPDATES):
        return "no_longer_pending", "Winget ya no considera este paquete pendiente de actualización"

    if returncode == 1002:
        return "already_installed", "El instalador devolvió código 1002: misma versión o una más nueva ya instalada"

    if returncode == 0:
        return "ok_but_unclear", "winget devolvió éxito pero la salida no es concluyente"

    return "failed", f"Proceso terminó con código {returncode}"


def pkg_has_unknown_version(pkg):
    v = (pkg.get("Version") or "").strip().lower()
    return v in ("unknown", "desconocida", "")


def build_upgrade_query(pkg, *, include_interactive_flags=False):
    cmd = ["winget", "upgrade", "--id", pkg["Id"], "--exact"]

    source = (pkg.get("Source") or "").strip()
    if source and source.lower() not in ("tag",):
        cmd += ["--source", source]

    scope = (pkg.get("Scope") or "").strip().lower()
    if scope in ("user", "machine"):
        cmd += ["--scope", scope]

    if pkg_has_unknown_version(pkg):
        cmd.append("--include-unknown")

    if include_interactive_flags:
        cmd += ["--disable-interactivity", "--accept-source-agreements"]

    return cmd


def should_retry_without_exact(result):
    txt = ((result.get("raw_output") or "") + "\n" + (result.get("reason") or "")).lower()
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


def kill_process(image_name):
    r = run_hidden(
        ["taskkill", "/F", "/IM", image_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def kill_processes(process_names):
    results = []
    for p in process_names:
        ok, out = kill_process(p)
        results.append({"process": p, "ok": ok, "output": out})
    return results


def should_offer_close_retry(result, running_processes):
    if not running_processes or result.get("status") != "installer_failed":
        return False

    txt = ((result.get("raw_output") or "") + "\n" + (result.get("reason") or "")).lower()
    patterns = [
        "otra aplicación está usando los archivos modificados por el instalador",
        "application is using the files modified by the installer",
        "salga de las aplicaciones e inténtelo de nuevo",
        "close the applications and try again",
        "código de salida: 6",
        "exit code: 6",
        "código de salida: 1",
        "exit code: 1",
        "error del instalador con el código de salida",
    ]
    return any(p in txt for p in patterns)


def is_process_running(image_name):
    r = run_hidden(
        ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (r.stdout or "").lower()
    return image_name.lower() in out


def get_running_process_hints(pkg_id):
    procs = PROCESS_HINTS.get(pkg_id, [])
    return [p for p in procs if is_process_running(p)]


def parse_winget_output():
    cmd = [
        "winget",
        "upgrade",
        "--include-unknown",
        "--accept-source-agreements",
        "--disable-interactivity",
    ]
    _, out, _ = run(cmd)
    lines = out.splitlines()
    pkgs = []

    def is_table_header(line):
        return re.search(r'^(Nombre|Name)\s+', line, re.I) and re.search(r'\b(Id)\b', line, re.I)

    def find_separator(start_idx):
        for j in range(start_idx + 1, len(lines)):
            stripped = lines[j].strip()
            if stripped and set(stripped) <= {"-"}:
                return j
        return None

    def build_parser_from_header(header_line):
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
            return None

        return pos_id, pos_version, pos_available, pos_source

    i = 0
    current_explicit_target = False

    while i < len(lines):
        low = lines[i].strip().lower()

        if (
            low.startswith("los siguientes paquetes tienen una actualización disponible")
            or low.startswith("the following packages have an upgrade available")
            or "requieren un destino explícito" in low
            or "require explicit targeting" in low
        ):
            current_explicit_target = True
            i += 1
            continue

        if (
            "paquete(s) tienen números de versión" in low
            or "packages have version numbers that cannot be determined" in low
            or "paquetes están anclados" in low
            or "packages are pinned" in low
            or low.startswith("instalando dependencias:")
            or low.startswith("installing dependencies:")
        ):
            break

        if not is_table_header(lines[i]):
            i += 1
            continue

        header_line = lines[i]
        sep_idx = find_separator(i)
        parser = build_parser_from_header(header_line)
        if sep_idx is None or parser is None:
            i += 1
            continue

        pos_id, pos_version, pos_available, pos_source = parser
        i = sep_idx + 1

        while i < len(lines):
            s = lines[i].rstrip()
            low = s.strip().lower()

            if not s:
                i += 1
                continue

            if is_table_header(s):
                break

            if (
                low.startswith("los siguientes paquetes tienen una actualización disponible")
                or low.startswith("the following packages have an upgrade available")
                or "requieren un destino explícito" in low
                or "require explicit targeting" in low
                or "paquete(s) tienen números de versión" in low
                or "packages have version numbers that cannot be determined" in low
                or "paquetes están anclados" in low
                or "packages are pinned" in low
                or low.startswith("instalando dependencias:")
                or low.startswith("installing dependencies:")
                or re.match(r'^\d+\s+actualizaciones disponibles', low)
                or re.match(r'^\d+\s+upgrades available', low)
            ):
                break

            if re.match(r'^\s*[-\\|/]\s*$', s):
                i += 1
                continue

            name = s[:pos_id].strip()
            pid = s[pos_id:pos_version].strip()
            installed = s[pos_version:pos_available].strip()
            available = s[pos_available:pos_source].strip()
            source = s[pos_source:].strip()

            if pid and available:
                pkgs.append({
                    "Name": name,
                    "Id": pid,
                    "Version": installed or "Unknown",
                    "Available": available,
                    "Scope": "auto",
                    "Source": source,
                    "RequiresExplicitTarget": current_explicit_target,
                    "Key": f"{pid}|{installed or 'Unknown'}|{available}|{source}|{int(current_explicit_target)}",
                })

            i += 1

    dedup = {}
    for p in pkgs:
        dedup[p["Key"]] = p

    return sorted(
        dedup.values(),
        key=lambda x: (
            not x.get("RequiresExplicitTarget", False),
            x["Name"].lower(),
            x["Id"].lower(),
            x["Available"].lower(),
        ),
    )


def precheck_upgrade(pkg):
    cmd = build_upgrade_query(pkg, include_interactive_flags=True)
    _, out, _ = run(cmd)
    status, _ = classify_winget_result(out, 0)

    if status in ("updated", "updated_restart_required"):
        return False, "not_a_precheck_state", out
    if status in ("no_longer_pending", "not_applicable", "not_found"):
        return False, status, out
    return True, "upgradable", out


def perform_upgrade_attempt(pkg, on_line, on_progress, is_cancelled, set_current_process, use_exact=True):
    def is_boring_status_line(line):
        boring_patterns = [
            r"No se ha encontrado ninguna actualización disponible",
            r"No hay versiones más recientes del paquete disponibles",
            r"No available upgrade found",
            r"No package found matching input criteria",
            r"No installed package found matching input criteria",
            r"No se encontró ningún paquete que coincida con los criterios de entrada",
            r"different install technology",
            r"tecnolog[ií]a de instalaci[oó]n.*diferente",
            r"Desinstale el paquete e instale",
            r"Uninstall the package and install",
        ]
        return matches_any(line, boring_patterns)

    cmd = build_upgrade_query(pkg, include_interactive_flags=False)
    if not use_exact:
        cmd = [x for x in cmd if x != "--exact"]

    cmd += ["--silent", "--accept-package-agreements", "--accept-source-agreements"]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=_hidden_startupinfo(),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    set_current_process(proc)

    log_path = None
    output_lines = []
    cancelled = False

    for raw in proc.stdout:
        if is_cancelled():
            try:
                proc.terminate()
            except Exception:
                pass
            cancelled = True
            break

        output_lines.append(raw)
        line = raw.rstrip("\r\n")
        if not line.strip() or RE_SPINNER.match(line):
            continue
        if RE_PROGRESS_SIZE.search(line) or RE_PROGRESS_BAR.match(line):
            on_progress(line)
            continue

        mlog = RE_LOG_PATH.search(line)
        if mlog:
            log_path = mlog.group(1).strip()

        if re.search(r"(licencia|license|microsoft no es responsable)", line, re.I):
            continue
        if is_boring_status_line(line):
            continue
        on_line(line)

    if cancelled:
        try:
            proc.wait(timeout=2)
        except Exception:
            pass
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
