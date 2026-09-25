"""
utilidades_archivos.py — Utilidades de archivos en una sola ventana (PyQt6).

Pestañas:
    1. Copiar            Robocopy con exclusiones editables, sesiones guardadas y salida en vivo.
    2. Organizar         Escanea una carpeta (recursivo), cuenta por extensión y mueve/copia
                         las extensiones elegidas a <destino>/<extensión>/.
    3. Listar rutas      Genera un .txt con las rutas de archivos y/o carpetas (recursivo),
                         con filtro de extensiones y carpetas a ignorar.
    4. Info entorno      Versiones de paquetes de un venv o del Python global -> requirements.txt.
    5. Licencias         THIRD_PARTY_NOTICES.txt con las licencias de un venv o del Python global.

La configuración (tema, sesiones guardadas, último venv...) vive en
'utilidades_config.json', junto a este script.

Requisitos: Python 3.9+ y PyQt6  (pip install PyQt6)
"""

from __future__ import annotations

import codecs
import copy
import fnmatch
import json
import ntpath
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from PyQt6.QtCore import QProcess, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (QColor, QDesktopServices, QFont, QFontDatabase,
                         QTextCharFormat, QTextCursor)
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup,
                             QCheckBox, QComboBox, QFileDialog, QFrame,
                             QGridLayout, QHBoxLayout, QHeaderView,
                             QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMainWindow, QMessageBox,
                             QPlainTextEdit, QProgressBar, QPushButton,
                             QRadioButton, QScrollArea, QSizePolicy, QSpinBox,
                             QSplitter, QTableWidget, QTableWidgetItem,
                             QTabWidget, QVBoxLayout, QWidget)

APP_NOMBRE = "Utilidades de archivos"
ES_WINDOWS = sys.platform.startswith("win")


def carpeta_app() -> Path:
    """Carpeta donde vive el script (o el .exe si se empaqueta con PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = carpeta_app() / "utilidades_config.json"


# ═════════════════════════════════════════════════════════════════════════════
# DESIGN TOKENS
# ═════════════════════════════════════════════════════════════════════════════

SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 16
SPACING_LG = 24

RADIUS_SM = 2
RADIUS_DEFAULT = 4
RADIUS_LG = 8

TXT_HEADLINE_MD = 20
TXT_HEADLINE_SM = 16
TXT_BODY_MD = 14
TXT_BODY_SM = 13
TXT_LABEL_MD = 12

# Se eligen en tiempo de ejecución la primera fuente instalada de cada lista
FUENTES_CUERPO = ["Inter", "Segoe UI", "Noto Sans", "Helvetica Neue", "Arial"]
FUENTES_TITULO = ["Hanken Grotesk", "Segoe UI Semibold", "Segoe UI", "Noto Sans", "Arial"]
FUENTES_MONO = ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "Courier New"]

PALETAS = {
    "claro": {
        "bg": "#faf9ff",
        "superficie": "#ffffff",
        "superficie_baja": "#f1f3ff",
        "superficie_alta": "#e1e8ff",
        "borde": "#c3c6d6",
        "borde_fuerte": "#737685",
        "texto": "#051a3e",
        "texto_suave": "#434654",
        "primario": "#003d9b",
        "primario_hover": "#0052cc",
        "sobre_primario": "#ffffff",
        "primario_suave": "#dae2ff",
        "texto_primario_suave": "#003d9b",
        "peligro": "#ba1a1a",
        "peligro_hover": "#93000a",
        "sobre_peligro": "#ffffff",
        "deshabilitado_bg": "#eceef6",
        "deshabilitado_texto": "#9a9daa",
        "consola_bg": "#ffffff",
        "tooltip_bg": "#1d3054",
        "tooltip_texto": "#edf0ff",
    },
    "oscuro": {
        "bg": "#0B121F",
        "superficie": "#161C27",
        "superficie_baja": "#1E2738",
        "superficie_alta": "#252D3D",
        "borde": "#2c3548",
        "borde_fuerte": "#3d4560",
        "texto": "#edf0ff",
        "texto_suave": "#9ca3b8",
        "primario": "#b2c5ff",
        "primario_hover": "#c9d6ff",
        "sobre_primario": "#002a6b",
        "primario_suave": "#0040a2",
        "texto_primario_suave": "#edf0ff",
        "peligro": "#ffb4ab",
        "peligro_hover": "#ffdad6",
        "sobre_peligro": "#690005",
        "deshabilitado_bg": "#1a2130",
        "deshabilitado_texto": "#5b6378",
        "consola_bg": "#0f1622",
        "tooltip_bg": "#edf0ff",
        "tooltip_texto": "#0B121F",
    },
}

# Colores del registro: tonos medios que se leen bien en ambos temas
COLOR_LOG = {
    "ok": "#2e9d5b",
    "aviso": "#d08700",
    "error": "#e5484d",
    "titulo": "#4c7dff",
    "suave": "#8a90a2",
}


def elegir_fuente(candidatas: list[str]) -> str:
    disponibles = set(QFontDatabase.families())
    for nombre in candidatas:
        if nombre in disponibles:
            return nombre
    return QApplication.font().family()


def preparar_iconos(p: dict, tema: str) -> dict:
    """Escribe los SVG (check, flechas) del tema en una carpeta temporal para usarlos en QSS."""
    carpeta = Path(tempfile.gettempdir()) / "utilidades_archivos_iconos"
    carpeta.mkdir(parents=True, exist_ok=True)
    trazos = {
        "check": ("M5 12.5l4.5 4.5L19 7.5", p["sobre_primario"]),
        "abajo": ("M6 9l6 6 6-6", p["texto_suave"]),
        "arriba": ("M6 15l6-6 6 6", p["texto_suave"]),
    }
    rutas = {}
    for nombre, (d, color) in trazos.items():
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
               f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3" '
               'stroke-linecap="round" stroke-linejoin="round"/></svg>')
        ruta = carpeta / f"{nombre}_{tema}.svg"
        try:
            ruta.write_text(svg, encoding="utf-8")
        except OSError:
            pass
        rutas[nombre] = ruta.as_posix()
    return rutas


def construir_qss(p: dict, ic: dict, f_cuerpo: str, f_titulo: str, f_mono: str) -> str:
    return f"""
QWidget {{
    color: {p['texto']};
    font-family: '{f_cuerpo}';
    font-size: {TXT_BODY_MD}px;
}}
QMainWindow, QDialog, QMessageBox, QInputDialog {{ background-color: {p['bg']}; }}
QWidget#raiz, QWidget#contenidoScroll, QWidget#pagina {{ background-color: {p['bg']}; }}

/* ─── Barra superior ─────────────────────────────── */
QFrame#barraSuperior {{
    background-color: {p['superficie']};
    border: none;
    border-bottom: 1px solid {p['borde']};
}}
QLabel[class="titulo-app"] {{
    font-family: '{f_titulo}';
    font-size: {TXT_HEADLINE_MD}px;
    font-weight: 600;
}}

/* ─── Textos ─────────────────────────────────────── */
QLabel {{ background: transparent; }}
QLabel[class="titulo-pagina"] {{
    font-family: '{f_titulo}';
    font-size: {TXT_HEADLINE_MD}px;
    font-weight: 600;
}}
QLabel[class="titulo-card"] {{
    font-family: '{f_titulo}';
    font-size: {TXT_HEADLINE_SM}px;
    font-weight: 600;
}}
QLabel[class="etiqueta"] {{
    font-size: {TXT_LABEL_MD}px;
    font-weight: 600;
    color: {p['texto_suave']};
}}
QLabel[class="suave"] {{ color: {p['texto_suave']}; font-size: {TXT_BODY_SM}px; }}
QLabel[class="aviso"] {{ color: {COLOR_LOG['aviso']}; font-size: {TXT_LABEL_MD}px; font-weight: 600; }}
QLabel[class="ok"] {{ color: {COLOR_LOG['ok']}; font-size: {TXT_LABEL_MD}px; font-weight: 600; }}
QLabel[class="comando"] {{
    font-family: '{f_mono}';
    font-size: {TXT_LABEL_MD}px;
    background-color: {p['superficie_baja']};
    border: 1px solid {p['borde']};
    border-radius: {RADIUS_DEFAULT}px;
    padding: {SPACING_SM}px;
}}
QLabel[class="dato"] {{ font-weight: 600; }}

/* ─── Cards ──────────────────────────────────────── */
QFrame[class="card"] {{
    background-color: {p['superficie']};
    border: 1px solid {p['borde']};
    border-radius: {RADIUS_LG}px;
}}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget#qt_scrollarea_viewport {{ background: transparent; }}

/* ─── Botones ────────────────────────────────────── */
QPushButton {{
    font-size: {TXT_LABEL_MD}px;
    font-weight: 600;
    padding: {SPACING_SM}px {SPACING_MD}px;
    border-radius: {RADIUS_DEFAULT}px;
    border: 1px solid {p['borde']};
    background-color: {p['superficie']};
    color: {p['texto']};
    min-height: 16px;
}}
QPushButton:hover {{ background-color: {p['superficie_baja']}; border-color: {p['borde_fuerte']}; }}
QPushButton:pressed {{ background-color: {p['superficie_alta']}; }}
QPushButton:focus {{ border-color: {p['primario']}; }}
QPushButton:disabled {{
    color: {p['deshabilitado_texto']};
    border-color: {p['borde']};
    background-color: {p['deshabilitado_bg']};
}}
QPushButton[class="primario"] {{
    background-color: {p['primario']};
    color: {p['sobre_primario']};
    border: 1px solid {p['primario']};
}}
QPushButton[class="primario"]:hover {{ background-color: {p['primario_hover']}; border-color: {p['primario_hover']}; }}
QPushButton[class="primario"]:pressed {{ background-color: {p['primario']}; }}
QPushButton[class="primario"]:disabled {{
    background-color: {p['deshabilitado_bg']};
    color: {p['deshabilitado_texto']};
    border-color: {p['borde']};
}}
QPushButton[class="fantasma"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {p['texto_suave']};
    padding: {SPACING_SM}px {SPACING_SM}px;
}}
QPushButton[class="fantasma"]:hover {{ background-color: {p['superficie_alta']}; color: {p['texto']}; }}
QPushButton[class="fantasma"]:disabled {{ background: transparent; color: {p['deshabilitado_texto']}; }}
QPushButton[class="peligro"] {{
    background-color: transparent;
    color: {p['peligro']};
    border: 1px solid {p['peligro']};
}}
QPushButton[class="peligro"]:hover {{ background-color: {p['peligro']}; color: {p['sobre_peligro']}; }}
QPushButton[class="peligro"]:disabled {{
    color: {p['deshabilitado_texto']};
    border-color: {p['borde']};
    background: transparent;
}}

/* ─── Entradas ───────────────────────────────────── */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {p['superficie']};
    border: 1px solid {p['borde']};
    border-radius: {RADIUS_DEFAULT}px;
    padding: {SPACING_XS}px {SPACING_SM}px;
    min-height: 24px;
    selection-background-color: {p['primario_suave']};
    selection-color: {p['texto_primario_suave']};
}}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{ border-color: {p['borde_fuerte']}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {p['primario']}; }}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background-color: {p['deshabilitado_bg']};
    color: {p['deshabilitado_texto']};
}}
QComboBox::drop-down {{ border: none; width: {SPACING_LG}px; }}
QComboBox::down-arrow {{ image: url({ic['abajo']}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background-color: {p['superficie']};
    border: 1px solid {p['borde']};
    padding: {SPACING_XS}px;
    outline: none;
    selection-background-color: {p['primario_suave']};
    selection-color: {p['texto_primario_suave']};
}}
QSpinBox {{ padding-right: {SPACING_LG}px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 20px;
    border: none;
    background: transparent;
}}
QSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-arrow {{ image: url({ic['arriba']}); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url({ic['abajo']}); width: 10px; height: 10px; }}

/* ─── Consola ────────────────────────────────────── */
QPlainTextEdit#consola {{
    font-family: '{f_mono}';
    font-size: {TXT_LABEL_MD}px;
    background-color: {p['consola_bg']};
    border: 1px solid {p['borde']};
    border-radius: {RADIUS_DEFAULT}px;
    padding: {SPACING_SM}px;
    selection-background-color: {p['primario_suave']};
    selection-color: {p['texto_primario_suave']};
}}

/* ─── Listas y tablas ────────────────────────────── */
QListWidget {{
    background-color: {p['superficie_baja']};
    border: 1px solid {p['borde']};
    border-radius: {RADIUS_DEFAULT}px;
    padding: {SPACING_XS}px;
    outline: none;
}}
QListWidget::item {{ padding: {SPACING_XS}px {SPACING_SM}px; border-radius: {RADIUS_DEFAULT}px; }}
QListWidget::item:hover {{ background-color: {p['superficie_alta']}; }}
QListWidget::item:selected {{
    background-color: {p['primario_suave']};
    color: {p['texto_primario_suave']};
}}
QTableWidget {{
    background-color: {p['superficie']};
    alternate-background-color: {p['superficie_baja']};
    border: 1px solid {p['borde']};
    border-radius: {RADIUS_DEFAULT}px;
    gridline-color: transparent;
    outline: none;
    font-size: {TXT_BODY_SM}px;
    selection-background-color: {p['primario_suave']};
    selection-color: {p['texto_primario_suave']};
}}
QTableWidget::item {{ padding: 0 {SPACING_SM}px; }}
QHeaderView {{ background-color: {p['superficie_baja']}; border: none; }}
QHeaderView::section {{
    background-color: {p['superficie_baja']};
    color: {p['texto_suave']};
    font-size: {TXT_LABEL_MD}px;
    font-weight: 600;
    padding: {SPACING_SM}px;
    border: none;
    border-bottom: 1px solid {p['borde']};
}}
QTableCornerButton::section {{ background-color: {p['superficie_baja']}; border: none; }}

/* ─── Checkbox / radio / indicadores ─────────────── */
QCheckBox, QRadioButton {{ spacing: {SPACING_SM}px; background: transparent; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {p['deshabilitado_texto']}; }}
QCheckBox::indicator, QListWidget::indicator, QTableWidget::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {p['borde_fuerte']};
    border-radius: {RADIUS_SM}px;
    background: {p['superficie']};
}}
QCheckBox::indicator:hover, QListWidget::indicator:hover, QTableWidget::indicator:hover {{
    border-color: {p['primario']};
}}
QCheckBox::indicator:checked, QListWidget::indicator:checked, QTableWidget::indicator:checked {{
    background-color: {p['primario']};
    border-color: {p['primario']};
    image: url({ic['check']});
}}
QCheckBox::indicator:disabled {{ border-color: {p['borde']}; background: {p['deshabilitado_bg']}; }}
QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {p['borde_fuerte']};
    border-radius: 10px;
    background: {p['superficie']};
}}
QRadioButton::indicator:hover {{ border-color: {p['primario']}; }}
QRadioButton::indicator:checked {{
    border: 5px solid {p['primario']};
    background: {p['sobre_primario']};
    width: 10px; height: 10px;
}}

/* ─── Pestañas ───────────────────────────────────── */
QTabWidget::pane {{ border: none; background: {p['bg']}; }}
QTabWidget::tab-bar {{ left: {SPACING_LG}px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    padding: {SPACING_SM + SPACING_XS}px {SPACING_MD}px;
    margin-right: {SPACING_XS}px;
    font-size: {TXT_BODY_SM}px;
    font-weight: 600;
    color: {p['texto_suave']};
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {p['primario']}; border-bottom: 2px solid {p['primario']}; }}
QTabBar::tab:hover:!selected {{ color: {p['texto']}; background: {p['superficie_baja']}; }}

