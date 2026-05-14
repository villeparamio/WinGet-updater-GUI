# 🪟 WinGet Updater GUI — Interfaz gráfica para actualizar programas con Winget

**WinGet Updater GUI** es una aplicación escrita en **Python + PySide6** que ofrece una **interfaz gráfica sencilla** para actualizar software en **Windows 10/11** usando el gestor de paquetes oficial **Winget**.

La aplicación detecta programas con actualizaciones disponibles, permite seleccionarlos desde una GUI, ejecuta las actualizaciones de forma silenciosa y muestra el progreso y el log en tiempo real.

---

## 📦 Descarga
Versión compilada disponible en la sección [Releases](https://github.com/villeparamio/WinGet-updater-GUI/releases).

---

## Idiomas compatibles

Actualmente la aplicación incluye:

- **Español**
- **English**

---

## 🔑 Palabras clave
`winget gui`, `windows updater`, `actualizador de programas`, `python tkinter`, `winget windows`, `package manager windows`

---

## 🚀 Características principales
- Detecta programas con actualizaciones disponibles mediante `winget upgrade`
- Permite seleccionar manualmente qué paquetes actualizar
- Ejecuta actualizaciones silenciosas con `winget`
- Usa coincidencia exacta (`--exact`) para evitar resoluciones ambiguas
- Muestra progreso y log en tiempo real
- Permite cancelar una actualización en curso
- Guarda el log en un archivo `.txt`
- Comprueba si `winget` está instalado y, si no lo está, intenta instalar **App Installer** automáticamente
- Clasifica distintos resultados de actualización:
  - actualizado correctamente
  - actualizado pero requiere reiniciar la aplicación
  - no aplicable
  - no encontrado
  - ya instalado / misma o más nueva versión
  - distinta tecnología de instalación
  - fallo del instalador
  - cancelado
- Detecta procesos conocidos asociados a ciertos paquetes
- Puede ofrecer cerrar procesos y reintentar una vez si hay archivos en uso
- Soporta paquetes que requieren **destino explícito** (`require explicit targeting`)
- Interfaz moderna en **Solarized Dark**
- Soporte de idiomas ampliable mediante archivos en `lang/`

---

## 🧩 Requisitos
- **Windows 10/11**
- **Python 3.12+**
- **winget** disponible en el sistema, o posibilidad de instalar **App Installer**
- Dependencias Python de `requirements.txt`

---

## ⚙️ Instalación
```bash
git clone https://github.com/villeparamio/WinGet-updater-GUI.git
cd WinGet-updater-GUI
pip install -r requirements.txt
python winget_updater.py
```

---

## 📁 Estructura del proyecto
```text
WinGet-updater-GUI/
├─ winget_updater.py
├─ gui_app.py
├─ winget_core.py
├─ process_hints.py
├─ i18n.py
├─ requirements.txt
├─ lang/
│  ├─ es.json
│  └─ en.json
├─ winget_updater.ico
├─ winget_updater.png
├─ version.txt
└─ README.md
```
---

## Funcionamiento general

Al arrancar, la aplicación:

1. solicita privilegios de administrador
2. comprueba si `winget` está disponible
3. si no lo está, intenta instalarlo automáticamente
4. obtiene la lista de paquetes con actualización disponible
5. permite filtrar, buscar y seleccionar paquetes
6. ejecuta cada actualización mostrando el log en tiempo real
7. clasifica el resultado final de cada paquete

---

## 🧠 Comportamiento actual
La aplicación distingue varios escenarios durante la actualización:

- **Updated** → actualizado correctamente
- **Updated, restart required** → actualizado correctamente, pero la aplicación debe reiniciarse
- **Already installed** → el instalador indica que ya existe la misma versión o una superior
- **Not applicable** → `winget` indica que la actualización no aplica al sistema o a esa instalación
- **Not found** → `winget` no encuentra un paquete instalado que coincida con el ID
- **Different install technology** → la nueva versión requiere desinstalar e instalar de nuevo
- **Installer failed** → error real del instalador
- **Cancelled** → cancelado por el usuario

Además:

- si se detecta un fallo típico de **files in use**
- y existen procesos conocidos asociados al paquete
- la aplicación puede ofrecer cerrar esos procesos y reintentar una vez

---

## 📜 Changelog

### v1.4
- Se **arregla la instalación de Microsoft App Installer (winget) en equipos que no lo tienen**:
  - Se desactiva la barra de progreso de `Invoke-WebRequest` (`$ProgressPreference = 'SilentlyContinue'`), que por un bug conocido de PowerShell 5.1 ralentizaba descargas grandes hasta varios órdenes de magnitud y provocaba que la descarga del bundle se quedase colgada.
  - Se pre-instalan las dependencias `Microsoft.VCLibs` y `Microsoft.UI.Xaml` antes del bundle de App Installer, detectando automáticamente la arquitectura (`x64`/`arm64`).
  - El error `0x80073D06` ("ya hay una versión superior instalada") se trata correctamente como caso benigno y no como fallo.
  - La detección de winget hace fallback a la ruta absoluta `%LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe` cuando el `PATH` del proceso actual está cacheado.
- La instalación de winget se ejecuta en un **hilo dedicado** (`InstallerThread`), evitando que la ventana se congele durante la descarga; el log fluye en tiempo real.
- Se añade **logueo de diagnóstico exhaustivo** con prefijo `[diag]`: stdout, stderr, exit code y salida parcial en caso de timeout para cada llamada PowerShell.
- Se añaden **timeouts** a todas las llamadas a subprocess y captura amplia de excepciones.
- Se fuerza codificación **UTF-8** en la salida de PowerShell para que los acentos se muestren correctamente en el log.
- Las llamadas a subprocess de la GUI se hacen ya sin abrir ventanas de consola en el `.exe`.
- Cuando falla abrir la Microsoft Store por `ms-windows-store://`, se prueba con la URL HTTPS `apps.microsoft.com` como fallback.
- Se completa el log al finalizar el **reintento sin `--exact`** y el **reintento tras matar procesos**: antes el reintento quedaba en silencio y el usuario no veía cómo había resuelto.
- Se elimina la línea cruda duplicada de winget cuando el resultado es "tecnología de instalación distinta".

### v1.3
- Se rediseña la interfaz con paleta **Solarized Dark** oficial y mejor contraste en texto secundario.
- El **log de ejecución** pasa a estar siempre visible en un panel inferior con tipografía monoespaciada.
- Cada paquete se muestra como una tarjeta con barra lateral de color según su estado (seleccionado, deseleccionado, destino explícito).
- Se corrige un **crash al cerrar procesos y reintentar**: el diálogo de confirmación se abría desde el hilo trabajador de Qt. Ahora se usa un puente signal + event para mostrarlo desde el hilo principal.
- Se limpia la lógica de ejecución:
  - `perform_upgrade_attempt` recibe callbacks simples en vez de un pseudo widget de Tkinter.
  - Se filtran las líneas de solo espacios que `winget` escribe al limpiar la barra de progreso.
  - Tras cancelar, se espera al proceso de `winget` unos segundos para no dejarlo colgado.
- Se amplía `process_hints.py` con más de 160 paquetes comunes: navegadores, IDEs, IDEs de JetBrains, terminales, clientes de chat, launchers de juegos, software RGB, editores multimedia, notas, gestores de contraseñas, torrents y utilidades de sistema.

### v1.2
- La interfaz gráfica se migra a **PySide6**.
- Se renueva la GUI con un diseño más moderno.
- Se mejora la lógica interna de actualización y clasificación de resultados.
- Se mejora el procesamiento del listado de paquetes de `winget`.
- Se añade soporte para paquetes que requieren destino explícito.
- Se incorpora soporte multidioma.
- Se añade selector de idioma en la interfaz.

### v1.1
- Se mejora la clasificación de resultados de `winget`.
- Se diferencia entre:
  - actualización completada
  - actualización completada con reinicio de aplicación pendiente
  - paquete no aplicable
  - paquete no encontrado
  - fallo del instalador
  - cancelación por usuario
- Se usa `--exact` en las operaciones de actualización para evitar coincidencias ambiguas.
- Se añade precheck antes de actualizar cada paquete.
- Se añade soporte para detección de procesos conocidos asociados a paquetes.
- Se añade la posibilidad de cerrar procesos conocidos y reintentar una actualización fallida por archivos en uso.
- Se separa la configuración de procesos asociados en el fichero `process_hints.py`.

### v1.0
- Primera versión pública de la interfaz gráfica para actualizar programas con `winget`.
- Listado de software con actualizaciones disponibles.
- Selección manual de paquetes.
- Ejecución de actualizaciones desde GUI.
- Visualización de logs en tiempo real.
- Guardado de log en fichero de texto.
- Instalación automática de `winget` si no está presente.

---

## 💻 Compilación en `.exe` (opcional)
```bash
pyinstaller --clean --onefile --noconsole --uac-admin ^
  --icon winget_updater.ico ^
  --version-file version.txt ^
  --add-data "winget_updater.ico;." ^
  --add-data "winget_updater.png;." ^
  --add-data "lang;lang" ^
  winget_updater.py
```

Si empaquetas la aplicación, recuerda incluir también los archivos de idioma.

---

## 🧠 Captura de pantalla
![Interfaz principal](screenshot.png)

---

## ⚠️ Limitaciones conocidas
- La salida de `winget` no siempre es totalmente consistente entre paquetes.
- Algunos paquetes pueden aparecer como actualizables pero luego resultar **no aplicables** o **no encontrables** al intentar actualizarlos.
- Algunos fallos del instalador dependen del propio paquete, del estado interno de Windows o de reinicios pendientes.
- La detección de procesos abiertos se basa en heurísticas definidas manualmente en `process_hints.py`, no en inspección completa de handles del sistema.

---

## 🔗 Más información
- [Documentación de winget](https://learn.microsoft.com/es-es/windows/package-manager/)
- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/)
- [PyInstaller](https://pyinstaller.org/)

---

## 🪪 Licencia
MIT License © [villeparamio](https://github.com/villeparamio)

---

## 💖 Donaciones

Si encuentras este proyecto útil y quieres apoyar su desarrollo y mantenimiento, considera hacer una donación.  
Tu contribución ayuda a seguir mejorando y manteniendo este software libre.

### 💸 PayPal
Puedes donar fácilmente mediante PayPal haciendo clic en el siguiente botón:

[![Donate](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate/?business=95M7L3UZENS6Q&no_recurring=0&currency_code=EUR)

Gracias por tu apoyo 🙏