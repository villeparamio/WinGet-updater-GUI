# 🧰 Winget Updater GUI

Interfaz gráfica en **Tkinter** para actualizar programas usando `winget`.

![screenshot](screenshot.png)

## 📦 Descargar

👉 [Última versión estable (Releases)](https://github.com/villeparamio/WinGet-updater-GUI/releases/latest)

**Ejecutable recomendado:** `winget_updater.exe`


## 🚀 Características

- Lista automáticamente los programas con actualizaciones disponibles.
- Permite seleccionar cuáles actualizar.
- Muestra progreso y logs en tiempo real.
- Botón para cancelar actualizaciones en curso.
- Guarda el log en un archivo `.txt`.
- Autocomprobación e instalación de *winget* si no está disponible.

---

## 📦 Requisitos

- Windows 10/11
- Python 3.12 o superior
- `tkinter` (viene incluido con Python)

---

## ⚙️ Compilación (opcional)

```bash
pyinstaller --clean --onefile --noconsole --uac-admin ^
  --icon winget_updater.ico ^
  --version-file version.txt ^
  --add-data "winget_updater.ico;." ^
  --add-data "winget_updater.png;." ^
  winget_updater.py
