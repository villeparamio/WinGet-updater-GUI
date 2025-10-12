# 🪟 WinGet Updater GUI — Interfaz gráfica para actualizar programas con Winget

**WinGet Updater GUI** es una aplicación escrita en **Python + Tkinter** que ofrece una **interfaz gráfica sencilla** para actualizar software en **Windows 10/11** usando el gestor de paquetes oficial **Winget**.

---

## 📦 Descarga
Versión compilada disponible en la sección [Releases](https://github.com/villeparamio/WinGet-updater-GUI/releases).

---

## 🔑 Palabras clave
`winget gui`, `windows updater`, `actualizador de programas`, `python tkinter`, `winget windows`, `package manager windows`

---

## 🚀 Características principales
- Lista automáticamente los programas con actualizaciones disponibles.
- Permite seleccionar cuáles actualizar.
- Muestra progreso y logs en tiempo real.
- Permite cancelar actualizaciones en curso.
- Guarda el registro en un archivo `.txt`.
- Comprueba e instala Winget si no está disponible.

---

## 🧩 Requisitos
- **Windows 10/11**
- **Python 3.12+**
- Módulo `tkinter` (incluido en Python)

---

## ⚙️ Instalación
```bash
git clone https://github.com/villeparamio/WinGet-updater-GUI.git
cd WinGet-updater-GUI
python winget_updater.py
```

---

## 💻 Compilación en .exe (opcional)
```bash
pyinstaller --clean --onefile --noconsole --uac-admin ^
  --icon winget_updater.ico ^
  --version-file version.txt ^
  --add-data "winget_updater.ico;." ^
  --add-data "winget_updater.png;." ^
  winget_updater.py
```

---

## 🧠 Captura de pantalla
![Interfaz principal](screenshot.png)

---

## 🔗 Más información
- [Documentación de Winget](https://learn.microsoft.com/es-es/windows/package-manager/)
- [PyInstaller](https://pyinstaller.org/)
- [Tkinter Docs](https://docs.python.org/3/library/tkinter.html)

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

### ₿ Criptomonedas
**Bitcoin (BTC):** `13Sp4LwbDC1NQv17p3NN9w2yodog8KGtda`  
**Ethereum (ETH):** `0x1939f4ba76adc18378533965857494e5f19ef4a4`

Gracias por tu apoyo 🙏