/* ─── Varios ─────────────────────────────────────── */
QProgressBar {{
    background-color: {p['superficie_alta']};
    border: none;
    border-radius: {RADIUS_SM}px;
    max-height: 6px;
    min-height: 6px;
}}
QProgressBar::chunk {{ background-color: {p['primario']}; border-radius: {RADIUS_SM}px; }}
QSplitter::handle {{ background: transparent; }}
QToolTip {{
    background-color: {p['tooltip_bg']};
    color: {p['tooltip_texto']};
    border: none;
    padding: {SPACING_XS}px {SPACING_SM}px;
}}
QScrollBar:vertical {{ width: 10px; background: transparent; margin: 0; }}
QScrollBar:horizontal {{ height: 10px; background: transparent; margin: 0; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {p['borde']};
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
    margin: 2px;
}}
QScrollBar::handle:hover {{ background: {p['borde_fuerte']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QMessageBox QPushButton {{ min-width: 72px; }}
"""


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN (JSON junto al script)
# ═════════════════════════════════════════════════════════════════════════════

class Config:
    def __init__(self, ruta: Path):
        self.ruta = ruta
        self.datos: dict = {}
        self.error: str | None = None
        if ruta.exists():
            try:
                with open(ruta, "r", encoding="utf-8") as fh:
                    datos = json.load(fh)
                if isinstance(datos, dict):
                    self.datos = datos
            except Exception as e:
                # No se pierde: se guarda una copia antes de empezar de cero
                try:
                    shutil.copy2(ruta, ruta.with_name(ruta.name + ".bak"))
                except OSError:
                    pass
                self.error = f"No se pudo leer la configuración ({e}). Se guardó una copia .bak."
        self.datos.setdefault("version", 1)
        if self.datos.get("tema") not in PALETAS:
            self.datos["tema"] = "oscuro"

    def seccion(self, nombre: str) -> dict:
        s = self.datos.get(nombre)
        if not isinstance(s, dict):
            s = self.datos[nombre] = {}
        return s

    def guardar(self):
        tmp = self.ruta.with_name(self.ruta.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.datos, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.ruta)
        except OSError as e:
            self.error = f"No se pudo guardar la configuración: {e}"


# ═════════════════════════════════════════════════════════════════════════════
# UTILIDADES GENERALES
# ═════════════════════════════════════════════════════════════════════════════

def norm(ruta) -> str:
    """Ruta normalizada para comparar (mayúsculas/minúsculas en Windows, separadores)."""
    return os.path.normcase(os.path.abspath(str(ruta)))


def esta_dentro(hija, padre) -> bool:
    h, p = norm(hija), norm(padre)
    return h == p or h.startswith(p.rstrip("\\/") + os.sep)


def ruta_libre(destino: Path) -> Path:
    """Si ya existe, añade _1, _2... para no sobrescribir."""
    if not destino.exists():
        return destino
    n = 1
    while True:
        candidato = destino.with_name(f"{destino.stem}_{n}{destino.suffix}")
        if not candidato.exists():
            return candidato
        n += 1


def normalizar_extension(texto: str) -> str:
    e = texto.strip().lower()
    if not e or e == ".":
        return ""
    return e if e.startswith(".") else "." + e


def abrir_en_sistema(ruta):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(ruta)))


def codificacion_consola() -> str:
    if ES_WINDOWS:
        try:
            import ctypes
            return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
        except Exception:
            return "cp850"
    return "utf-8"


def entorno_limpio() -> dict:
    """Variables de entorno para lanzar OTRO python sin que herede las de esta app."""
    env = os.environ.copy()
    for var in ("PYTHONHOME", "PYTHONPATH", "__PYVENV_LAUNCHER__", "PYTHONSTARTUP"):
        env.pop(var, None)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


FLAGS_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Cancelado(Exception):
    pass


def ejecutar_cancelable(tarea, cmd, timeout=600) -> subprocess.CompletedProcess:
    """subprocess.run que se puede cancelar desde la interfaz."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL, env=entorno_limpio(),
                            creationflags=FLAGS_SIN_VENTANA)
    inicio = time.monotonic()
    while True:
        try:
            out, err = proc.communicate(timeout=0.25)
            break
        except subprocess.TimeoutExpired:
            if tarea is not None and tarea.cancelada:
                proc.kill()
                proc.communicate()
                raise Cancelado()
            if time.monotonic() - inicio > timeout:
                proc.kill()
                proc.communicate()
                raise TimeoutError(f"El proceso tardó más de {timeout} s: {cmd[0]}")
    return subprocess.CompletedProcess(
        cmd, proc.returncode,
        out.decode("utf-8", errors="replace"),
        err.decode("utf-8", errors="replace"))


# ─── Localizar el Python de un venv o el global ─────────────────────────────

def buscar_python_venv(texto: str) -> tuple[Path, Path]:
    """Devuelve (python, carpeta_del_venv). Acepta la carpeta del venv, su Scripts/bin o el python."""
    if not texto:
        raise ValueError("Elige la carpeta del entorno virtual.")
    p = Path(texto)
    if p.is_file():
        carpeta = p.parent.parent if p.parent.name.lower() in ("scripts", "bin") else p.parent
        return p, carpeta
    if not p.is_dir():
        raise ValueError(f"No existe la carpeta: {p}")
    if p.name.lower() in ("scripts", "bin"):
        p = p.parent
    for rel in ("Scripts/python.exe", "bin/python", "bin/python3", "python.exe"):
        exe = p / rel
        if exe.is_file():
            return exe, p
    raise ValueError(f"No encontré python dentro de '{p}'. ¿Es la carpeta de un venv?")


def buscar_python_global(tarea=None) -> Path:
    """
    El python que aparece al abrir cmd sin activar ningún venv: el primero del PATH,
    ignorando carpetas de venvs activos y el alias falso de la Microsoft Store.
    """
    excluir = []
    for var in ("VIRTUAL_ENV", "CONDA_PREFIX"):
        if os.environ.get(var):
            excluir.append(os.environ[var])
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        excluir.append(sys.prefix)  # esta app corre dentro de un venv: no contarlo
    entradas = [e for e in os.environ.get("PATH", "").split(os.pathsep)
                if e and not any(esta_dentro(e, x) for x in excluir)]
    ruta_path = os.pathsep.join(entradas)

    candidatos = []
    for nombre in (("python",) if ES_WINDOWS else ("python3", "python")):
        exe = shutil.which(nombre, path=ruta_path)
        if exe and "windowsapps" not in exe.lower():
            candidatos.append([exe])
    if ES_WINDOWS and shutil.which("py"):
        candidatos.append([shutil.which("py"), "-3"])
    base = Path(getattr(sys, "base_prefix", sys.prefix))
    for rel in ("python.exe", "bin/python3", "bin/python"):
        if (base / rel).is_file():
            candidatos.append([str(base / rel)])

    for cmd in candidatos:
        try:
            r = ejecutar_cancelable(tarea, cmd + ["-c", "import sys; print(sys.executable)"], timeout=30)
        except (OSError, TimeoutError):
            continue
        real = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        if r.returncode == 0 and real and Path(real).is_file():
            return Path(real)
    raise RuntimeError("No encontré un Python global en el PATH.")


# ─── Script auxiliar que se ejecuta DENTRO del python elegido ───────────────
# Lee los paquetes con importlib.metadata del propio entorno (y sus licencias).
# Compatible con Python 3.8+.

HELPER_ENTORNO = r'''
import json, os, re, sys
from importlib import metadata

PATRON_LICENCIA = re.compile(
    r"(^|/)(licen[cs]e|licence|copying|notice|authors|copyright)[^/]*$", re.I)
EXT_TEXTO = {"", ".txt", ".md", ".rst", ".text", ".apache", ".bsd", ".mit", ".gpl"}
AVISOS = []

def parece_texto(contenido):
    if not contenido or "\x00" in contenido[:2000]:
        return False
    muestra = contenido[:2000]
    raros = sum(1 for c in muestra if not c.isprintable() and c not in "\n\r\t")
    if raros > len(muestra) * 0.02:
        return False
    pistas = ("import ", "def ", "class ", "@dataclass", "#!/usr/bin/env")
    if sum(1 for p in pistas if p in muestra) >= 2:
        return False
    return True

def leer(ruta):
    for cod in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(ruta, "r", encoding=cod) as fh:
                return fh.read().strip()
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    return ""

def tipo_de_licencia(md):
    exp = md.get("License-Expression")
    if exp:
        return exp.strip()
    for clas in md.get_all("Classifier") or []:
        if clas.startswith("License ::"):
            nombre = clas.split("::")[-1].strip()
            if nombre and nombre != "OSI Approved":
                return nombre
    lic = (md.get("License") or "").strip()
    if lic and "\n" not in lic and len(lic) <= 80:
        return lic
    return "Ver texto de la licencia"

def texto_de_licencia(dist):
    partes = []
    try:
        archivos = list(dist.files or [])
    except Exception:
        archivos = []
    vistos = set()
    for f in archivos:
        ruta = str(f).replace("\\", "/")
        if ".dist-info/" not in ruta and ".egg-info/" not in ruta:
            continue
        if not PATRON_LICENCIA.search(ruta):
            continue
        nombre = ruta.rsplit("/", 1)[-1]
        if os.path.splitext(nombre)[1].lower() not in EXT_TEXTO:
            continue
        if nombre.lower() in vistos:
            continue
        vistos.add(nombre.lower())
        contenido = ""
        try:
            contenido = dist.read_text(str(f)) or ""
        except Exception:
            contenido = ""
        if not contenido.strip():
            try:
                contenido = leer(str(dist.locate_file(f)))
            except Exception:
                contenido = ""
        contenido = (contenido or "").strip()
        if contenido and not parece_texto(contenido):
            AVISOS.append("%s: '%s' no parece una licencia; se omite"
                          % (dist.metadata.get("Name"), nombre))
            contenido = ""
        if contenido:
            etiqueta = "[%s]\n" % nombre if len(vistos) > 1 else ""
            partes.append(etiqueta + contenido)
    if partes:
        return "\n\n".join(partes)
    lic = (dist.metadata.get("License") or "").strip()
    if lic and ("\n" in lic or len(lic) > 80):
        return lic
    if lic:
        return ("Licencia declarada: %s\n"
                "El paquete no incluye el texto completo en su distribución." % lic)
    return ("El paquete no declara licencia ni incluye su texto en la distribución.\n"
            "Consulta el proyecto original para conocer sus términos.")

def main():
    modo, salida = sys.argv[1], sys.argv[2]
    paquetes = {}
    for dist in metadata.distributions():
        try:
            md = dist.metadata
            nombre = (md.get("Name") or "").strip()
            if not nombre or nombre.lower() in paquetes:
                continue
            fila = {"nombre": nombre, "version": dist.version or "?"}
            if modo == "licencias":
                fila["tipo"] = tipo_de_licencia(md)
                fila["texto"] = texto_de_licencia(dist)
            paquetes[nombre.lower()] = fila
        except Exception as e:
            AVISOS.append("No se pudo leer un paquete: %s" % e)
    datos = {
        "version": sys.version,
        "executable": sys.executable,
        "prefix": sys.prefix,
        "base_prefix": getattr(sys, "base_prefix", sys.prefix),
        "paquetes": sorted(paquetes.values(), key=lambda f: f["nombre"].lower()),
        "avisos": AVISOS,
    }
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False)

main()
'''


def leer_entorno(tarea, python: Path, modo: str) -> dict:
    """Ejecuta HELPER_ENTORNO con el python indicado y devuelve sus datos."""
    carpeta = Path(tempfile.mkdtemp(prefix="utilidades_"))
    try:
        script = carpeta / "leer_entorno.py"
        salida = carpeta / "datos.json"
        script.write_text(HELPER_ENTORNO, encoding="utf-8")
        r = ejecutar_cancelable(tarea, [str(python), str(script), modo, str(salida)])
        if r.returncode != 0 or not salida.exists():
            detalle = (r.stderr or r.stdout).strip().splitlines()
            raise RuntimeError("El python elegido no pudo leer sus paquetes"
                               + (f": {detalle[-1]}" if detalle else "."))
        with open(salida, "r", encoding="utf-8") as fh:
            return json.load(fh)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


def resolver_python(tarea, usa_global: bool, venv: str) -> tuple[Path, Path | None]:
    if usa_global:
        tarea.log("Buscando el Python global…", "suave")
        return buscar_python_global(tarea), None
    return buscar_python_venv(venv)


# ═════════════════════════════════════════════════════════════════════════════
# COMPONENTES DE INTERFAZ
# ═════════════════════════════════════════════════════════════════════════════

def tarjeta(titulo: str | None = None, descripcion: str | None = None):
    marco = QFrame()
    marco.setProperty("class", "card")
    lay = QVBoxLayout(marco)
    lay.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
    lay.setSpacing(SPACING_SM)
    if titulo:
        t = QLabel(titulo)
        t.setProperty("class", "titulo-card")
        lay.addWidget(t)
    if descripcion:
        d = QLabel(descripcion)
        d.setProperty("class", "suave")
        d.setWordWrap(True)
        lay.addWidget(d)
    return marco, lay


def boton(texto: str, clase: str | None = None, tooltip: str | None = None) -> QPushButton:
    b = QPushButton(texto)
    if clase:
        b.setProperty("class", clase)
    if tooltip:
        b.setToolTip(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def etiqueta(texto: str, clase: str = "etiqueta") -> QLabel:
    lbl = QLabel(texto)
    lbl.setProperty("class", clase)
    lbl.setWordWrap(True)
    return lbl


def refrescar_estilo(w: QWidget):
    w.style().unpolish(w)
    w.style().polish(w)


class CampoRuta(QLineEdit):
    """QLineEdit que acepta arrastrar carpetas/archivos desde el explorador."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            ruta = e.mimeData().urls()[0].toLocalFile()
            if ruta:
                self.setText(str(Path(ruta)))
            e.acceptProposedAction()
        else:
            super().dropEvent(e)


class SelectorRuta(QWidget):
    """Campo de texto + botón Examinar. modo: 'carpeta' | 'archivo' | 'guardar'."""
    cambiado = pyqtSignal(str)

    def __init__(self, modo="carpeta", placeholder="", filtro="Todos los archivos (*)", parent=None):
        super().__init__(parent)
        self.modo, self.filtro = modo, filtro
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(SPACING_SM)
        self.campo = CampoRuta()
        self.campo.setPlaceholderText(placeholder)
        self.campo.setClearButtonEnabled(True)
        self.campo.textChanged.connect(self.cambiado.emit)
        self.btn = boton("Examinar…")
        self.btn.clicked.connect(self._examinar)
        lay.addWidget(self.campo, 1)
        lay.addWidget(self.btn)

    def _examinar(self):
        inicio = self.texto() or str(Path.home())
        if self.modo == "carpeta":
            r = QFileDialog.getExistingDirectory(self, "Elegir carpeta", inicio)
        elif self.modo == "archivo":
            r, _ = QFileDialog.getOpenFileName(self, "Elegir archivo", inicio, self.filtro)
        else:
            r, _ = QFileDialog.getSaveFileName(self, "Guardar como", inicio, self.filtro)
        if r:
            self.campo.setText(str(Path(r)))

    def texto(self) -> str:
        return self.campo.text().strip().strip('"')

    def establecer(self, texto: str):
        self.campo.setText(texto or "")


class ListaEditable(QWidget):
    """Lista con casillas: agregar (varios separados por coma), quitar, editar con doble clic."""
    cambiado = pyqtSignal()

    def __init__(self, titulo, ayuda="", placeholder="Agregar…", normalizar=None, parent=None):
        super().__init__(parent)
        self.normalizar = normalizar
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SPACING_XS)
        v.addWidget(etiqueta(titulo))
        if ayuda:
            v.addWidget(etiqueta(ayuda, "suave"))

        self.lista = QListWidget()
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista.setMinimumHeight(112)
        self.lista.setMaximumHeight(176)
        self.lista.setToolTip("Desmarca para no usarla sin borrarla. Doble clic para editar.")
        self.lista.itemChanged.connect(self._item_cambiado)
        v.addWidget(self.lista)

        fila = QHBoxLayout()
        fila.setSpacing(SPACING_SM)
        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText(placeholder)
        self.entrada.returnPressed.connect(self.agregar)
        self.btn_agregar = boton("Agregar")
        self.btn_agregar.clicked.connect(self.agregar)
        self.btn_quitar = boton("Quitar", "fantasma", "Quita los elementos seleccionados")
        self.btn_quitar.clicked.connect(self.quitar)
        fila.addWidget(self.entrada, 1)
        fila.addWidget(self.btn_agregar)
        fila.addWidget(self.btn_quitar)
        v.addLayout(fila)

    def _norm(self, texto: str) -> str:
        t = texto.strip().strip('"')
        if t and self.normalizar:
            t = self.normalizar(t)
        return t

    def _nuevo_item(self, texto: str, activo: bool = True) -> QListWidgetItem:
        it = QListWidgetItem(texto)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
        it.setCheckState(Qt.CheckState.Checked if activo else Qt.CheckState.Unchecked)
        return it

    def agregar(self):
        existentes = {t.lower() for t, _ in self.valores()}
        agregados = 0
        self.lista.blockSignals(True)
        for parte in re.split(r"[,;]", self.entrada.text()):
            t = self._norm(parte)
            if t and t.lower() not in existentes:
                self.lista.addItem(self._nuevo_item(t))
                existentes.add(t.lower())
                agregados += 1
        self.lista.blockSignals(False)
        self.entrada.clear()
        if agregados:
            self.cambiado.emit()

    def quitar(self):
        seleccion = self.lista.selectedItems()
        for it in seleccion:
            self.lista.takeItem(self.lista.row(it))
        if seleccion:
            self.cambiado.emit()

    def _item_cambiado(self, it: QListWidgetItem):
        nuevo = self._norm(it.text())
        self.lista.blockSignals(True)
        if not nuevo:
            self.lista.takeItem(self.lista.row(it))
        elif nuevo != it.text():
            it.setText(nuevo)
        self.lista.blockSignals(False)
        self.cambiado.emit()

    def valores(self) -> list:
        return [[self.lista.item(i).text(), self.lista.item(i).checkState() == Qt.CheckState.Checked]
                for i in range(self.lista.count())]

    def activos(self) -> list[str]:
        return [t for t, activo in self.valores() if activo]

    def establecer(self, valores):
        self.lista.blockSignals(True)
        self.lista.clear()
        for v in valores or []:
            texto, activo = (v, True) if isinstance(v, str) else (v[0], bool(v[1]))
            texto = self._norm(texto)
            if texto:
                self.lista.addItem(self._nuevo_item(texto, activo))
        self.lista.blockSignals(False)


PREDETERMINADA = "Predeterminada"


class BarraSesiones(QFrame):
    """
    Combo de sesiones con nombre para una pestaña. 'Predeterminada' siempre existe
    y no se puede sobrescribir. Los cambios sin guardar se marcan, pero se pueden
    usar igual sin guardarlos.
    """
    sesion_cargada = pyqtSignal(dict)

    def __init__(self, config: Config, clave: str, defaults: dict, obtener_estado, parent=None):
        super().__init__(parent)
        self.config, self.clave, self.defaults = config, clave, defaults
        self.obtener_estado = obtener_estado
        self._cargando = False
        self.setProperty("class", "card")

        v = QVBoxLayout(self)
        v.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        v.setSpacing(SPACING_SM)
        fila = QHBoxLayout()
        fila.setSpacing(SPACING_SM)
        fila.addWidget(etiqueta("SESIÓN"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(120)
        self.combo.currentTextChanged.connect(self._al_cambiar)
        fila.addWidget(self.combo, 1)
        self.lbl_mod = etiqueta("● sin guardar", "aviso")
        self.lbl_mod.setWordWrap(False)
        self.lbl_mod.setToolTip("Hay cambios respecto a la sesión elegida. Puedes usarlos sin guardarlos.")
        self.lbl_mod.setVisible(False)
        fila.addWidget(self.lbl_mod)
        v.addLayout(fila)
        fila = QHBoxLayout()
        fila.setSpacing(SPACING_SM)
        self.btn_guardar = boton("Guardar", tooltip="Sobrescribe la sesión elegida")
        self.btn_guardar_como = boton("Guardar como…", tooltip="Guarda la configuración actual con un nombre nuevo")
        self.btn_eliminar = boton("Eliminar", "fantasma", "Elimina la sesión elegida")
        self.btn_guardar.clicked.connect(self.guardar)
        self.btn_guardar_como.clicked.connect(self.guardar_como)
        self.btn_eliminar.clicked.connect(self.eliminar)
        for b in (self.btn_guardar, self.btn_guardar_como, self.btn_eliminar):
            fila.addWidget(b)
        fila.addStretch(1)
        v.addLayout(fila)

    # ─── datos ───
    def _sec(self) -> dict:
        return self.config.seccion(self.clave)

    def _sesiones(self) -> dict:
        s = self._sec().get("sesiones")
        if not isinstance(s, dict):
            s = self._sec()["sesiones"] = {}
        return s

    def _rellenar(self, seleccion: str):
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(PREDETERMINADA)
        for nombre in sorted(self._sesiones(), key=str.lower):
            self.combo.addItem(nombre)
        idx = self.combo.findText(seleccion)
        self.combo.setCurrentIndex(max(idx, 0))
        self.combo.blockSignals(False)
        self._actualizar_botones()

    def _actualizar_botones(self):
        es_pred = self.combo.currentText() == PREDETERMINADA
        self.btn_eliminar.setEnabled(not es_pred)
        self.btn_guardar.setEnabled(not es_pred)

    def _set_mod(self, valor: bool):
        self.lbl_mod.setVisible(valor)

    # ─── acciones ───
    def cargar_inicial(self):
        nombre = self._sec().get("ultima", PREDETERMINADA)
        if nombre not in self._sesiones():
            nombre = PREDETERMINADA
        self._rellenar(nombre)
        self._aplicar(nombre)

    def _al_cambiar(self, nombre: str):
        if not nombre:
            return
        self._aplicar(nombre)
        self._sec()["ultima"] = nombre
        self.config.guardar()

    def _aplicar(self, nombre: str):
        estado = copy.deepcopy(self.defaults)
        if nombre != PREDETERMINADA:
            estado.update(copy.deepcopy(self._sesiones().get(nombre, {})))
        self._cargando = True
        try:
            self.sesion_cargada.emit(estado)
        finally:
            self._cargando = False
        self._set_mod(False)
        self._actualizar_botones()

    def marcar_modificado(self):
        if not self._cargando:
            self._set_mod(True)

    def guardar(self):
        nombre = self.combo.currentText()
        if nombre == PREDETERMINADA:
            self.guardar_como()
            return
        self._sesiones()[nombre] = self.obtener_estado()
        self.config.guardar()
        self._set_mod(False)

    def guardar_como(self):
        sugerido = self.combo.currentText() if self.combo.currentText() != PREDETERMINADA else ""
        nombre, ok = QInputDialog.getText(self, "Guardar sesión", "Nombre de la sesión:", text=sugerido)
        nombre = (nombre or "").strip()
        if not ok or not nombre:
            return
        if nombre.lower() == PREDETERMINADA.lower():
            QMessageBox.warning(self, "Guardar sesión", "Ese nombre está reservado. Elige otro.")
            return
        if nombre in self._sesiones():
            r = QMessageBox.question(self, "Guardar sesión", f"Ya existe «{nombre}». ¿Sobrescribirla?")
            if r != QMessageBox.StandardButton.Yes:
                return
        self._sesiones()[nombre] = self.obtener_estado()
        self._sec()["ultima"] = nombre
        self.config.guardar()
        self._rellenar(nombre)
        self._set_mod(False)

    def eliminar(self):
        nombre = self.combo.currentText()
        if nombre == PREDETERMINADA:
            return
        r = QMessageBox.question(self, "Eliminar sesión", f"¿Eliminar la sesión «{nombre}»?")
        if r != QMessageBox.StandardButton.Yes:
            return
        self._sesiones().pop(nombre, None)
        self._sec()["ultima"] = PREDETERMINADA
        self.config.guardar()
        # Se conservan los valores en pantalla; solo cambia la sesión seleccionada
        self._rellenar(PREDETERMINADA)
        self._set_mod(True)


class SelectorPython(QWidget):
    """Elegir un venv o el Python global."""
    cambiado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SPACING_SM)
        self.rb_venv = QRadioButton("Un entorno virtual (venv)")
        self.rb_global = QRadioButton("Python global (el que sale en cmd sin activar ningún venv)")
        self.rb_venv.setChecked(True)
        grupo = QButtonGroup(self)
        grupo.addButton(self.rb_venv)
        grupo.addButton(self.rb_global)
        v.addWidget(self.rb_venv)
        v.addWidget(self.rb_global)
        self.ruta = SelectorRuta("carpeta", "Carpeta del venv, ej. C:\\proyecto\\.venv")
        v.addWidget(self.ruta)
        self.info = etiqueta("", "suave")
        v.addWidget(self.info)
        self.rb_venv.toggled.connect(self._actualizar)
        self.ruta.cambiado.connect(self._actualizar)
        self._actualizar()

    def usa_global(self) -> bool:
        return self.rb_global.isChecked()

    def venv(self) -> str:
        return self.ruta.texto()

    def carpeta_venv(self) -> Path | None:
        """Carpeta del venv si es válida (para rutas de salida por defecto)."""
        if self.usa_global():
            return None
        try:
            return buscar_python_venv(self.venv())[1]
        except ValueError:
            return None

    def _actualizar(self, *_):
        self.ruta.setEnabled(not self.usa_global())
        if self.usa_global():
            self.info.setText("Se detectará al ejecutar (primer python del PATH).")
            self.info.setProperty("class", "suave")
        elif not self.venv():
            self.info.setText("Elige la carpeta del venv (la que contiene Scripts\\ o bin\\).")
            self.info.setProperty("class", "suave")
        else:
            try:
                exe, _ = buscar_python_venv(self.venv())
                self.info.setText(f"✓ Python encontrado: {exe}")
                self.info.setProperty("class", "ok")
            except ValueError as e:
                self.info.setText(str(e))
                self.info.setProperty("class", "aviso")
        refrescar_estilo(self.info)
        self.cambiado.emit()

    def estado(self) -> dict:
        return {"global": self.usa_global(), "venv": self.venv()}

    def establecer(self, d: dict):
        d = d or {}
        (self.rb_global if d.get("global") else self.rb_venv).setChecked(True)
        if d.get("venv"):
            self.ruta.establecer(d["venv"])
        self._actualizar()


class Consola(QPlainTextEdit):
    """
    Registro de solo lectura. Todo lo que llega se acumula y se escribe en bloque
    ~12 veces por segundo: así miles de líneas por segundo no congelan la interfaz.
    'agregar' escribe mensajes con hora y color; 'alimentar' recibe la salida cruda
    de un proceso (maneja \\r y los porcentajes de robocopy).
    """
    RE_PORCENTAJE = re.compile(r"^\s*\d+(\.\d+)?%\s*$")
    RE_CORTE = re.compile(r"(\r\n|\n|\r)")
    MAX_LINEAS = 20000
    # Dibujar cada línea cuesta ~30 µs; por encima de esto se muestran solo las más
    # recientes de cada tanda (nadie puede leer 20.000 líneas por segundo).
    LIMITE_POR_VACIADO = 1500

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("consola")
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setMaximumBlockCount(self.MAX_LINEAS)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._pendiente: list[tuple] = []
        self._formatos: dict[str, QTextCharFormat] = {}
        self._reiniciar_linea()
        self._cr_pendiente = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._vaciar)

    # ─── API ───
    def agregar(self, texto: str, tipo: str = "normal"):
        self._pendiente.append(("msg", str(texto), tipo, time.strftime("%H:%M:%S")))
        self._programar()

    def alimentar(self, texto: str):
        if texto:
            self._pendiente.append(("raw", texto))
            self._programar()

    def cerrar_linea(self):
        self._pendiente.append(("fin",))
        self._programar()

    def limpiar(self):
        self._pendiente.clear()
        self.clear()
        self._reiniciar_linea()
        self._cr_pendiente = False

    # ─── internos ───
    def _programar(self):
        if not self._timer.isActive():
            self._timer.start()

    def _reiniciar_linea(self):
        self._linea, self._pct, self._tras_cr = "", "", False

    def _viva(self) -> str:
        return self._linea + (f"   {self._pct.strip()}" if self._pct else "")

    def _formato(self, tipo: str) -> QTextCharFormat:
        f = self._formatos.get(tipo)
        if f is None:
            f = QTextCharFormat()
            color = COLOR_LOG.get(tipo)
            if color:
                f.setForeground(QColor(color))
            if tipo == "titulo":
                f.setFontWeight(QFont.Weight.Bold)
            self._formatos[tipo] = f
        return f

    def _al_final(self) -> bool:
        barra = self.verticalScrollBar()
        return barra.value() >= barra.maximum() - 4

    def _procesar_crudo(self, texto: str) -> list[str]:
        """Actualiza la línea en curso y devuelve las líneas que quedaron terminadas."""
        if self._cr_pendiente:
            texto, self._cr_pendiente = "\r" + texto, False
        if texto.endswith("\r"):  # puede ser la mitad de un \r\n: se decide con el siguiente trozo
            texto, self._cr_pendiente = texto[:-1], True
        terminadas = []
        for parte in self.RE_CORTE.split(texto):
            if parte in ("\r\n", "\n"):
                terminadas.append(self._viva())
                self._reiniciar_linea()
            elif parte == "\r":
                self._tras_cr = True
            elif parte:
                if self.RE_PORCENTAJE.match(parte):
                    self._pct = parte
                elif self._tras_cr:
                    self._linea, self._pct = parte, ""
                else:
                    self._linea += parte
                self._tras_cr = False
        return terminadas

    def _escribir_crudo(self, c: QTextCursor, terminadas: list[str]):
        """Sustituye la última línea (la 'viva') por las terminadas + la nueva línea viva."""
        if len(terminadas) > self.LIMITE_POR_VACIADO:
            omitidas = len(terminadas) - self.LIMITE_POR_VACIADO
            terminadas = [f"… {omitidas:,} líneas sin mostrar (llegan demasiado rápido)"] \
                + terminadas[-self.LIMITE_POR_VACIADO:]
        c.movePosition(QTextCursor.MoveOperation.End)
        c.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        c.insertText("\n".join(terminadas + [self._viva()]), QTextCharFormat())

    def _escribir_msg(self, c: QTextCursor, texto: str, tipo: str, hora: str):
        c.movePosition(QTextCursor.MoveOperation.End)
        for i, linea in enumerate(texto.splitlines() or [""]):
            c.insertText(f"[{hora}] " if i == 0 else " " * 11, self._formato("suave"))
            c.insertText(linea, self._formato(tipo))
            c.insertText("\n", QTextCharFormat())

    def _vaciar(self):
        items, self._pendiente = self._pendiente, []
        if not items:
            return
        # Si llegó una avalancha de mensajes, solo se muestran los últimos
        sobran = len(items) - self.LIMITE_POR_VACIADO
        omitidos = 0
        while sobran > 0 and items[omitidos][0] == "msg":
            omitidos += 1
            sobran -= 1
        if omitidos:
            items = [("msg", f"… {omitidos:,} líneas sin mostrar (llegan demasiado rápido)", "suave",
                      time.strftime("%H:%M:%S"))] + items[omitidos:]

        abajo = self._al_final()
        c = QTextCursor(self.document())
        c.beginEditBlock()
        terminadas: list[str] = []
        for item in items:
            if item[0] == "raw":
                terminadas += self._procesar_crudo(item[1])
                continue
            # 'fin' o 'msg': primero se cierra la línea cruda que estuviera a medias
            self._cr_pendiente = False
            if self._linea or self._pct:
                terminadas.append(self._viva())
                self._reiniciar_linea()
            if terminadas:
                # La línea viva ya está vacía, así que esto termina en salto de línea
                self._escribir_crudo(c, terminadas)
                terminadas = []
            if item[0] == "msg":
                self._escribir_msg(c, item[1], item[2], item[3])
        self._escribir_crudo(c, terminadas)
        c.endEditBlock()
        if abajo:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


# ═════════════════════════════════════════════════════════════════════════════
# TAREAS EN SEGUNDO PLANO
# ═════════════════════════════════════════════════════════════════════════════

class Tarea(QThread):
    """
    Ejecuta funcion(tarea, *args) en otro hilo. La función usa tarea.log/progreso/revisar.
    Los mensajes y el progreso se guardan aquí y la página los recoge cada 100 ms
    (en vez de una señal por línea, que satura la interfaz).
    """
    listo = pyqtSignal(object)
    fallo = pyqtSignal(str)
    cancelado = pyqtSignal()

    def __init__(self, funcion, *args, parent=None):
        super().__init__(parent)
        self._funcion, self._args = funcion, args
        self.cancelada = False
        self._lock = threading.Lock()
        self._mensajes: list[tuple[str, str]] = []
        self._avance: tuple | None = None

    def cancelar(self):
        self.cancelada = True

    def revisar(self):
        if self.cancelada:
            raise Cancelado()

    def log(self, texto: str, tipo: str = "normal"):
        with self._lock:
            self._mensajes.append((texto, tipo))

    def progreso(self, actual: int, total: int, texto: str = ""):
        self._avance = (actual, total, texto)

    def tomar(self) -> tuple[list, tuple | None]:
        with self._lock:
            mensajes, self._mensajes = self._mensajes, []
        avance, self._avance = self._avance, None
        return mensajes, avance

    def run(self):
        try:
            self.listo.emit(self._funcion(self, *self._args))
        except Cancelado:
            self.cancelado.emit()
        except Exception as e:
            self.fallo.emit(f"{type(e).__name__}: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA BASE
# ═════════════════════════════════════════════════════════════════════════════

class Pagina(QWidget):
    """Formulario a la izquierda (con scroll) + registro y progreso a la derecha."""

    def __init__(self, ventana, titulo: str, descripcion: str):
        super().__init__()
        self.setObjectName("pagina")
        self.ventana = ventana
        self.config: Config = ventana.config
        self.tarea: Tarea | None = None
        self._acciones: list[QPushButton] = []
        self.salio_bien = True   # la barra queda llena solo si la última operación terminó bien

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_LG)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(SPACING_MD)
        raiz.addWidget(splitter)

        # ─── Izquierda ───
        izq = QWidget()
        vi = QVBoxLayout(izq)
        vi.setContentsMargins(0, 0, 0, 0)
        vi.setSpacing(SPACING_MD)
        cab = QVBoxLayout()
        cab.setSpacing(SPACING_XS)
        lbl_t = QLabel(titulo)
        lbl_t.setProperty("class", "titulo-pagina")
        cab.addWidget(lbl_t)
        cab.addWidget(etiqueta(descripcion, "suave"))
        vi.addLayout(cab)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.formulario = QWidget()
        self.formulario.setObjectName("contenidoScroll")
        self.cuerpo = QVBoxLayout(self.formulario)
        self.cuerpo.setContentsMargins(0, 0, SPACING_MD, 0)
        self.cuerpo.setSpacing(SPACING_MD)
        self.scroll.setWidget(self.formulario)
        vi.addWidget(self.scroll, 1)

        self.fila_acciones = QHBoxLayout()
        self.fila_acciones.setSpacing(SPACING_SM)
        self.fila_acciones.addStretch(1)
        self.btn_cancelar = boton("Cancelar", "peligro")
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self.cancelar)
        self.fila_acciones.addWidget(self.btn_cancelar)
        vi.addLayout(self.fila_acciones)

        # ─── Derecha ───
        der, vd = tarjeta()
        cab_d = QHBoxLayout()
        lbl_r = QLabel("Registro")
        lbl_r.setProperty("class", "titulo-card")
        cab_d.addWidget(lbl_r)
        cab_d.addStretch(1)
        btn_limpiar = boton("Limpiar", "fantasma")
        cab_d.addWidget(btn_limpiar)
        vd.addLayout(cab_d)
        self.consola = Consola()
        btn_limpiar.clicked.connect(self.consola.limpiar)
        vd.addWidget(self.consola, 1)
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setRange(0, 1)
        self.barra.setValue(0)
        vd.addWidget(self.barra)
        self.lbl_estado = etiqueta("Listo.", "suave")
        vd.addWidget(self.lbl_estado)

        splitter.addWidget(izq)
        splitter.addWidget(der)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([620, 600])

    # ─── helpers para subclases ───
    def agregar_accion(self, b: QPushButton):
        self.fila_acciones.insertWidget(len(self._acciones), b)
        self._acciones.append(b)

    def estado(self, texto: str):
        self.lbl_estado.setText(texto)

    def set_ocupado(self, ocupado: bool):
        self.formulario.setEnabled(not ocupado)
        for b in self._acciones:
            b.setEnabled(not ocupado)
        self.btn_cancelar.setEnabled(ocupado)
        if ocupado:
            self.salio_bien = True
            self.barra.setRange(0, 0)
        else:
            self.barra.setRange(0, 1)
            self.barra.setValue(1 if self.salio_bien else 0)
            self.actualizar_acciones()

    def actualizar_acciones(self):
        """Las subclases lo usan para habilitar botones según el estado."""

    def ocupada(self) -> bool:
        return self.tarea is not None

    def lanzar(self, funcion, args: tuple, al_terminar, texto_estado="Trabajando…"):
        self.tarea = t = Tarea(funcion, *args, parent=self)
        t.listo.connect(lambda r: (self._drenar(), al_terminar(r)))
        t.fallo.connect(self._fallo)
        t.cancelado.connect(self._cancelado)
        t.finished.connect(self._terminada)
        if not hasattr(self, "_sondeo"):
            self._sondeo = QTimer(self)
            self._sondeo.setInterval(100)
            self._sondeo.timeout.connect(self._drenar)
        self.estado(texto_estado)
        self.set_ocupado(True)
        self._sondeo.start()
        t.start()

    def _drenar(self):
        """Pasa al registro y a la barra lo que la tarea fue dejando desde la última vez."""
        if self.tarea is None:
            return
        mensajes, avance = self.tarea.tomar()
        for texto, tipo in mensajes:
            self.consola.agregar(texto, tipo)
        if avance:
            self._avance(*avance)

    def _avance(self, actual: int, total: int, texto: str):
        if total > 0:
            self.barra.setRange(0, total)
            self.barra.setValue(actual)
        else:
            self.barra.setRange(0, 0)
        if texto:
            self.estado(texto)

    def _fallo(self, mensaje: str):
        self.salio_bien = False
        self._drenar()
        self.consola.agregar(mensaje, "error")
        self.estado("Terminó con error.")

    def _cancelado(self):
        self.salio_bien = False
        self._drenar()
        self.consola.agregar("Operación cancelada.", "aviso")
        self.estado("Cancelado.")

    def _terminada(self):
        self._drenar()
        self._sondeo.stop()
        if self.tarea is not None:
            self.tarea.deleteLater()
        self.tarea = None
        self.set_ocupado(False)

    def cancelar(self):
        if self.tarea is not None:
            self.tarea.cancelar()
            self.estado("Cancelando…")

    def esperar(self, ms: int = 3000):
        if self.tarea is not None:
            self.tarea.wait(ms)

    def error(self, texto: str):
        QMessageBox.warning(self, APP_NOMBRE, texto)


def grid_opciones() -> QGridLayout:
    g = QGridLayout()
    g.setHorizontalSpacing(SPACING_MD)
    g.setVerticalSpacing(SPACING_SM)
    g.setColumnStretch(1, 1)
    return g


# ═════════════════════════════════════════════════════════════════════════════
# 1. COPIAR (ROBOCOPY)
# ═════════════════════════════════════════════════════════════════════════════

HILOS_CPU = os.cpu_count() or 8
# Robocopy usa 8 por defecto. Se escala con los hilos lógicos del PC, sin pasar de 32:
# el límite real suele ser el disco, no la CPU.
HILOS_RECOMENDADOS = max(8, min(32, HILOS_CPU))
HILOS_USB = 4
HILOS_HDD = 8
# Para el tiempo restante cada archivo "cuesta" como 64 KB extra: copiar miles de
# archivos pequeños tarda mucho más de lo que dicen sus bytes.
COSTO_POR_ARCHIVO = 64 * 1024

DEFAULT_COPIAR = {
    "origen": "",
    "destino": "",
    "copiar_carpeta": True,
    "excluir_carpetas": [[".venv*", True], ["__pycache__", True], ["venv*", True], ["build*", True]],
    "excluir_archivos": [],
    "reintentos": 4,
    "espera": 5,
    "multihilo": True,
    "hilos_auto": True,
    "hilos": HILOS_RECOMENDADOS,
    "calcular_total": True,
    "simular": False,
    "sin_porcentaje": False,
    "guardar_registro": False,
    "extra": "",
}
CARPETA_REGISTROS = carpeta_app() / "registros"


def formatear_bytes(n: float) -> str:
    for unidad in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.1f} {unidad}"
        n /= 1024
    return f"{n:.2f} TB"


def formatear_duracion(seg: float) -> str:
    seg = int(max(seg, 0))
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


# ─── Tipo de disco (solo Windows) ───────────────────────────────────────────

NOMBRES_TIPO_DISCO = {"usb": "USB / tarjeta", "hdd": "disco mecánico (HDD)", "ssd": "SSD",
                      "red": "red", "desconocido": "tipo desconocido"}


def info_unidad(ruta: str) -> dict | None:
    """
    {'unidad': 'E:', 'tipo': 'usb'|'hdd'|'ssd'|'red'|'desconocido', 'modelo': str}
    Usa el bus del disco (IOCTL_STORAGE_QUERY_PROPERTY), así detecta también los discos
    USB externos que Windows muestra como "fijos". None si no se puede saber.
    """
    if not ES_WINDOWS or not ruta:
        return None
    ruta = ntpath.abspath(ruta)
    if ruta.startswith("\\\\"):
        return {"unidad": "\\\\" + ruta.lstrip("\\").split("\\")[0], "tipo": "red", "modelo": ""}
    unidad = ntpath.splitdrive(ruta)[0].upper()
    if len(unidad) != 2:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        k32.GetDriveTypeW.restype = wintypes.UINT
        tipo_windows = k32.GetDriveTypeW(unidad + "\\")
        if tipo_windows in (0, 1):      # desconocida / no existe
            return None
        if tipo_windows == 4:           # unidad de red mapeada
            return {"unidad": unidad, "tipo": "red", "modelo": ""}

        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                        wintypes.LPVOID]
        k32.DeviceIoControl.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]

        # Acceso 0 = solo consultar (no necesita permisos de administrador)
        h = k32.CreateFileW(f"\\\\.\\{unidad}", 0, 0x1 | 0x2, None, 3, 0, None)
        if not h or h == ctypes.c_void_p(-1).value:
            return {"unidad": unidad, "tipo": "usb" if tipo_windows == 2 else "desconocido", "modelo": ""}
        try:
            def consultar(propiedad: int, tamano: int) -> bytes | None:
                consulta = (ctypes.c_ubyte * 12)()      # STORAGE_PROPERTY_QUERY
                ctypes.c_uint32.from_buffer(consulta, 0).value = propiedad
                salida = (ctypes.c_ubyte * tamano)()
                devuelto = wintypes.DWORD(0)
                ok = k32.DeviceIoControl(h, 0x002D1400, consulta, 12, salida, tamano,
                                         ctypes.byref(devuelto), None)
                return bytes(salida[:devuelto.value]) if ok else None

            bus = modelo = None
            d = consultar(0, 1024)                       # StorageDeviceProperty
            if d and len(d) >= 32:
                bus = int.from_bytes(d[28:32], "little")
                partes = []
                for off in (int.from_bytes(d[12:16], "little"), int.from_bytes(d[16:20], "little")):
                    if 0 < off < len(d):
                        partes.append(d[off:].split(b"\0", 1)[0].decode("ascii", "ignore").strip())
                modelo = " ".join(p for p in partes if p)
            penaliza = None
            d = consultar(7, 12)                         # StorageDeviceSeekPenaltyProperty
            if d and len(d) >= 9:
                penaliza = bool(d[8])
        finally:
            k32.CloseHandle(h)

        if bus in (7, 12, 13) or tipo_windows == 2:      # USB, SD, MMC o extraíble
            tipo = "usb"
        elif bus == 17 or penaliza is False:             # NVMe o sin penalización de búsqueda
            tipo = "ssd"
        elif penaliza:
            tipo = "hdd"
        else:
            tipo = "desconocido"
        return {"unidad": unidad, "tipo": tipo, "modelo": modelo or ""}
    except Exception:
        return None


def hilos_segun_discos(infos: list) -> tuple[int, str]:
    tipos = {i["tipo"] for i in infos if i}
    if "usb" in tipos:
        return HILOS_USB, "hay una unidad USB"
    if "hdd" in tipos:
        return HILOS_HDD, "hay un disco mecánico"
    if not tipos:
        return HILOS_RECOMENDADOS, f"tu PC tiene {HILOS_CPU} hilos lógicos"
    return HILOS_RECOMENDADOS, f"discos rápidos y {HILOS_CPU} hilos lógicos"


# ─── Robocopy: salida y progreso ────────────────────────────────────────────

def describir_codigo_robocopy(codigo: int) -> tuple[str, str]:
    if codigo >= 16:
        return "error", f"Código {codigo}: error grave, robocopy no copió nada (revisa rutas y permisos)."
    partes = []
    if codigo == 0:
        partes.append("No había nada que copiar: el destino ya estaba al día.")
    if codigo & 1:
        partes.append("Se copiaron archivos correctamente.")
    if codigo & 2:
        partes.append("Hay archivos o carpetas extra en el destino (no se tocaron).")
    if codigo & 4:
        partes.append("Se detectaron archivos no coincidentes.")
    if codigo & 8:
        partes.append("Algunos archivos o carpetas NO se pudieron copiar (revisa el registro).")
    tipo = "error" if codigo & 8 else ("aviso" if codigo & 4 else "ok")
    return tipo, f"Código {codigo}: " + " ".join(partes)


def limpiar_ruta_robocopy(r: str) -> str:
    r = r.strip().strip('"')
    if not re.fullmatch(r"[A-Za-z]:[\\/]?", r):
        r = r.rstrip("\\/")
    return r


# Filas del resumen final con 6 números (Total, Copiado, Omitido, No coinc., Error, Extras).
# Se identifican por su orden (Carpetas, Archivos, Bytes), no por el texto, que cambia con el idioma.
RE_RESUMEN = re.compile(r"^\s*[^\d\s][^:]*:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$")


def leer_resumen_robocopy(texto: str) -> dict | None:
    filas = [tuple(int(x) for x in m.groups())
             for m in (RE_RESUMEN.match(linea) for linea in texto.splitlines()) if m]
    if len(filas) < 3:
        return None
    archivos, bytes_ = filas[1], filas[2]
    return {"archivos": archivos[1], "bytes": bytes_[1], "omitidos": archivos[2]}


class ProgresoRobocopy:
    """
    Lee la salida de robocopy (con /BYTES) y lleva la cuenta de bytes y archivos copiados.
    Cada línea de archivo trae su tamaño; el archivo anterior se da por terminado cuando
    aparece el siguiente, y el % por archivo (sin /MT) afina el avance dentro de uno grande.
    """
    RE_ARCHIVO = re.compile(r"\t\s*(\d+)\t(.*\S)\s*$")
    RE_GUIONES = re.compile(r"^\s*-{20,}\s*$")

    def __init__(self, sin_cabecera: bool):
        # Con cabecera, la lista de archivos va entre la 3.ª y la 4.ª línea de guiones
        self._cuerpo = 0 if sin_cabecera else 3
        self._guiones = 0
        self._buffer = ""
        self._actual: int | None = None
        self._pct = 0.0
        self.bytes_hechos = 0
        self.archivos_hechos = 0

    def alimentar(self, texto: str):
        self._buffer += texto
        partes = re.split(r"\r\n|\n|\r", self._buffer)
        self._buffer = partes.pop()
        for linea in partes:
            self._linea(linea)
        if Consola.RE_PORCENTAJE.match(self._buffer):
            self._linea(self._buffer)
            self._buffer = ""

    def _linea(self, linea: str):
        if Consola.RE_PORCENTAJE.match(linea):
            try:
                self._pct = float(linea.strip().rstrip("%"))
            except ValueError:
                pass
            return
        if self.RE_GUIONES.match(linea):
            self._guiones += 1
            return
        if self._guiones != self._cuerpo:
            return
        m = self.RE_ARCHIVO.search(linea)
        if not m or "*" in linea[:m.start()]:      # '*EXTRA': solo existe en el destino
            return
        if m.group(2).endswith(("\\", "/")):       # es una carpeta
            return
        self._cerrar_actual()
        self._actual, self._pct = int(m.group(1)), 0.0

    def _cerrar_actual(self):
        if self._actual is not None:
            self.bytes_hechos += self._actual
            self.archivos_hechos += 1
            self._actual = None

    def terminar(self):
        self._cerrar_actual()

    def hechos(self) -> tuple[float, int]:
        parcial = self._actual * min(self._pct, 100.0) / 100 if self._actual else 0
        return self.bytes_hechos + parcial, self.archivos_hechos


class PaginaCopiar(Pagina):
    def __init__(self, ventana):
        super().__init__(ventana, "Copiar con Robocopy",
                         "Copia una carpeta con todas sus subcarpetas omitiendo lo que no quieras. "
                         "La salida de robocopy se ve en vivo en el registro.")
        self.proceso: QProcess | None = None
        self._fase: str | None = None           # 'calculo' | 'copia'
        self._cancelado = False
        self._totales: dict | None = None
        self._progreso: ProgresoRobocopy | None = None
        self._muestras: deque = deque()
        self._t_inicio = 0.0
        self._salida_calculo: list[str] = []
        self._args_copia: list[str] = []
        self._cache_discos: dict[str, dict | None] = {}
        self._archivo_registro = None
        self._ruta_registro: Path | None = None

        self.sesiones = BarraSesiones(self.config, "copiar", DEFAULT_COPIAR, self.obtener_estado)
        self.sesiones.sesion_cargada.connect(self.aplicar_estado)
        self.cuerpo.addWidget(self.sesiones)

        # Rutas
        card, lay = tarjeta("Rutas", "También puedes arrastrar carpetas desde el explorador.")
        lay.addWidget(etiqueta("ORIGEN"))
        self.origen = SelectorRuta("carpeta", "Carpeta que quieres copiar")
        lay.addWidget(self.origen)
        lay.addWidget(etiqueta("DESTINO"))
        self.destino = SelectorRuta("carpeta", "Carpeta donde quedará la copia")
        lay.addWidget(self.destino)
        self.chk_carpeta = QCheckBox("Copiar la carpeta completa, no solo su contenido (como Ctrl+C / Ctrl+V)")
        lay.addWidget(self.chk_carpeta)
        self.lbl_resultado = etiqueta("", "suave")
        lay.addWidget(self.lbl_resultado)
        self.cuerpo.addWidget(card)

        # Exclusiones
        card, lay = tarjeta("Qué omitir")
        self.lista_carpetas = ListaEditable(
            "CARPETAS A OMITIR (/XD)", "Nombres o comodines: node_modules, .git, build*…",
            "Agregar carpeta o patrón (varios separados por coma)")
        self.lista_archivos = ListaEditable(
            "ARCHIVOS A OMITIR (/XF)", "Nombres o comodines: *.tmp, *.log, Thumbs.db…",
            "Agregar archivo o patrón (varios separados por coma)")
        lay.addWidget(self.lista_carpetas)
        lay.addSpacing(SPACING_SM)
        lay.addWidget(self.lista_archivos)
        self.cuerpo.addWidget(card)

        # Opciones
        card, lay = tarjeta("Opciones")
        g = grid_opciones()
        self.sp_reintentos = QSpinBox()
        self.sp_reintentos.setRange(0, 9999)
        self.sp_espera = QSpinBox()
        self.sp_espera.setRange(0, 3600)
        self.sp_espera.setSuffix(" s")
        self.chk_mt = QCheckBox("Multihilo (/MT)")
        self.chk_mt.setToolTip("Copia varios archivos a la vez. Más rápido con muchos archivos pequeños.")
        fila_hilos = QHBoxLayout()
        fila_hilos.setSpacing(SPACING_SM)
        self.sp_hilos = QSpinBox()
        self.sp_hilos.setRange(1, 128)
        self.sp_hilos.setSuffix(" hilos")
        self.chk_auto = QCheckBox("Automático según el disco")
        self.chk_auto.setToolTip(f"USB o tarjeta: {HILOS_USB} · disco mecánico: {HILOS_HDD} · "
                                 f"SSD/NVMe: {HILOS_RECOMENDADOS} (tu PC tiene {HILOS_CPU} hilos lógicos)")
        fila_hilos.addWidget(self.sp_hilos, 1)
        fila_hilos.addWidget(self.chk_auto)
        self.lbl_discos = etiqueta("", "suave")
        self.chk_total = QCheckBox("Calcular el total antes de copiar (para ver % y tiempo restante)")
        self.chk_total.setToolTip("Hace una pasada rápida sin copiar nada (/L) para saber cuántos "
                                  "archivos y bytes hay que copiar de verdad.")
        self.chk_simular = QCheckBox("Solo simular (/L): muestra qué haría sin copiar nada")
        self.chk_np = QCheckBox("Ocultar el % de cada archivo (/NP)")
        self.chk_registro = QCheckBox("Guardar el registro completo en un .txt (carpeta «registros» junto a la app)")
        self.chk_registro.setToolTip("Si robocopy va muy rápido, en pantalla solo se ven las últimas líneas; "
                                     "el .txt guarda todas.")
        self.txt_extra = QLineEdit()
        self.txt_extra.setPlaceholderText("Parámetros extra, ej. /XO /XJ")
        g.addWidget(etiqueta("REINTENTOS (/R)"), 0, 0)
        g.addWidget(self.sp_reintentos, 0, 1)
        g.addWidget(etiqueta("ESPERA ENTRE REINTENTOS (/W)"), 1, 0)
        g.addWidget(self.sp_espera, 1, 1)
        g.addWidget(self.chk_mt, 2, 0)
        g.addLayout(fila_hilos, 2, 1)
        g.addWidget(self.lbl_discos, 3, 1)
        g.addWidget(self.chk_total, 4, 0, 1, 2)
        g.addWidget(self.chk_simular, 5, 0, 1, 2)
        g.addWidget(self.chk_np, 6, 0, 1, 2)
        g.addWidget(self.chk_registro, 7, 0, 1, 2)
        g.addWidget(etiqueta("EXTRA"), 8, 0)
        g.addWidget(self.txt_extra, 8, 1)
        lay.addLayout(g)
        self.cuerpo.addWidget(card)

        # Comando
        card, lay = tarjeta("Comando")
        self.lbl_comando = QLabel()
        self.lbl_comando.setProperty("class", "comando")
        self.lbl_comando.setWordWrap(True)
        self.lbl_comando.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl_comando)
        if not ES_WINDOWS:
            lay.addWidget(etiqueta("Robocopy solo existe en Windows: aquí solo puedes ver el comando.", "aviso"))
        self.cuerpo.addWidget(card)
        self.cuerpo.addStretch(1)

        self.btn_copiar = boton("Iniciar copia", "primario")
        self.btn_copiar.clicked.connect(self.iniciar)
        self.agregar_accion(self.btn_copiar)

        # Timers: detección de discos (espera a que termines de escribir) y progreso
        self._timer_discos = QTimer(self)
        self._timer_discos.setSingleShot(True)
        self._timer_discos.setInterval(400)
        self._timer_discos.timeout.connect(self._detectar_discos)
        self._reloj = QTimer(self)
        self._reloj.setInterval(500)
        self._reloj.timeout.connect(self._actualizar_progreso)

        for sig in (self.origen.cambiado, self.destino.cambiado, self.chk_carpeta.toggled,
                    self.lista_carpetas.cambiado, self.lista_archivos.cambiado,
                    self.sp_reintentos.valueChanged, self.sp_espera.valueChanged, self.chk_mt.toggled,
                    self.chk_auto.toggled, self.sp_hilos.valueChanged, self.chk_total.toggled,
                    self.chk_simular.toggled, self.chk_np.toggled, self.chk_registro.toggled,
                    self.txt_extra.textChanged):
            sig.connect(self._cambio)
        for sig in (self.origen.cambiado, self.destino.cambiado, self.chk_carpeta.toggled):
            sig.connect(lambda *_: self._timer_discos.start())
        self.chk_auto.toggled.connect(lambda *_: self._detectar_discos())

        self.sesiones.cargar_inicial()
        self._detectar_discos()
        self._cambio()

    # ─── estado / sesiones ───
    def obtener_estado(self) -> dict:
        return {
            "origen": self.origen.texto(),
            "destino": self.destino.texto(),
            "copiar_carpeta": self.chk_carpeta.isChecked(),
            "excluir_carpetas": self.lista_carpetas.valores(),
            "excluir_archivos": self.lista_archivos.valores(),
            "reintentos": self.sp_reintentos.value(),
            "espera": self.sp_espera.value(),
            "multihilo": self.chk_mt.isChecked(),
            "hilos_auto": self.chk_auto.isChecked(),
            "hilos": self.sp_hilos.value(),
            "calcular_total": self.chk_total.isChecked(),
            "simular": self.chk_simular.isChecked(),
            "sin_porcentaje": self.chk_np.isChecked(),
            "guardar_registro": self.chk_registro.isChecked(),
            "extra": self.txt_extra.text().strip(),
        }

    def aplicar_estado(self, e: dict):
        # Las rutas solo se cambian si la sesión trae alguna (así 'Predeterminada' no borra lo escrito)
        if e.get("origen"):
            self.origen.establecer(e["origen"])
        if e.get("destino"):
            self.destino.establecer(e["destino"])
        self.chk_registro.setChecked(bool(e.get("guardar_registro")))
        self.chk_carpeta.setChecked(bool(e.get("copiar_carpeta", True)))
        self.lista_carpetas.establecer(e.get("excluir_carpetas"))
        self.lista_archivos.establecer(e.get("excluir_archivos"))
        self.sp_reintentos.setValue(int(e.get("reintentos", 4)))
        self.sp_espera.setValue(int(e.get("espera", 5)))
        self.chk_mt.setChecked(bool(e.get("multihilo", True)))
        self.chk_auto.setChecked(bool(e.get("hilos_auto", True)))
        self.sp_hilos.setValue(int(e.get("hilos", HILOS_RECOMENDADOS)))
        self.chk_total.setChecked(bool(e.get("calcular_total", True)))
        self.chk_simular.setChecked(bool(e.get("simular")))
        self.chk_np.setChecked(bool(e.get("sin_porcentaje")))
        self.txt_extra.setText(e.get("extra", ""))
        self._detectar_discos()
        self._cambio()

    def _cambio(self, *_):
        self.sesiones.marcar_modificado()
        self.chk_auto.setEnabled(self.chk_mt.isChecked())
        self.sp_hilos.setEnabled(self.chk_mt.isChecked() and not self.chk_auto.isChecked())
        self.chk_total.setEnabled(not self.chk_simular.isChecked())
        destino = self.destino_efectivo()
        if not destino:
            self.lbl_resultado.setText("")
        elif self.chk_carpeta.isChecked() and destino == limpiar_ruta_robocopy(self.destino.texto()):
            self.lbl_resultado.setText("El origen es una unidad completa: se copiará su contenido.")
        else:
            self.lbl_resultado.setText(f"La copia quedará en: {destino}")
        self.lbl_comando.setText(self._comando_texto(self.argumentos()))

    # ─── discos / hilos ───
    def _info_disco(self, ruta: str, refrescar: bool = False) -> dict | None:
        if not ruta:
            return None
        clave = ntpath.splitdrive(ntpath.abspath(ruta))[0].upper() if ES_WINDOWS else ruta
        if refrescar or clave not in self._cache_discos:
            self._cache_discos[clave] = info_unidad(ruta)
        return self._cache_discos[clave]

    def _detectar_discos(self, refrescar: bool = False):
        infos = [self._info_disco(self.origen.texto(), refrescar),
                 self._info_disco(self.destino.texto(), refrescar)]
        hilos, motivo = hilos_segun_discos(infos)
        partes = []
        for nombre, info in (("Origen", infos[0]), ("Destino", infos[1])):
            if info:
                modelo = f" · {info['modelo']}" if info["modelo"] else ""
                partes.append(f"{nombre} {info['unidad']}: {NOMBRES_TIPO_DISCO[info['tipo']]}{modelo}")
        texto = " | ".join(partes) if partes else "No se pudo detectar el tipo de disco."
        self.lbl_discos.setText(f"{texto}\nRecomendado: {hilos} hilos ({motivo}).")
        if self.chk_auto.isChecked() and self.sp_hilos.value() != hilos:
            # Cambio automático: no cuenta como modificación de la sesión
            self.sp_hilos.blockSignals(True)
            self.sp_hilos.setValue(hilos)
            self.sp_hilos.blockSignals(False)
            self.lbl_comando.setText(self._comando_texto(self.argumentos()))

    # ─── robocopy ───
    def destino_efectivo(self) -> str:
        """Destino real: con 'carpeta completa' es <destino>\\<nombre de la carpeta de origen>."""
        destino = limpiar_ruta_robocopy(self.destino.texto())
        origen = limpiar_ruta_robocopy(self.origen.texto())
        if not destino or not origen or not self.chk_carpeta.isChecked():
            return destino
        nombre = ntpath.basename(origen.rstrip("\\/"))
        if not nombre or re.fullmatch(r"[A-Za-z]:", nombre):
            return destino  # es una unidad (C:\): no hay carpeta que crear
        return ntpath.join(destino, nombre)

    def _base_args(self, extra_xd: list[str] | None = None) -> list[str]:
        args = [limpiar_ruta_robocopy(self.origen.texto()) or "<origen>",
                self.destino_efectivo() or "<destino>", "/E"]
        carpetas = self.lista_carpetas.activos() + (extra_xd or [])
        if carpetas:
            args += ["/XD", *carpetas]
        archivos = self.lista_archivos.activos()
        if archivos:
            args += ["/XF", *archivos]
        return args

    def _extra_args(self) -> list[str]:
        extra = self.txt_extra.text().strip()
        if not extra:
            return []
        try:
            partes = shlex.split(extra, posix=False)
        except ValueError:
            partes = extra.split()
        return [p.strip('"') for p in partes if p.strip('"')]

    def _con_progreso(self) -> bool:
        return self.chk_total.isChecked() and not self.chk_simular.isChecked()

    def argumentos(self, extra_xd: list[str] | None = None) -> list[str]:
        args = self._base_args(extra_xd)
        args += [f"/R:{self.sp_reintentos.value()}", f"/W:{self.sp_espera.value()}"]
        if self.chk_mt.isChecked():
            args.append(f"/MT:{self.sp_hilos.value()}")
        elif not self.chk_np.isChecked():
            args.append("/ETA")
        if self.chk_np.isChecked():
            args.append("/NP")
        if self.chk_simular.isChecked():
            args.append("/L")
        if self._con_progreso():
            args.append("/BYTES")   # tamaños exactos en cada línea para calcular el avance
        return args + self._extra_args()

    def argumentos_calculo(self, extra_xd: list[str] | None = None) -> list[str]:
        """Pasada rápida sin copiar ni listar archivos: solo el resumen con los totales."""
        args = self._base_args(extra_xd)
        args += ["/L", "/NFL", "/NDL", "/NJH", "/NP", "/BYTES", "/R:0", "/W:0"]
        if self.chk_mt.isChecked():
            args.append(f"/MT:{self.sp_hilos.value()}")
        return args + self._extra_args()

    @staticmethod
    def _comando_texto(args: list[str]) -> str:
        return "robocopy " + " ".join(f'"{a}"' if " " in a else a for a in args)

    def iniciar(self):
        origen = self.origen.texto()
        destino = self.destino_efectivo()
        if not origen or not Path(origen).is_dir():
            self.error("La carpeta de origen no existe.")
            return
        if not destino:
            self.error("Elige la carpeta de destino.")
            return
        if norm(origen) == norm(destino):
            self.error("El origen y el destino son la misma carpeta.")
            return
        extra_xd = []
        if esta_dentro(destino, origen):
            r = QMessageBox.question(
                self, APP_NOMBRE,
                "El destino está DENTRO del origen. Para no copiar la copia sobre sí misma, "
                "se añadirá el destino a las carpetas omitidas.\n\n¿Continuar?")
            if r != QMessageBox.StandardButton.Yes:
                return
            extra_xd.append(destino)
        if not ES_WINDOWS:
            self.error("Robocopy solo está disponible en Windows.")
            return

        self._detectar_discos(refrescar=True)   # por si conectaste otro USB con la misma letra
        self._cancelado = False
        self._totales = None
        self._progreso = None
        self._args_copia = self.argumentos(extra_xd)
        self.set_ocupado(True)
        if self._con_progreso():
            self._fase = "calculo"
            self._salida_calculo = []
            self.consola.agregar("Calculando cuánto hay que copiar…", "suave")
            self.estado("Calculando el tamaño de la copia…")
            self._lanzar_proceso(self.argumentos_calculo(extra_xd))
        else:
            self._arrancar_copia()

    def _lanzar_proceso(self, args: list[str]):
        self._decoder = codecs.getincrementaldecoder(codificacion_consola())(errors="replace")
        self.proceso = QProcess(self)
        self.proceso.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proceso.readyReadStandardOutput.connect(self._leer)
        self.proceso.finished.connect(self._terminado)
        self.proceso.errorOccurred.connect(self._error_proceso)
        self.proceso.start("robocopy", args)

    def _arrancar_copia(self):
        self._fase = "copia"
        simular = self.chk_simular.isChecked()
        if self._con_progreso():
            extras = [a.upper() for a in self._extra_args()]
            self._progreso = ProgresoRobocopy(sin_cabecera="/NJH" in extras)
        self.consola.agregar("▶ " + self._comando_texto(self._args_copia), "titulo")
        self.estado("Simulando…" if simular else "Copiando…")
        self._abrir_registro()
        self._t_inicio = time.monotonic()
        self._muestras.clear()
        if self._progreso is not None:
            self._reloj.start()
        self._lanzar_proceso(self._args_copia)

    def _leer(self):
        if self.proceso is None:
            return
        texto = self._decoder.decode(bytes(self.proceso.readAllStandardOutput()))
        if self._fase == "calculo":
            self._salida_calculo.append(texto)
            return
        if self._progreso is not None:
            self._progreso.alimentar(texto)
        if self._archivo_registro is not None:
            self._archivo_registro.write(texto)
        self.consola.alimentar(texto)

    def _terminado(self, codigo: int, estado_salida):
        resto = self._decoder.decode(b"", final=True)
        if resto:
            if self._fase == "calculo":
                self._salida_calculo.append(resto)
            else:
                self.consola.alimentar(resto)
                if self._archivo_registro is not None:
                    self._archivo_registro.write(resto)
                if self._progreso is not None:
                    self._progreso.alimentar(resto)
        if self.proceso is not None:
            self.proceso.deleteLater()
            self.proceso = None

        if self._cancelado:
            self.consola.cerrar_linea()
            self.consola.agregar("Copia cancelada por el usuario.", "aviso")
            self.estado("Cancelado.")
            self.salio_bien = False
            self._fin()
            return
        if self._fase == "calculo":
            self._calculo_listo(codigo)
            return

        self.consola.cerrar_linea()
        if estado_salida == QProcess.ExitStatus.CrashExit:
            self.consola.agregar("Robocopy se cerró de forma inesperada.", "error")
            self.estado("Terminó con error.")
            self.salio_bien = False
        else:
            tipo, texto = describir_codigo_robocopy(codigo)
            self.consola.agregar(texto, tipo)
            self.estado("Terminado." if tipo != "error" else "Terminó con errores.")
            self.salio_bien = tipo != "error"
            self._resumen_final()
        self._fin()

    def _calculo_listo(self, codigo: int):
        self._totales = leer_resumen_robocopy("".join(self._salida_calculo))
        if codigo >= 16 or self._totales is None:
            self.consola.agregar("No se pudo calcular el total; se copiará sin porcentaje.", "aviso")
            self._totales = None
        else:
            t = self._totales
            texto = f"Hay que copiar {t['archivos']:,} archivos ({formatear_bytes(t['bytes'])})"
            if t["omitidos"]:
                texto += f"; {t['omitidos']:,} ya están iguales en el destino y se saltan"
            self.consola.agregar(texto + ".", "ok")
        self._arrancar_copia()

    def _resumen_final(self):
        if self._progreso is None or self.chk_simular.isChecked():
            return
        self._progreso.terminar()
        duracion = time.monotonic() - self._t_inicio
        b, n = self._progreso.hechos()
        velocidad = f" · promedio {formatear_bytes(b / duracion)}/s" if duracion >= 1 else ""
        self.consola.agregar(f"Tiempo total: {formatear_duracion(duracion)} · {n:,} archivos · "
                             f"{formatear_bytes(b)}{velocidad}", "ok")

    def _actualizar_progreso(self):
        if self._progreso is None or self._fase != "copia":
            return
        ahora = time.monotonic()
        b, n = self._progreso.hechos()
        trabajo = b + n * COSTO_POR_ARCHIVO
        # Velocidad con los últimos ~20 s: reacciona a cambios (archivos grandes/pequeños)
        self._muestras.append((ahora, trabajo, b))
        while len(self._muestras) > 2 and ahora - self._muestras[0][0] > 20:
            self._muestras.popleft()
        t0, w0, b0 = self._muestras[0]
        dt = ahora - t0

        linea1, linea2 = [], []
        tot = self._totales
        if tot and (tot["bytes"] or tot["archivos"]):
            if tot["bytes"]:
                frac = b / tot["bytes"]
            else:
                frac = n / tot["archivos"]
            frac = min(frac, 0.999)
            self.barra.setRange(0, 1000)
            self.barra.setValue(int(frac * 1000))
            linea1 += [f"{frac * 100:.1f}%", f"{formatear_bytes(b)} de {formatear_bytes(tot['bytes'])}",
                       f"{min(n, tot['archivos']):,} de {tot['archivos']:,} archivos"]
            total_trabajo = tot["bytes"] + tot["archivos"] * COSTO_POR_ARCHIVO
            velocidad_trabajo = (trabajo - w0) / dt if dt >= 3 else 0
            if velocidad_trabajo > 0:
                linea2.append(f"quedan ~{formatear_duracion(max(total_trabajo - trabajo, 0) / velocidad_trabajo)}")
            else:
                linea2.append("calculando tiempo restante…")
        else:
            linea1 += [formatear_bytes(b), f"{n:,} archivos"]
        if dt >= 1:
            linea2.append(f"{formatear_bytes((b - b0) / dt)}/s")
        linea2.append(f"transcurrido {formatear_duracion(ahora - self._t_inicio)}")
        self.estado(" · ".join(linea1) + "\n" + " · ".join(linea2))

    def _error_proceso(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.consola.agregar("No se pudo iniciar robocopy. ¿Estás en Windows?", "error")
            self.estado("Error.")
            self.salio_bien = False
            if self.proceso is not None:
                self.proceso.deleteLater()
                self.proceso = None
            self._fin()

    def _abrir_registro(self):
        self._archivo_registro = self._ruta_registro = None
        if not self.chk_registro.isChecked():
            return
        ruta = CARPETA_REGISTROS / time.strftime("robocopy_%Y-%m-%d_%H-%M-%S.txt")
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            self._archivo_registro = open(ruta, "w", encoding="utf-8", newline="")
            self._archivo_registro.write(self._comando_texto(self._args_copia) + "\r\n\r\n")
            self._ruta_registro = ruta
        except OSError as e:
            self.consola.agregar(f"No se pudo crear el registro en «{ruta}»: {e}", "aviso")

    def _cerrar_registro(self):
        if self._archivo_registro is None:
            return
        try:
            self._archivo_registro.close()
            self.consola.agregar(f"Registro completo guardado en «{self._ruta_registro}».", "ok")
        except OSError as e:
            self.consola.agregar(f"No se pudo guardar el registro: {e}", "aviso")
        self._archivo_registro = None

    def _fin(self):
        self._reloj.stop()
        self._cerrar_registro()
        self._fase = None
        self.set_ocupado(False)

    def ocupada(self) -> bool:
        return self.proceso is not None or self._fase is not None

    def cancelar(self):
        if self.proceso is not None:
            self._cancelado = True
            self.estado("Cancelando…")
            self.proceso.kill()

    def esperar(self, ms: int = 3000):
        if self.proceso is not None:
            self.proceso.waitForFinished(ms)


# ═════════════════════════════════════════════════════════════════════════════
# 2. ORGANIZAR POR EXTENSIÓN
# ═════════════════════════════════════════════════════════════════════════════

SIN_EXT = "(sin extensión)"


def tarea_escanear(t: Tarea, origen: str, destino: str) -> dict:
    """Recorre origen y TODAS sus subcarpetas agrupando archivos por extensión."""
    por_ext: dict[str, list[str]] = defaultdict(list)
    destino_n = norm(destino)
    n = 0
    t.log(f"Escaneando «{origen}» y subcarpetas…", "titulo")

    def sin_acceso(err):
        t.log(f"Sin acceso: {err.filename}", "aviso")

    for raiz, dirs, archivos in os.walk(origen, onerror=sin_acceso):
        t.revisar()
        # No volver a contar lo que ya se organizó en una corrida anterior
        dirs[:] = sorted(d for d in dirs if norm(os.path.join(raiz, d)) != destino_n)
        for a in archivos:
            por_ext[os.path.splitext(a)[1].lower()].append(os.path.join(raiz, a))
            n += 1
        t.progreso(n, 0, f"{n:,} archivos encontrados…")
    t.log(f"Total: {n:,} archivos | {len(por_ext)} extensiones distintas.", "ok")
    return dict(por_ext)


def tarea_organizar(t: Tarea, por_ext: dict, exts: list[str], destino: str,
                    mover: bool, subcarpetas: bool):
    lista = [(ext, ruta) for ext in exts for ruta in por_ext.get(ext, [])]
    total = len(lista)
    base = Path(destino)
    base.mkdir(parents=True, exist_ok=True)
    verbo = "Moviendo" if mover else "Copiando"
    t.log(f"{verbo} {total:,} archivos a «{base}»…", "titulo")
    ok = errores = 0
    for i, (ext, ruta) in enumerate(lista, 1):
        t.revisar()
        origen = Path(ruta)
        try:
            if not origen.exists():
                raise FileNotFoundError("ya no existe")
            carpeta = base / (ext.lstrip(".") or "sin_extension") if subcarpetas else base
            carpeta.mkdir(parents=True, exist_ok=True)
            destino_archivo = ruta_libre(carpeta / origen.name)
            if mover:
                shutil.move(str(origen), str(destino_archivo))
            else:
                shutil.copy2(str(origen), str(destino_archivo))
            ok += 1
            t.log(f"{origen}  →  {destino_archivo}")
        except Exception as e:
            errores += 1
            t.log(f"✗ {origen}: {e}", "error")
        t.progreso(i, total, f"{verbo}… {i:,} / {total:,}")
    t.log(f"✓ {'Movidos' if mover else 'Copiados'}: {ok:,} archivos"
          + (f" | con errores: {errores:,}" if errores else ""), "ok" if not errores else "aviso")
    return {"ok": ok, "errores": errores, "destino": str(base), "mover": mover}


class PaginaOrganizar(Pagina):
    def __init__(self, ventana):
        super().__init__(ventana, "Organizar por extensión",
                         "Escanea una carpeta y todas sus subcarpetas, cuenta los archivos por "
                         "extensión y mueve o copia los tipos que elijas a una carpeta por extensión.")
        self._por_ext: dict | None = None
        self._origen_escaneado = ""
        self._destino_usado: str | None = None

        card, lay = tarjeta("1 · Carpeta a escanear")
        self.origen = SelectorRuta("carpeta", "Carpeta a escanear (incluye subcarpetas)")
        self.origen.cambiado.connect(self._origen_cambiado)
        lay.addWidget(self.origen)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("2 · Extensiones",
                            "Marca las extensiones que quieres mover o copiar.")
        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["EXTENSIÓN", "ARCHIVOS"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.verticalHeader().setDefaultSectionSize(32)
        self.tabla.setMinimumHeight(240)
        self.tabla.itemChanged.connect(lambda *_: self._actualizar_resumen())
        lay.addWidget(self.tabla)
        fila = QHBoxLayout()
        self.btn_todas = boton("Marcar todas", "fantasma")
        self.btn_ninguna = boton("Desmarcar todas", "fantasma")
        self.btn_exportar = boton("Exportar lista .txt", "fantasma",
                                  "Guarda la lista de extensiones encontradas (una por línea)")
        self.btn_todas.clicked.connect(lambda: self._marcar_todas(True))
        self.btn_ninguna.clicked.connect(lambda: self._marcar_todas(False))
        self.btn_exportar.clicked.connect(self._exportar)
        fila.addWidget(self.btn_todas)
        fila.addWidget(self.btn_ninguna)
        fila.addStretch(1)
        fila.addWidget(self.btn_exportar)
        lay.addLayout(fila)
        self.lbl_resumen = etiqueta("Escanea una carpeta para ver sus extensiones.", "suave")
        lay.addWidget(self.lbl_resumen)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("3 · Destino")
        self.destino = SelectorRuta("carpeta", "Predeterminado: <carpeta escaneada>\\Organizado")
        lay.addWidget(self.destino)
        fila = QHBoxLayout()
        self.rb_mover = QRadioButton("Mover")
        self.rb_copiar = QRadioButton("Copiar")
        self.rb_mover.setChecked(True)
        grupo = QButtonGroup(self)
        grupo.addButton(self.rb_mover)
        grupo.addButton(self.rb_copiar)
        fila.addWidget(self.rb_mover)
        fila.addWidget(self.rb_copiar)
        fila.addStretch(1)
        lay.addLayout(fila)
        self.chk_sub = QCheckBox("Crear una subcarpeta por extensión (ej. Organizado\\pdf\\)")
        self.chk_sub.setChecked(True)
        lay.addWidget(self.chk_sub)
        lay.addWidget(etiqueta("Si ya existe un archivo con el mismo nombre se añade _1, _2… "
                               "(nunca se sobrescribe).", "suave"))
        self.cuerpo.addWidget(card)
        self.cuerpo.addStretch(1)

        self.btn_escanear = boton("Escanear")
        self.btn_escanear.clicked.connect(self.escanear)
        self.btn_organizar = boton("Organizar", "primario")
        self.btn_organizar.clicked.connect(self.organizar)
        self.agregar_accion(self.btn_escanear)
        self.agregar_accion(self.btn_organizar)

        ultima = self.config.seccion("organizar").get("origen", "")
        if ultima:
            self.origen.establecer(ultima)
        self.actualizar_acciones()

    def _destino_efectivo(self) -> str:
        return self.destino.texto() or str(Path(self.origen.texto() or ".") / "Organizado")

    def _origen_cambiado(self, *_):
        if self._por_ext is not None and self.origen.texto() != self._origen_escaneado:
            self._por_ext = None
            self.tabla.setRowCount(0)
            self.lbl_resumen.setText("La carpeta cambió: vuelve a escanear.")
        self.actualizar_acciones()

    def _marcadas(self) -> list[str]:
        return [self.tabla.item(r, 0).data(Qt.ItemDataRole.UserRole)
                for r in range(self.tabla.rowCount())
                if self.tabla.item(r, 0).checkState() == Qt.CheckState.Checked]

    def _marcar_todas(self, valor: bool):
        self.tabla.blockSignals(True)
        for r in range(self.tabla.rowCount()):
            self.tabla.item(r, 0).setCheckState(Qt.CheckState.Checked if valor else Qt.CheckState.Unchecked)
        self.tabla.blockSignals(False)
        self._actualizar_resumen()

    def _actualizar_resumen(self):
        if self._por_ext is None:
            self.actualizar_acciones()
            return
        marcadas = self._marcadas()
        n = sum(len(self._por_ext.get(e, [])) for e in marcadas)
        self.lbl_resumen.setText(f"{len(marcadas)} de {len(self._por_ext)} extensiones marcadas · "
                                 f"{n:,} archivos")
        self.actualizar_acciones()

    def actualizar_acciones(self):
        hay = self._por_ext is not None and self.tabla.rowCount() > 0
        if self.ocupada():
            return
        self.btn_organizar.setEnabled(hay and bool(self._marcadas()))
        for b in (self.btn_todas, self.btn_ninguna, self.btn_exportar):
            b.setEnabled(hay)

    def escanear(self):
        origen = self.origen.texto()
        if not origen or not Path(origen).is_dir():
            self.error("La carpeta a escanear no existe.")
            return
        self.config.seccion("organizar")["origen"] = origen
        self.config.guardar()
        self._origen_escaneado = origen
        self._destino_usado = self._destino_efectivo()
        self.lanzar(tarea_escanear, (origen, self._destino_usado), self._escaneo_listo, "Escaneando…")

    def _escaneo_listo(self, por_ext: dict):
        self._por_ext = por_ext
        self.tabla.blockSignals(True)
        self.tabla.setSortingEnabled(False)
        self.tabla.setRowCount(0)
        for ext, rutas in sorted(por_ext.items(), key=lambda x: (-len(x[1]), x[0])):
            r = self.tabla.rowCount()
            self.tabla.insertRow(r)
            it = QTableWidgetItem(ext or SIN_EXT)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, ext)
            cant = QTableWidgetItem()
            cant.setData(Qt.ItemDataRole.DisplayRole, len(rutas))
            cant.setFlags(Qt.ItemFlag.ItemIsEnabled)
            cant.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabla.setItem(r, 0, it)
            self.tabla.setItem(r, 1, cant)
        self.tabla.setSortingEnabled(True)
        self.tabla.blockSignals(False)
        self.estado(f"Escaneo listo: {sum(len(v) for v in por_ext.values()):,} archivos.")
        self._actualizar_resumen()

    def _exportar(self):
        if not self._por_ext:
            return
        inicio = str(Path(self._origen_escaneado) / "extensiones.txt")
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar extensiones", inicio, "Texto (*.txt)")
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write("\n".join(sorted(e or SIN_EXT for e in self._por_ext)))
            self.consola.agregar(f"Lista de extensiones guardada en «{ruta}».", "ok")
        except OSError as e:
            self.error(f"No se pudo guardar: {e}")

    def organizar(self):
        exts = self._marcadas()
        if not self._por_ext or not exts:
            return
        destino = self._destino_efectivo()
        if self._destino_usado and norm(destino) != norm(self._destino_usado) \
                and esta_dentro(destino, self._origen_escaneado):
            self.error("Cambiaste el destino a una carpeta dentro de la escaneada. "
                       "Vuelve a escanear para no incluirla.")
            return
        mover = self.rb_mover.isChecked()
        n = sum(len(self._por_ext[e]) for e in exts)
        verbo = "MOVER" if mover else "COPIAR"
        r = QMessageBox.question(
            self, APP_NOMBRE,
            f"Se van a {verbo} {n:,} archivos ({len(exts)} extensiones) a:\n{destino}\n\n¿Continuar?")
        if r != QMessageBox.StandardButton.Yes:
            return
        self.lanzar(tarea_organizar, (self._por_ext, exts, destino, mover, self.chk_sub.isChecked()),
                    self._organizado, "Organizando…")

    def _organizado(self, res: dict):
        self.estado(f"Listo: {res['ok']:,} archivos" + (f", {res['errores']:,} con error." if res["errores"] else "."))
        if res["mover"]:
            # Los archivos ya no están donde estaban: el escaneo quedó viejo
            self._por_ext = None
            self.tabla.setRowCount(0)
            self.lbl_resumen.setText("Archivos movidos. Vuelve a escanear si quieres seguir.")


# ═════════════════════════════════════════════════════════════════════════════
# 3. LISTAR RUTAS
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_RUTAS = {
    "carpeta": "",
    "incluir": "ambos",               # archivos | carpetas | ambos
    "modo_filtro": "todo",            # todo | solo | excluir
    "extensiones": [[".bat", True], [".lnk", True], [".exe", True], [".msi", True], [".pdf", True]],
    "ignorar": [],
    "carpeta_salida": "",
    "nombre_salida": "lista_archivos.txt",
    "relativas": False,
}


def tarea_rutas(t: Tarea, cfg: dict) -> dict:
    base = Path(cfg["carpeta"]).absolute()
    salida = Path(cfg["salida"])
    incluir_archivos = cfg["incluir"] in ("archivos", "ambos")
    incluir_carpetas = cfg["incluir"] in ("carpetas", "ambos")
    modo = cfg["modo_filtro"]
    exts = tuple(e.lower() for e in cfg["extensiones"])
    ignorar = [p.lower() for p in cfg["ignorar"]]
    relativas = cfg["relativas"]

    salida.parent.mkdir(parents=True, exist_ok=True)
    tmp = salida.with_name(salida.name + ".tmp")
    propios = {norm(salida), norm(tmp)}
    n_carpetas = n_archivos = vistos = 0

    def pasa(nombre: str) -> bool:
        if modo == "todo":
            return True
        coincide = nombre.lower().endswith(exts)
        return coincide if modo == "solo" else not coincide

    def texto(ruta: str) -> str:
        return os.path.relpath(ruta, base) if relativas else ruta

    def sin_acceso(err):
        t.log(f"Sin acceso: {err.filename}", "aviso")

    t.log(f"Recorriendo «{base}»…", "titulo")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for raiz, dirs, archivos in os.walk(base, onerror=sin_acceso):
                t.revisar()
                dirs[:] = sorted(d for d in dirs
                                 if not any(fnmatch.fnmatch(d.lower(), p) for p in ignorar))
                # Cada carpeta aparece justo antes de su contenido
                if incluir_carpetas and norm(raiz) != norm(base):
                    f.write(texto(raiz) + "\n")
                    n_carpetas += 1
                if incluir_archivos:
                    for a in sorted(archivos):
                        vistos += 1
                        ruta = os.path.join(raiz, a)
                        if pasa(a) and norm(ruta) not in propios:
                            f.write(texto(ruta) + "\n")
                            n_archivos += 1
                t.progreso(n_carpetas + n_archivos, 0, f"{n_carpetas + n_archivos:,} rutas…")
        os.replace(tmp, salida)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise

    if incluir_carpetas:
        t.log(f"Carpetas guardadas: {n_carpetas:,}")
    if incluir_archivos:
        t.log(f"Archivos guardados: {n_archivos:,} (de {vistos:,} encontrados)")
    t.log(f"✓ Lista generada en «{salida}».", "ok")
    return {"salida": str(salida), "total": n_carpetas + n_archivos}


class PaginaRutas(Pagina):
    def __init__(self, ventana):
        super().__init__(ventana, "Listar rutas",
                         "Recorre una carpeta y todas sus subcarpetas y guarda las rutas en un .txt. "
                         "Por defecto incluye todo.")
        self._ultima_salida: str | None = None

        self.sesiones = BarraSesiones(self.config, "rutas", DEFAULT_RUTAS, self.obtener_estado)
        self.sesiones.sesion_cargada.connect(self.aplicar_estado)
        self.cuerpo.addWidget(self.sesiones)

        card, lay = tarjeta("Carpeta a analizar")
        self.carpeta = SelectorRuta("carpeta", "Carpeta raíz")
        lay.addWidget(self.carpeta)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("Qué incluir")
        fila = QHBoxLayout()
        self.rb_archivos = QRadioButton("Solo archivos")
        self.rb_carpetas = QRadioButton("Solo carpetas")
        self.rb_ambos = QRadioButton("Archivos y carpetas")
        self.grupo_incluir = QButtonGroup(self)
        for rb in (self.rb_ambos, self.rb_archivos, self.rb_carpetas):
            self.grupo_incluir.addButton(rb)
            fila.addWidget(rb)
        fila.addStretch(1)
        lay.addLayout(fila)
        self.chk_relativas = QCheckBox("Rutas relativas a la carpeta analizada (en vez de completas)")
        lay.addWidget(self.chk_relativas)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("Filtro de archivos", "Solo afecta a los archivos; las carpetas no se filtran.")
        fila = QHBoxLayout()
        self.rb_todo = QRadioButton("Todo")
        self.rb_solo = QRadioButton("Solo estas extensiones")
        self.rb_excluir = QRadioButton("Excluir estas extensiones")
        self.grupo_filtro = QButtonGroup(self)
        for rb in (self.rb_todo, self.rb_solo, self.rb_excluir):
            self.grupo_filtro.addButton(rb)
            fila.addWidget(rb)
        fila.addStretch(1)
        lay.addLayout(fila)
        self.lista_ext = ListaEditable("EXTENSIONES", "", "Agregar extensiones, ej. mp4, jpg, png",
                                       normalizar=normalizar_extension)
        lay.addWidget(self.lista_ext)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta()
        self.lista_ignorar = ListaEditable(
            "CARPETAS A IGNORAR", "No se recorren ni aparecen en la lista. Admite comodines (.git, node_modules, .venv*).",
            "Agregar carpeta o patrón")
        lay.addWidget(self.lista_ignorar)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("Archivo de salida")
        lay.addWidget(etiqueta("CARPETA"))
        self.carpeta_salida = SelectorRuta("carpeta", "Predeterminado: la carpeta analizada")
        lay.addWidget(self.carpeta_salida)
        lay.addWidget(etiqueta("NOMBRE"))
        self.nombre_salida = QLineEdit()
        lay.addWidget(self.nombre_salida)
        self.cuerpo.addWidget(card)
        self.cuerpo.addStretch(1)

        self.btn_generar = boton("Generar lista", "primario")
        self.btn_generar.clicked.connect(self.generar)
        self.btn_abrir = boton("Abrir .txt", "fantasma")
        self.btn_abrir.clicked.connect(lambda: self._ultima_salida and abrir_en_sistema(self._ultima_salida))
        self.btn_abrir_carpeta = boton("Abrir carpeta", "fantasma")
        self.btn_abrir_carpeta.clicked.connect(
            lambda: self._ultima_salida and abrir_en_sistema(Path(self._ultima_salida).parent))
        self.agregar_accion(self.btn_generar)
        self.agregar_accion(self.btn_abrir)
        self.agregar_accion(self.btn_abrir_carpeta)

        for sig in (self.carpeta.cambiado, self.grupo_incluir.buttonToggled, self.chk_relativas.toggled,
                    self.grupo_filtro.buttonToggled, self.lista_ext.cambiado, self.lista_ignorar.cambiado,
                    self.carpeta_salida.cambiado, self.nombre_salida.textChanged):
            sig.connect(self._cambio)

        self.sesiones.cargar_inicial()
        self.actualizar_acciones()

    def _cambio(self, *_):
        self.sesiones.marcar_modificado()
        self.lista_ext.setEnabled(not self.rb_todo.isChecked())

    def actualizar_acciones(self):
        if not self.ocupada():
            hay = bool(self._ultima_salida)
            self.btn_abrir.setEnabled(hay)
            self.btn_abrir_carpeta.setEnabled(hay)

    def _incluir(self) -> str:
        return "archivos" if self.rb_archivos.isChecked() else "carpetas" if self.rb_carpetas.isChecked() else "ambos"

    def _modo(self) -> str:
        return "solo" if self.rb_solo.isChecked() else "excluir" if self.rb_excluir.isChecked() else "todo"

    def obtener_estado(self) -> dict:
        return {
            "carpeta": self.carpeta.texto(),
            "incluir": self._incluir(),
            "modo_filtro": self._modo(),
            "extensiones": self.lista_ext.valores(),
            "ignorar": self.lista_ignorar.valores(),
            "carpeta_salida": self.carpeta_salida.texto(),
            "nombre_salida": self.nombre_salida.text().strip(),
            "relativas": self.chk_relativas.isChecked(),
        }

    def aplicar_estado(self, e: dict):
        if e.get("carpeta"):
            self.carpeta.establecer(e["carpeta"])
        {"archivos": self.rb_archivos, "carpetas": self.rb_carpetas}.get(e.get("incluir"), self.rb_ambos).setChecked(True)
        {"solo": self.rb_solo, "excluir": self.rb_excluir}.get(e.get("modo_filtro"), self.rb_todo).setChecked(True)
        self.lista_ext.establecer(e.get("extensiones"))
        self.lista_ignorar.establecer(e.get("ignorar"))
        if e.get("carpeta_salida"):
            self.carpeta_salida.establecer(e["carpeta_salida"])
        self.nombre_salida.setText(e.get("nombre_salida") or "lista_archivos.txt")
        self.chk_relativas.setChecked(bool(e.get("relativas")))
        self._cambio()

    def generar(self):
        carpeta = self.carpeta.texto()
        if not carpeta or not Path(carpeta).is_dir():
            self.error("La carpeta a analizar no existe.")
            return
        extensiones = self.lista_ext.activos()
        if self._modo() != "todo" and not extensiones:
            self.error("El filtro necesita al menos una extensión marcada (o elige «Todo»).")
            return
        nombre = self.nombre_salida.text().strip() or "lista_archivos.txt"
        if not nombre.lower().endswith(".txt"):
            nombre += ".txt"
        salida = Path(self.carpeta_salida.texto() or carpeta) / nombre
        cfg = {
            "carpeta": carpeta,
            "salida": str(salida),
            "incluir": self._incluir(),
            "modo_filtro": self._modo(),
            "extensiones": extensiones,
            "ignorar": self.lista_ignorar.activos(),
            "relativas": self.chk_relativas.isChecked(),
        }
        self.lanzar(tarea_rutas, (cfg,), self._listo, "Generando lista…")

    def _listo(self, res: dict):
        self._ultima_salida = res["salida"]
        self.estado(f"Listo: {res['total']:,} rutas guardadas.")


# ═════════════════════════════════════════════════════════════════════════════
# 4. INFO DEL ENTORNO
# ═════════════════════════════════════════════════════════════════════════════

def tarea_info(t: Tarea, usa_global: bool, venv: str) -> dict:
    exe, carpeta = resolver_python(t, usa_global, venv)
    t.log(f"Python: {exe}", "titulo")
    datos = leer_entorno(t, exe, "info")
    t.log(f"Versión: {datos['version'].split()[0]} | {len(datos['paquetes'])} paquetes")

    t.log("Ejecutando pip freeze…", "suave")
    freeze, fuente = "", "pip freeze"
    try:
        r = ejecutar_cancelable(t, [str(exe), "-m", "pip", "freeze"], timeout=300)
        if r.returncode == 0:
            freeze = r.stdout
        else:
            ultima = (r.stderr.strip().splitlines() or ["pip no disponible"])[-1]
            t.log(f"pip freeze falló ({ultima}). Se usará la lista de paquetes.", "aviso")
    except (OSError, TimeoutError) as e:
        t.log(f"No se pudo ejecutar pip freeze ({e}). Se usará la lista de paquetes.", "aviso")
    if not freeze.strip():
        fuente = "lista de paquetes instalados"
        freeze = "".join(f"{p['nombre']}=={p['version']}\n" for p in datos["paquetes"])

    datos.update({"exe": str(exe), "carpeta_venv": str(carpeta) if carpeta else None,
                  "freeze": freeze, "fuente": fuente})
    return datos


class PaginaEntorno(Pagina):
    def __init__(self, ventana):
        super().__init__(ventana, "Info del entorno",
                         "Muestra la versión de Python y de cada librería instalada en un venv "
                         "(o en el Python global) y lo guarda como requirements.txt.")
        self._datos: dict | None = None

        card, lay = tarjeta("Python a analizar")
        self.selector = SelectorPython()
        lay.addWidget(self.selector)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("Guardar")
        self.chk_guardar = QCheckBox("Guardar el archivo automáticamente al analizar")
        self.chk_guardar.setChecked(True)
        lay.addWidget(self.chk_guardar)
        lay.addWidget(etiqueta("CARPETA"))
        self.carpeta_salida = SelectorRuta(
            "carpeta", "Predeterminado: la carpeta del venv (o la de esta app si es el global)")
        lay.addWidget(self.carpeta_salida)
        lay.addWidget(etiqueta("NOMBRE"))
        self.nombre_salida = QLineEdit("requirements.txt")
        lay.addWidget(self.nombre_salida)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("Resultado")
        g = grid_opciones()
        self.lbl_version = QLabel("—")
        self.lbl_exe = QLabel("—")
        self.lbl_tipo = QLabel("—")
        self.lbl_total = QLabel("—")
        for i, (nombre, lbl) in enumerate([("PYTHON", self.lbl_version), ("EJECUTABLE", self.lbl_exe),
                                            ("TIPO", self.lbl_tipo), ("PAQUETES", self.lbl_total)]):
            lbl.setProperty("class", "dato")
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            g.addWidget(etiqueta(nombre), i, 0)
            g.addWidget(lbl, i, 1)
        lay.addLayout(g)
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Filtrar paquetes…")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.textChanged.connect(self._filtrar)
        lay.addWidget(self.buscar)
        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["PAQUETE", "VERSIÓN"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.verticalHeader().setDefaultSectionSize(28)
        self.tabla.setMinimumHeight(280)
        lay.addWidget(self.tabla)
        self.cuerpo.addWidget(card)
        self.cuerpo.addStretch(1)

        self.btn_analizar = boton("Analizar", "primario")
        self.btn_analizar.clicked.connect(self.analizar)
        self.btn_guardar = boton("Guardar ahora")
        self.btn_guardar.clicked.connect(lambda: self.guardar(preguntar=True))
        self.agregar_accion(self.btn_analizar)
        self.agregar_accion(self.btn_guardar)

        sec = self.config.seccion("entorno")
        self.selector.establecer(sec.get("python", {}))
        self.actualizar_acciones()

    def actualizar_acciones(self):
        if not self.ocupada():
            self.btn_guardar.setEnabled(self._datos is not None)

    def analizar(self):
        if not self.selector.usa_global():
            try:
                buscar_python_venv(self.selector.venv())
            except ValueError as e:
                self.error(str(e))
                return
        self.config.seccion("entorno")["python"] = self.selector.estado()
        self.config.guardar()
        self.lanzar(tarea_info, (self.selector.usa_global(), self.selector.venv()),
                    self._listo, "Analizando entorno…")

    def _listo(self, d: dict):
        self._datos = d
        es_venv = d["prefix"] != d["base_prefix"]
        self.lbl_version.setText(d["version"].split()[0])
        self.lbl_exe.setText(d["exe"])
        self.lbl_tipo.setText("Entorno virtual" if es_venv else "Instalación global")
        self.lbl_total.setText(f"{len(d['paquetes'])}")
        self.tabla.setSortingEnabled(False)
        self.tabla.setRowCount(len(d["paquetes"]))
        for i, p in enumerate(d["paquetes"]):
            self.tabla.setItem(i, 0, QTableWidgetItem(p["nombre"]))
            self.tabla.setItem(i, 1, QTableWidgetItem(p["version"]))
        self.tabla.setSortingEnabled(True)
        self._filtrar(self.buscar.text())
        self.estado(f"{len(d['paquetes'])} paquetes encontrados.")
        if self.chk_guardar.isChecked():
            self.guardar(preguntar=False)

    def _filtrar(self, texto: str):
        texto = texto.strip().lower()
        for r in range(self.tabla.rowCount()):
            it = self.tabla.item(r, 0)
            self.tabla.setRowHidden(r, bool(texto) and (it is None or texto not in it.text().lower()))

    def _ruta_salida(self) -> Path:
        d = self._datos or {}
        carpeta = self.carpeta_salida.texto() or d.get("carpeta_venv") or str(carpeta_app())
        nombre = self.nombre_salida.text().strip() or "requirements.txt"
        return Path(carpeta) / nombre

    def guardar(self, preguntar: bool):
        if not self._datos:
            return
        ruta = self._ruta_salida()
        if preguntar and ruta.exists():
            r = QMessageBox.question(self, APP_NOMBRE, f"«{ruta}» ya existe. ¿Sobrescribirlo?")
            if r != QMessageBox.StandardButton.Yes:
                return
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(self._datos["freeze"])
            self.consola.agregar(f"✓ {ruta.name} guardado ({self._datos['fuente']}) en «{ruta.parent}».", "ok")
        except OSError as e:
            self.consola.agregar(f"No se pudo guardar «{ruta}»: {e}", "error")


# ═════════════════════════════════════════════════════════════════════════════
# 5. LICENCIAS
# ═════════════════════════════════════════════════════════════════════════════

ANCHO_DOC = 60
SEPARADOR_DOC = "-" * ANCHO_DOC
ENCABEZADO_LICENCIAS = (
    "Este documento contiene los textos completos y sin modificar de las licencias\n"
    "de todas las librerías externas que usa {app}.\n"
    "Las licencias se reproducen tal cual para cumplir con los requisitos legales\n"
    "de redistribución.\n\n"
    "Este archivo se entrega únicamente con fines informativos y de cumplimiento legal.\n"
)

DEFAULT_LICENCIAS = {
    "python": {"global": False, "venv": ""},
    "app": "esta aplicación",
    "carpeta_salida": "",
    "nombre_salida": "THIRD_PARTY_NOTICES.txt",
    "excluir": "",
    "solo_requeridos": False,
    "requirements": "",
    "extra": "",
}


def leer_texto(ruta) -> str:
    for cod in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(ruta, "r", encoding=cod) as fh:
                return fh.read().strip()
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    return ""


def titulo_doc(texto: str) -> str:
    return "=" * ANCHO_DOC + "\n" + texto.center(ANCHO_DOC) + "\n" + "=" * ANCHO_DOC


def componentes_extra(t: Tarea, config: dict, base: str) -> list:
    """Componentes que no son paquetes de Python (FFmpeg, Ghostscript, modelos...)."""
    salida = []
    for comp in config.get("componentes") or []:
        nombre = comp.get("nombre")
        if not nombre:
            continue
        texto = comp.get("texto") or ""
        if not texto and comp.get("archivo"):
            ruta = comp["archivo"]
            if not os.path.isabs(ruta):
                ruta = os.path.join(base, ruta)
            texto = leer_texto(ruta)
            if not texto:
                t.log(f"No se pudo leer la licencia de {nombre}: {ruta}", "aviso")
        encabezado = []
        if comp.get("url"):
            encabezado.append(f"Proyecto: {comp['url']}")
        if comp.get("nota"):
            encabezado.append(comp["nota"])
        cuerpo = "\n".join(encabezado + ([""] if encabezado else []) + [texto or "(sin texto)"])
        salida.append((nombre, comp.get("version", "?"),
                       comp.get("tipo", "Ver texto de la licencia"), cuerpo.strip()))
    return salida


def completar_faltantes(paquetes: list, config: dict, base: str) -> list:
    """Rellena los paquetes sin licencia con la sección 'faltantes' del JSON."""
    faltantes = {k.lower(): v for k, v in (config.get("faltantes") or {}).items()}
    if not faltantes:
        return paquetes
    salida = []
    for nombre, version, tipo, texto in paquetes:
        datos = faltantes.get(nombre.lower())
        if datos and texto.startswith(("El paquete no declara", "Licencia declarada:")):
            nuevo = datos.get("texto") or ""
            if not nuevo and datos.get("archivo"):
                ruta = datos["archivo"]
                if not os.path.isabs(ruta):
                    ruta = os.path.join(base, ruta)
                nuevo = leer_texto(ruta)
            if nuevo:
                texto = nuevo
                tipo = datos.get("tipo", tipo)
        salida.append((nombre, version, tipo, texto))
    return salida


def nombres_de_requirements(ruta) -> set:
    nombres = set()
    for linea in (leer_texto(ruta) or "").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea or linea.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9._-]+)", linea)
        if m:
            nombres.add(m.group(1).lower().replace("_", "-"))
    return nombres


def tarea_licencias(t: Tarea, cfg: dict, solo_listar: bool) -> dict:
    exe, carpeta_venv = resolver_python(t, cfg["global"], cfg["venv"])
    t.log(f"Python: {exe}", "titulo")

    config, base = {}, os.getcwd()
    if cfg["extra"]:
        base = os.path.dirname(os.path.abspath(cfg["extra"]))
        try:
            with open(cfg["extra"], "r", encoding="utf-8") as fh:
                config = json.load(fh)
        except Exception as e:
            raise RuntimeError(f"No se pudo leer el JSON extra «{cfg['extra']}»: {e}")

    t.log("Leyendo paquetes y licencias…", "suave")
    datos = leer_entorno(t, exe, "licencias")
    for aviso in datos.get("avisos", []):
        t.log(aviso, "aviso")

    excluir = {x.strip().lower() for x in cfg["excluir"].split(",") if x.strip()}
    paquetes = [(p["nombre"], p["version"], p["tipo"], p["texto"])
                for p in datos["paquetes"] if p["nombre"].lower() not in excluir]

    if cfg["solo_requeridos"]:
        req = cfg["requirements"] or (str(Path(carpeta_venv) / "requirements.txt") if carpeta_venv else "")
        if not req or not Path(req).is_file():
            raise RuntimeError(f"No encontré el requirements.txt: «{req or '(vacío)'}»")
        pedidos = nombres_de_requirements(req)
        if pedidos:
            paquetes = [x for x in paquetes if x[0].lower().replace("_", "-") in pedidos]
        t.log(f"Filtrado con «{req}»: {len(paquetes)} paquetes.")

    paquetes = completar_faltantes(paquetes, config, base)
    filas = sorted(paquetes + componentes_extra(t, config, base), key=lambda x: x[0].lower())
    if not filas:
        raise RuntimeError("No se encontró ningún paquete.")

    if solo_listar:
        for nombre, version, tipo, _ in filas:
            t.log(f"{nombre}=={version}   [{tipo}]")
        t.log(f"Total: {len(filas)} componentes.", "ok")
        return {"salida": None, "total": len(filas)}

    partes = [titulo_doc("LICENSE INFORMATION DOCUMENT"), ""]
    partes.append((config.get("encabezado") or ENCABEZADO_LICENCIAS.format(app=cfg["app"])).strip())
    partes += ["", "", titulo_doc("SUMMARY OF INCLUDED PACKAGES"), ""]
    partes += [f"{nombre}=={version}" for nombre, version, _, _ in filas]
    partes += ["", "", titulo_doc("DETAILED LICENSE TEXTS"), ""]
    for nombre, version, tipo, texto in filas:
        partes += [f"--- {nombre} ({version}) ---", f"License Type: {tipo}", "", texto, "",
                   SEPARADOR_DOC, ""]
    contenido = "\n".join(partes).rstrip() + "\n"

    carpeta = cfg["carpeta_salida"] or (str(carpeta_venv) if carpeta_venv else str(carpeta_app()))
    salida = Path(carpeta) / (cfg["nombre_salida"] or "THIRD_PARTY_NOTICES.txt")
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(contenido)

    sin_texto = [n for n, _, _, tx in filas if tx.startswith("El paquete no declara")]
    t.log(f"✓ {salida}: {len(filas)} componentes, {len(contenido) / 1024:.0f} KB.", "ok")
    if sin_texto:
        t.log(f"Sin texto de licencia ({len(sin_texto)}): {', '.join(sin_texto)}", "aviso")
    return {"salida": str(salida), "total": len(filas)}


class PaginaLicencias(Pagina):
    def __init__(self, ventana):
        super().__init__(ventana, "Licencias de terceros",
                         "Genera un THIRD_PARTY_NOTICES.txt con la licencia completa de cada librería "
                         "instalada en un venv (o en el Python global).")
        self._ultima_salida: str | None = None

        self.sesiones = BarraSesiones(self.config, "licencias", DEFAULT_LICENCIAS, self.obtener_estado)
        self.sesiones.sesion_cargada.connect(self.aplicar_estado)
        self.cuerpo.addWidget(self.sesiones)

        card, lay = tarjeta("Python a analizar")
        self.selector = SelectorPython()
        lay.addWidget(self.selector)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("Documento")
        lay.addWidget(etiqueta("NOMBRE DE LA APLICACIÓN (para el encabezado)"))
        self.txt_app = QLineEdit()
        lay.addWidget(self.txt_app)
        lay.addWidget(etiqueta("CARPETA DE SALIDA"))
        self.carpeta_salida = SelectorRuta(
            "carpeta", "Predeterminado: la carpeta del venv (o la de esta app si es el global)")
        lay.addWidget(self.carpeta_salida)
        lay.addWidget(etiqueta("NOMBRE DEL ARCHIVO"))
        self.nombre_salida = QLineEdit()
        lay.addWidget(self.nombre_salida)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("Filtros")
        lay.addWidget(etiqueta("PAQUETES A EXCLUIR (separados por coma)"))
        self.txt_excluir = QLineEdit()
        self.txt_excluir.setPlaceholderText("ej. pip, setuptools, wheel")
        lay.addWidget(self.txt_excluir)
        self.chk_req = QCheckBox("Incluir solo los paquetes de un requirements.txt")
        lay.addWidget(self.chk_req)
        self.req = SelectorRuta("archivo", "Predeterminado: requirements.txt de la carpeta del venv",
                                "Requirements (*.txt);;Todos (*)")
        lay.addWidget(self.req)
        self.cuerpo.addWidget(card)

        self.btn_avanzado = boton("Mostrar opciones avanzadas", "fantasma")
        self.btn_avanzado.setCheckable(True)
        self.cuerpo.addWidget(self.btn_avanzado, 0, Qt.AlignmentFlag.AlignLeft)
        self.card_avanzado, lay = tarjeta(
            "Avanzado: JSON extra",
            "Opcional. Permite un encabezado propio, componentes que no son paquetes de Python "
            "(FFmpeg, Ghostscript…) y licencias para paquetes que no traen la suya.")
        self.extra = SelectorRuta("archivo", "licencias_extra.json", "JSON (*.json);;Todos (*)")
        lay.addWidget(self.extra)
        ayuda = QLabel(
            '{\n  "encabezado": "Texto propio bajo el título",\n'
            '  "componentes": [{"nombre": "FFmpeg", "version": "7.0", "tipo": "GPL v3",\n'
            '                   "url": "https://ffmpeg.org", "nota": "Proceso externo",\n'
            '                   "archivo": "tools/ffmpeg/LICENSE"}],\n'
            '  "faltantes": {"paquete": {"tipo": "MIT", "texto": "…"}}\n}')
        ayuda.setProperty("class", "comando")
        ayuda.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(ayuda)
        self.card_avanzado.setVisible(False)
        self.btn_avanzado.toggled.connect(self._toggle_avanzado)
        self.cuerpo.addWidget(self.card_avanzado)
        self.cuerpo.addStretch(1)

        self.btn_generar = boton("Generar documento", "primario")
        self.btn_generar.clicked.connect(lambda: self.generar(False))
        self.btn_listar = boton("Solo listar", tooltip="Muestra qué encontró sin escribir nada")
        self.btn_listar.clicked.connect(lambda: self.generar(True))
        self.btn_abrir = boton("Abrir archivo", "fantasma")
        self.btn_abrir.clicked.connect(lambda: self._ultima_salida and abrir_en_sistema(self._ultima_salida))
        for b in (self.btn_generar, self.btn_listar, self.btn_abrir):
            self.agregar_accion(b)

        for sig in (self.selector.cambiado, self.txt_app.textChanged, self.carpeta_salida.cambiado,
                    self.nombre_salida.textChanged, self.txt_excluir.textChanged, self.chk_req.toggled,
                    self.req.cambiado, self.extra.cambiado):
            sig.connect(self._cambio)

        self.sesiones.cargar_inicial()
        self.actualizar_acciones()

    def _toggle_avanzado(self, visible: bool):
        self.card_avanzado.setVisible(visible)
        self.btn_avanzado.setText("Ocultar opciones avanzadas" if visible else "Mostrar opciones avanzadas")

    def _cambio(self, *_):
        self.sesiones.marcar_modificado()
        self.req.setEnabled(self.chk_req.isChecked())

    def actualizar_acciones(self):
        if not self.ocupada():
            self.btn_abrir.setEnabled(bool(self._ultima_salida))

    def obtener_estado(self) -> dict:
        return {
            "python": self.selector.estado(),
            "app": self.txt_app.text().strip(),
            "carpeta_salida": self.carpeta_salida.texto(),
            "nombre_salida": self.nombre_salida.text().strip(),
            "excluir": self.txt_excluir.text().strip(),
            "solo_requeridos": self.chk_req.isChecked(),
            "requirements": self.req.texto(),
            "extra": self.extra.texto(),
        }

    def aplicar_estado(self, e: dict):
        self.selector.establecer(e.get("python"))
        self.txt_app.setText(e.get("app", ""))
        self.carpeta_salida.establecer(e.get("carpeta_salida", ""))
        self.nombre_salida.setText(e.get("nombre_salida") or "THIRD_PARTY_NOTICES.txt")
        self.txt_excluir.setText(e.get("excluir", ""))
        self.chk_req.setChecked(bool(e.get("solo_requeridos")))
        self.req.establecer(e.get("requirements", ""))
        self.extra.establecer(e.get("extra", ""))
        if e.get("extra") and not self.btn_avanzado.isChecked():
            self.btn_avanzado.setChecked(True)
        self._cambio()

    def generar(self, solo_listar: bool):
        if not self.selector.usa_global():
            try:
                buscar_python_venv(self.selector.venv())
            except ValueError as e:
                self.error(str(e))
                return
        if self.extra.texto() and not Path(self.extra.texto()).is_file():
            self.error("El JSON extra no existe.")
            return
        cfg = {
            "global": self.selector.usa_global(),
            "venv": self.selector.venv(),
            "app": self.txt_app.text().strip() or "esta aplicación",
            "carpeta_salida": self.carpeta_salida.texto(),
            "nombre_salida": self.nombre_salida.text().strip(),
            "excluir": self.txt_excluir.text(),
            "solo_requeridos": self.chk_req.isChecked(),
            "requirements": self.req.texto(),
            "extra": self.extra.texto(),
        }
        self.lanzar(tarea_licencias, (cfg, solo_listar), self._listo,
                    "Listando…" if solo_listar else "Generando documento…")

    def _listo(self, res: dict):
        if res.get("salida"):
            self._ultima_salida = res["salida"]
        self.estado(f"Listo: {res['total']} componentes.")


# ═════════════════════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ═════════════════════════════════════════════════════════════════════════════

class VentanaPrincipal(QMainWindow):
    def __init__(self, app: QApplication, config: Config):
        super().__init__()
        self.app, self.config = app, config
        self.setWindowTitle(APP_NOMBRE)
        self.resize(1320, 860)
        self.setMinimumSize(1000, 640)

        self.f_cuerpo = elegir_fuente(FUENTES_CUERPO)
        self.f_titulo = elegir_fuente(FUENTES_TITULO)
        self.f_mono = elegir_fuente(FUENTES_MONO)
        app.setFont(QFont(self.f_cuerpo, 10))

        raiz = QWidget()
        raiz.setObjectName("raiz")
        v = QVBoxLayout(raiz)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        barra = QFrame()
        barra.setObjectName("barraSuperior")
        h = QHBoxLayout(barra)
        h.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        h.setSpacing(SPACING_MD)
        titulo = QLabel(APP_NOMBRE)
        titulo.setProperty("class", "titulo-app")
        h.addWidget(titulo)
        sub = etiqueta("Copiar · Organizar · Listar rutas · Entornos Python · Licencias", "suave")
        sub.setWordWrap(False)
        sub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        h.addWidget(sub, 1)
        self.btn_tema = boton("", "fantasma", "Cambiar entre tema claro y oscuro")
        self.btn_tema.clicked.connect(self.alternar_tema)
        h.addWidget(self.btn_tema)
        v.addWidget(barra)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.paginas = [
            ("Copiar", PaginaCopiar(self)),
            ("Organizar", PaginaOrganizar(self)),
            ("Listar rutas", PaginaRutas(self)),
            ("Info entorno", PaginaEntorno(self)),
            ("Licencias", PaginaLicencias(self)),
        ]
        for nombre, pagina in self.paginas:
            self.tabs.addTab(pagina, nombre)
        v.addWidget(self.tabs, 1)
        self.setCentralWidget(raiz)

        idx = self.config.datos.get("pestana", 0)
        if isinstance(idx, int) and 0 <= idx < self.tabs.count():
            self.tabs.setCurrentIndex(idx)
        self.aplicar_tema(self.config.datos["tema"])
        if self.config.error:
            self.paginas[0][1].consola.agregar(self.config.error, "aviso")

    def aplicar_tema(self, tema: str):
        self.config.datos["tema"] = tema
        p = PALETAS[tema]
        self.app.setStyleSheet(construir_qss(p, preparar_iconos(p, tema),
                                             self.f_cuerpo, self.f_titulo, self.f_mono))
        self.btn_tema.setText("☀  Tema claro" if tema == "oscuro" else "☾  Tema oscuro")
        self.btn_tema.setMinimumWidth(self.btn_tema.sizeHint().width() + SPACING_MD)

    def alternar_tema(self):
        self.aplicar_tema("claro" if self.config.datos["tema"] == "oscuro" else "oscuro")
        self.config.guardar()

    def closeEvent(self, e):
        ocupadas = [n for n, p in self.paginas if p.ocupada()]
        if ocupadas:
            r = QMessageBox.question(
                self, APP_NOMBRE,
                f"Hay tareas en curso ({', '.join(ocupadas)}). ¿Cancelarlas y salir?")
            if r != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            for _, p in self.paginas:
                p.cancelar()
            for _, p in self.paginas:
                p.esperar()
        self.config.datos["pestana"] = self.tabs.currentIndex()
        self.config.guardar()
        e.accept()


def main():
    if ES_WINDOWS:
        try:  # icono propio en la barra de tareas en vez del de python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("utilidades.archivos")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NOMBRE)
    app.setStyle("Fusion")
    ventana = VentanaPrincipal(app, Config(CONFIG_PATH))
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
