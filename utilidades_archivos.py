# =============================================================================
#  Utilidades de archivos
#  Copyright (C) 2026  Kevin González (DoMiNaTh0R)
#  SPDX-License-Identifier: GPL-3.0-or-later
#
#  Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
#  los términos de la Licencia Pública General de GNU publicada por la Free
#  Software Foundation, ya sea la versión 3 de la Licencia o (a tu elección)
#  cualquier versión posterior.
#
#  Este programa se distribuye con la esperanza de que sea útil, pero SIN
#  NINGUNA GARANTÍA; ni siquiera la garantía implícita de COMERCIABILIDAD o
#  IDONEIDAD PARA UN PROPÓSITO PARTICULAR. Consulta la Licencia Pública General
#  de GNU para más detalles.
#
#  Deberías haber recibido una copia de la Licencia Pública General de GNU junto
#  con este programa (archivo LICENSE). Si no, visita <https://www.gnu.org/licenses/>.
#
#  El logo y el avatar (recursos/logo_app.png, app.ico y avatar_DoMiN.jpg) NO
#  están bajo la GPL: © Kevin González, todos los derechos reservados. Ver
#  recursos/LICENCIA_LOGO_Y_AVATAR.txt.
#
#  Código fuente: https://github.com/DoMiNaTh0R/UTILIDADES-ARCHIVOS-PYTHON
# =============================================================================
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
    6. Actualizaciones   winget upgrade: revisa que winget y sus orígenes sean los oficiales,
                         verifica SHA256 y firma (PowerShell), actualiza uno por uno y hace un reporte.
    7. Acerca de         Versión, creador, licencia y datos de la app.

La configuración (tema, sesiones guardadas, último venv...) y los registros viven en
%LOCALAPPDATA%\\UtilidadesArchivos (utilidades_config.json y registros\\), igual con el
código fuente que con el .exe compilado.

Requisitos: Python 3.9+ y PyQt6  (pip install PyQt6)

Compila igual con PyInstaller y con Nuitka (ver compilar.py). Tras compilar:
    UtilidadesArchivos.exe --autoprueba    prueba sin ventana y deja autoprueba.json
"""

from __future__ import annotations

import codecs
import copy
import fnmatch
import json
import math
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
import unicodedata
import urllib.parse
from collections import defaultdict, deque
from pathlib import Path

from PyQt6.QtCore import (PYQT_VERSION_STR, QT_VERSION_STR, QByteArray, QElapsedTimer, QObject, QProcess,
                          QSize, Qt, QThread, QTimer, QUrl, pyqtSignal)
from PyQt6.QtGui import (QColor, QDesktopServices, QFont, QFontDatabase, QFontMetrics, QIcon, QPainter,
                         QPainterPath, QPalette, QPixmap, QTextCharFormat, QTextCursor)
from PyQt6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QApplication, QButtonGroup,
                             QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
                             QGridLayout, QHBoxLayout, QHeaderView,
                             QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMainWindow, QMenu, QMessageBox,
                             QPlainTextEdit, QProgressBar, QPushButton,
                             QRadioButton, QScrollArea, QSizePolicy, QSpinBox,
                             QSplitter, QTableWidget, QTableWidgetItem,
                             QTabWidget, QVBoxLayout, QWidget)

# Datos de la app: los scripts de compilación los leen de aquí (sin importar PyQt6)
APP_NOMBRE = "Utilidades de archivos"
APP_ID = "UtilidadesArchivos"            # nombre del .exe y de su carpeta en %LOCALAPPDATA%
APP_VERSION = "1.1.0"
APP_AUTOR = "DoMiNaTh0R"
APP_AUTOR_NOMBRE = "Kevin González"
APP_ANIO = "2026"
APP_REPO = "https://github.com/DoMiNaTh0R/UTILIDADES-ARCHIVOS-PYTHON"
APP_LICENCIA = "GNU GPL v3"
APP_USER_MODEL_ID = "DoMiNaTh0R.UtilidadesArchivos"

ES_WINDOWS = sys.platform.startswith("win")


# ─── Rutas (código fuente, PyInstaller y Nuitka) ────────────────────────────

def forma_de_ejecucion() -> str:
    if getattr(sys, "frozen", False):
        return "PyInstaller"
    if "__compiled__" in globals():
        return "Nuitka"
    return "Código fuente"


def carpeta_app() -> Path:
    """Carpeta real del script o del .exe (en un onefile, la del .exe, no la temporal)."""
    if getattr(sys, "frozen", False):                      # PyInstaller
        return Path(sys.executable).resolve().parent
    compilado = globals().get("__compiled__")
    if compilado is not None:                              # Nuitka: __file__ apunta a la
        contenedora = getattr(compilado, "containing_dir", None)   # carpeta de extracción
        if contenedora:
            return Path(contenedora)
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent


def carpeta_recursos() -> Path:
    """recursos\\ (logo, avatar, icono): dentro del paquete compilado o junto al script."""
    meipass = getattr(sys, "_MEIPASS", None)
    base = Path(meipass) if meipass else Path(__file__).resolve().parent
    return base / "recursos"


def recurso(nombre: str) -> Path:
    return carpeta_recursos() / nombre


def archivo_legal(nombre: str) -> Path | None:
    """LICENSE o THIRD_PARTY_NOTICES.txt: junto al .exe, dentro del paquete compilado o en la raíz del proyecto."""
    candidatos = [carpeta_app() / nombre, carpeta_recursos().parent / nombre, carpeta_recursos() / nombre,
                  Path(__file__).resolve().parent / nombre, Path(__file__).resolve().parent.parent / nombre]
    return next((c for c in candidatos if c.is_file()), None)


def carpeta_datos() -> Path:
    """
    Dónde van la configuración, los registros y fallo_grave.log: %LOCALAPPDATA%\\UtilidadesArchivos,
    igual con el código fuente, PyInstaller o Nuitka. La variable UTILIDADES_DATOS la cambia
    (la usa la autoprueba).
    """
    if os.environ.get("UTILIDADES_DATOS"):
        return Path(os.environ["UTILIDADES_DATOS"])
    if "--autoprueba" in sys.argv:          # nunca toca tu configuración real
        return Path(tempfile.gettempdir()) / f"{APP_ID}_autoprueba"
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / APP_ID


CARPETA_DATOS = carpeta_datos()
CONFIG_PATH = CARPETA_DATOS / "utilidades_config.json"


def migrar_datos_viejos():
    """
    Hasta ahora la configuración y los registros se guardaban junto al script o al .exe.
    La primera vez que la app usa %LOCALAPPDATA% se copian ahí (los originales no se tocan).
    """
    if os.environ.get("UTILIDADES_DATOS") or "--autoprueba" in sys.argv or CONFIG_PATH.exists():
        return
    viejo = carpeta_app()
    if viejo.resolve() == CARPETA_DATOS.resolve():
        return
    try:
        if (viejo / "utilidades_config.json").is_file():
            CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
            shutil.copy2(viejo / "utilidades_config.json", CONFIG_PATH)
        if (viejo / "registros").is_dir():
            destino = CARPETA_DATOS / "registros"
            destino.mkdir(parents=True, exist_ok=True)
            for archivo in (viejo / "registros").iterdir():
                if archivo.is_file() and not (destino / archivo.name).exists():
                    shutil.copy2(archivo, destino / archivo.name)
    except OSError:
        pass


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
    svgs = {nombre: (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3" '
                     'stroke-linecap="round" stroke-linejoin="round"/>')
            for nombre, (d, color) in trazos.items()}
    # Engranaje (botón de opciones): contorno con 8 dientes y el agujero del centro
    svgs["engranaje"] = (f'<path d="{ruta_engranaje()}" fill="{p["texto_suave"]}" fill-rule="evenodd" '
                         f'stroke="{p["texto_suave"]}" stroke-width="1" stroke-linejoin="round"/>')
    rutas = {}
    for nombre, cuerpo in svgs.items():
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">{cuerpo}</svg>'
        ruta = carpeta / f"{nombre}_{tema}.svg"
        try:
            ruta.write_text(svg, encoding="utf-8")
        except OSError:
            pass
        rutas[nombre] = ruta.as_posix()
    return rutas


def ruta_engranaje(dientes: int = 8, r_ext: float = 10.5, r_int: float = 7.8, r_hueco: float = 3.2) -> str:
    paso = 2 * math.pi / dientes
    puntos = []
    for i in range(dientes):
        a = i * paso - math.pi / 2
        for desfase, r in ((-0.29, r_int), (-0.15, r_ext), (0.15, r_ext), (0.29, r_int)):
            puntos.append((12 + r * math.cos(a + desfase * paso), 12 + r * math.sin(a + desfase * paso)))
    contorno = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in puntos) + " Z"
    hueco = (f"M{12 + r_hueco:.2f} 12 A{r_hueco} {r_hueco} 0 1 0 {12 - r_hueco:.2f} 12 "
             f"A{r_hueco} {r_hueco} 0 1 0 {12 + r_hueco:.2f} 12 Z")
    return f"{contorno} {hueco}"


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
QLabel[class="error-texto"] {{ color: {COLOR_LOG['error']}; font-weight: 700; }}
QLabel[class="chip-ok"], QLabel[class="chip-aviso"], QLabel[class="chip-error"], QLabel[class="chip-info"],
QLabel[class="chip-primario"] {{
    font-size: {TXT_LABEL_MD}px;
    font-weight: 600;
    border-radius: 12px;
    padding: 4px {SPACING_MD - 4}px;
}}
QLabel[class="chip-ok"] {{ color: {COLOR_LOG['ok']}; background-color: rgba(46, 157, 91, 0.14);
    border: 1px solid rgba(46, 157, 91, 0.45); }}
QLabel[class="chip-aviso"] {{ color: {COLOR_LOG['aviso']}; background-color: rgba(208, 135, 0, 0.14);
    border: 1px solid rgba(208, 135, 0, 0.45); }}
QLabel[class="chip-error"] {{ color: {COLOR_LOG['error']}; background-color: rgba(229, 72, 77, 0.14);
    border: 1px solid rgba(229, 72, 77, 0.45); }}
QLabel[class="chip-info"] {{ color: {p['texto_suave']}; background-color: {p['superficie_baja']};
    border: 1px solid {p['borde']}; }}
QLabel[class="chip-primario"] {{ color: {p['texto_primario_suave']}; background-color: {p['primario_suave']};
    border: 1px solid {p['primario_suave']}; }}
QLabel[class="version"] {{
    font-size: {TXT_LABEL_MD}px;
    font-weight: 600;
    color: {p['texto_primario_suave']};
    background-color: {p['primario_suave']};
    border-radius: {RADIUS_DEFAULT}px;
    padding: 2px {SPACING_SM}px;
}}
QLabel[class="autor"] {{
    font-family: '{f_titulo}';
    font-size: {TXT_HEADLINE_SM}px;
    font-weight: 700;
}}

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
QPushButton[class="creador"] {{
    background: transparent;
    border: 1px solid {p['borde']};
    border-radius: 16px;
    color: {p['texto']};
    padding: 3px {SPACING_MD - 4}px 3px 4px;
    text-align: left;
}}
QPushButton[class="creador"]:hover {{ background-color: {p['superficie_baja']}; border-color: {p['borde_fuerte']}; }}
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

/* ─── Menús (clic derecho: Copiar, Pegar…) ───────── */
QMenu {{
    background-color: {p['superficie']};
    color: {p['texto']};
    border: 1px solid {p['borde_fuerte']};
    padding: {SPACING_XS}px;
}}
QMenu::item {{
    background: transparent;
    padding: 6px {SPACING_LG}px 6px {SPACING_SM + SPACING_XS}px;
    border-radius: {RADIUS_DEFAULT}px;
}}
QMenu::item:selected {{ background-color: {p['primario_suave']}; color: {p['texto_primario_suave']}; }}
QMenu::item:disabled {{ color: {p['deshabilitado_texto']}; background: transparent; }}
QMenu::separator {{ height: 1px; background: {p['borde']}; margin: {SPACING_XS}px {SPACING_SM}px; }}

/* ─── Actualizaciones ────────────────────────────── */
QFrame#barraAcciones {{
    background-color: {p['superficie']};
    border: none;
    border-top: 1px solid {p['borde']};
}}
QTabWidget#pestanasPaquetes::tab-bar {{ left: 0px; }}
QPushButton#btnOpciones {{ qproperty-icon: url({ic['engranaje']}); qproperty-iconSize: 18px 18px; }}
QFrame[class="dato-reporte"] {{
    background-color: {p['superficie_baja']};
    border: 1px solid {p['borde']};
    border-radius: {RADIUS_LG}px;
}}
QLabel[class="numero-reporte"] {{
    font-family: '{f_titulo}';
    font-size: 26px;
    font-weight: 700;
}}
QLabel[class="mono"] {{ font-family: '{f_mono}'; font-size: {TXT_LABEL_MD}px; }}
QLabel[class="seccion"] {{
    font-family: '{f_titulo}';
    font-size: {TXT_BODY_MD}px;
    font-weight: 600;
    padding-top: {SPACING_XS}px;
}}
"""


def paleta_qt(p: dict) -> QPalette:
    """
    Colores del tema para lo que Qt dibuja por su cuenta (menús de clic derecho, selección,
    diálogos): sin esto, en el tema oscuro salían con fondo blanco y letra clara.
    """
    pal = QPalette()
    grupos = (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled)
    R = QPalette.ColorRole
    colores = {
        R.Window: p["bg"], R.WindowText: p["texto"], R.Base: p["superficie"],
        R.AlternateBase: p["superficie_baja"], R.Text: p["texto"], R.Button: p["superficie"],
        R.ButtonText: p["texto"], R.BrightText: p["peligro"], R.Highlight: p["primario_suave"],
        R.HighlightedText: p["texto_primario_suave"], R.ToolTipBase: p["tooltip_bg"],
        R.ToolTipText: p["tooltip_texto"], R.PlaceholderText: p["texto_suave"], R.Link: p["primario"],
        R.LinkVisited: p["primario"], R.Light: p["superficie_alta"], R.Midlight: p["superficie_baja"],
        R.Mid: p["borde"], R.Dark: p["borde_fuerte"], R.Shadow: p["bg"],
    }
    for grupo in grupos:
        for rol, color in colores.items():
            pal.setColor(grupo, rol, QColor(color))
    for rol in (R.WindowText, R.Text, R.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, rol, QColor(p["deshabilitado_texto"]))
    return pal


def cargar_traduccion_qt(app: QApplication):
    """Los menús propios de Qt (Copiar, Pegar, Seleccionar todo…) en español."""
    from PyQt6.QtCore import QLibraryInfo, QTranslator
    # La de Qt; en la versión de Nuitka, compilar.py la deja en traducciones\
    carpetas = [QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
                str(carpeta_recursos().parent / "traducciones"),
                str(carpeta_app() / "traducciones")]
    traductor = QTranslator(app)
    for carpeta in carpetas:
        if carpeta and traductor.load("qtbase_es", carpeta):
            app.installTranslator(traductor)
            return True
    return False


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN (JSON en %LOCALAPPDATA%\UtilidadesArchivos)
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
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
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


def titulo_card(texto: str) -> QLabel:
    t = QLabel(texto)
    t.setProperty("class", "titulo-card")
    return t


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


_CACHE_IMAGENES: dict[str, QPixmap] = {}


def imagen(nombre: str) -> QPixmap:
    """Imagen de recursos\\ (se lee una sola vez). Si falta, un pixmap nulo: la app sigue igual."""
    if nombre not in _CACHE_IMAGENES:
        _CACHE_IMAGENES[nombre] = QPixmap(str(recurso(nombre)))
    return _CACHE_IMAGENES[nombre]


def pixmap_escalado(nombre: str, lado: int, dpr: float = 1.0) -> QPixmap:
    original = imagen(nombre)
    if original.isNull():
        return QPixmap()
    px = original.scaled(int(lado * dpr), int(lado * dpr), Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    px.setDevicePixelRatio(dpr)
    return px


def pixmap_circular(nombre: str, lado: int, dpr: float = 1.0) -> QPixmap:
    """Recorte circular (para el avatar del creador)."""
    original = imagen(nombre)
    if original.isNull():
        return QPixmap()
    tam = int(lado * dpr)
    cuadrado = original.scaled(tam, tam, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
    salida = QPixmap(tam, tam)
    salida.fill(Qt.GlobalColor.transparent)
    p = QPainter(salida)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    camino = QPainterPath()
    camino.addEllipse(0, 0, tam, tam)
    p.setClipPath(camino)
    p.drawPixmap((tam - cuadrado.width()) // 2, (tam - cuadrado.height()) // 2, cuadrado)
    p.end()
    salida.setDevicePixelRatio(dpr)
    return salida


def refrescar_estilo(w: QWidget):
    w.style().unpolish(w)
    w.style().polish(w)


def pasar_rueda_a_pagina(widget: QWidget, e):
    """Manda la rueda del mouse a la barra de desplazamiento de la página que contiene al widget."""
    padre = widget.parentWidget()
    while padre is not None and not isinstance(padre, QAbstractScrollArea):
        padre = padre.parentWidget()
    if padre is not None:
        QApplication.sendEvent(padre.verticalScrollBar(), e)
    e.accept()


class SpinSinRueda(QSpinBox):
    """QSpinBox que ignora la rueda del mouse: al desplazarte por la página no cambia de valor."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, e):
        pasar_rueda_a_pagina(self, e)


class ComboSinRueda(QComboBox):
    """QComboBox que ignora la rueda del mouse (igual que SpinSinRueda)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, e):
        pasar_rueda_a_pagina(self, e)


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
        self.combo = ComboSinRueda()
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
CARPETA_REGISTROS = CARPETA_DATOS / "registros"


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
    # Resultado de la detección de discos, que corre en otro hilo: consultar un disco
    # dormido o una unidad de red puede tardar segundos y congelaría la ventana.
    discos_detectados = pyqtSignal(dict, int)

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
        self._gen_discos = self._gen_mostrada = 0   # se muestra solo la última detección pedida
        self._tras_discos = None                # qué hacer cuando termine (iniciar la copia)
        self.discos_detectados.connect(self._discos_listos)
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
        self.sp_reintentos = SpinSinRueda()
        self.sp_reintentos.setRange(0, 9999)
        self.sp_espera = SpinSinRueda()
        self.sp_espera.setRange(0, 3600)
        self.sp_espera.setSuffix(" s")
        self.chk_mt = QCheckBox("Multihilo (/MT)")
        self.chk_mt.setToolTip("Copia varios archivos a la vez. Más rápido con muchos archivos pequeños.")
        fila_hilos = QHBoxLayout()
        fila_hilos.setSpacing(SPACING_SM)
        self.sp_hilos = SpinSinRueda()
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
        self.chk_registro = QCheckBox("Guardar el registro completo en un .txt (carpeta «registros»: Acerca de → Abrir registros)")
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
    @staticmethod
    def _clave_disco(ruta: str) -> str | None:
        if not ruta:
            return None
        return ntpath.splitdrive(ntpath.abspath(ruta))[0].upper() if ES_WINDOWS else ruta

    def _detectar_discos(self, refrescar: bool = False, luego=None):
        """Consulta en otro hilo los discos que falten (o todos con refrescar) y luego los muestra."""
        rutas = (self.origen.texto(), self.destino.texto())
        faltan = {}
        for ruta in rutas:
            clave = self._clave_disco(ruta)
            if clave and (refrescar or clave not in self._cache_discos):
                faltan[clave] = ruta
        if luego is not None:
            self._tras_discos = luego
        if not faltan:
            self._mostrar_discos()
            if self._gen_discos == self._gen_mostrada:      # no hay otra consulta en curso
                self._ejecutar_tras_discos()
            return
        self._gen_discos += 1
        gen = self._gen_discos

        def consultar():
            resultado = {}
            for clave, ruta in faltan.items():
                try:
                    resultado[clave] = info_unidad(ruta)
                except Exception:
                    resultado[clave] = None
            self.discos_detectados.emit(resultado, gen)

        threading.Thread(target=consultar, daemon=True, name="detectar_discos").start()

    def _discos_listos(self, resultado: dict, gen: int):
        self._cache_discos.update(resultado)
        if gen != self._gen_discos:
            return          # llegará una detección más nueva
        self._gen_mostrada = gen
        self._mostrar_discos()
        self._ejecutar_tras_discos()

    def _ejecutar_tras_discos(self):
        accion, self._tras_discos = self._tras_discos, None
        if accion is not None:
            accion()

    def _mostrar_discos(self):
        infos = [self._cache_discos.get(self._clave_disco(self.origen.texto())),
                 self._cache_discos.get(self._clave_disco(self.destino.texto()))]
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

        self._cancelado = False
        self._totales = None
        self._progreso = None
        self._fase = "discos"
        self.set_ocupado(True)
        self.estado("Revisando los discos…")
        # Se vuelven a consultar por si conectaste otro USB con la misma letra;
        # los hilos automáticos se ajustan antes de armar el comando.
        self._detectar_discos(refrescar=True, luego=lambda: self._iniciar_tras_discos(extra_xd))

    def _iniciar_tras_discos(self, extra_xd: list[str]):
        if self._fase != "discos":      # se canceló mientras se revisaban los discos
            return
        self._args_copia = self.argumentos(extra_xd)
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
        # Qt puede avisar «finished» antes que el último «readyRead»: se lee lo que quedó en el búfer
        self._leer()
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
        elif self._fase == "discos":
            self.consola.agregar("Copia cancelada por el usuario.", "aviso")
            self.estado("Cancelado.")
            self.salio_bien = False
            self._fin()

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
        carpeta = self.carpeta_salida.texto() or d.get("carpeta_venv") or str(CARPETA_DATOS)
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

    carpeta = cfg["carpeta_salida"] or (str(carpeta_venv) if carpeta_venv else str(CARPETA_DATOS))
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
# 6. ACTUALIZACIONES (WINGET + REVISIÓN DE FIRMAS CON POWERSHELL)
# ═════════════════════════════════════════════════════════════════════════════
#
# winget se ejecuta directamente en un QProcess: no traba la interfaz y su código de salida es
# el real. PowerShell solo revisa firmas digitales, con comandos cortos y legibles: nada de
# -EncodedCommand ni -ExecutionPolicy Bypass, porque antivirus como Avast bloquean
# powershell.exe cuando se lanza así (es el patrón típico del malware).
# Seguridad:
#   · winget tiene que ser el original: App Installer firmado por Microsoft (Get-AppxPackage
#     y Get-AuthenticodeSignature sobre winget.exe).
#   · El origen «winget» tiene que ser el oficial (URL, identificador y tipo exactos).
#   · La opción de administrador InstallerHashOverride tiene que estar desactivada: así winget
#     siempre comprueba el SHA256 de cada instalador contra su manifiesto y rechaza el que no
#     coincida. Nunca se usa --ignore-security-hash.
#   · Solo los paquetes de los orígenes oficiales de winget se actualizan en lote; los de la
#     Microsoft Store, de terceros o mal identificados quedan para revisión manual.
#   · Opcional: «winget show» (SHA256 y sitio del instalador) y descarga previa del instalador
#     para revisar su firma digital (Get-AuthenticodeSignature) y recalcular su SHA256.

_SISTEMA = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32"
POWERSHELL = str(_SISTEMA / "WindowsPowerShell" / "v1.0" / "powershell.exe")
TASKKILL = str(_SISTEMA / "taskkill.exe")
CMD = os.environ.get("ComSpec") or str(_SISTEMA / "cmd.exe")

# PowerShell escribe en UTF-8 y devuelve sus datos en una línea marcada con JSON
PREAMBULO_PS = "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
MARCA_JSON = "@@JSON@@ "

# Orígenes oficiales tal como los devuelve «winget source export»: (URL, identificador, tipo, descripción)
ORIGENES_OFICIALES = {
    "winget": ("https://cdn.winget.microsoft.com/cache", "Microsoft.Winget.Source_8wekyb3d8bbwe",
               "Microsoft.PreIndexed.Package", "repositorio oficial de winget (Microsoft)"),
    "winget-font": ("https://cdn.winget.microsoft.com/fonts", "Microsoft.Winget.Fonts.Source_8wekyb3d8bbwe",
                    "Microsoft.PreIndexed.Package", "fuentes tipográficas oficiales de winget"),
    "msstore": ("https://storeedgefd.dsx.mp.microsoft.com/v9.0", "StoreEdgeFD",
                "Microsoft.Rest", "Microsoft Store"),
}
# Solo estos se actualizan en lote: sus manifiestos traen el SHA256 de cada instalador
ORIGENES_EN_LOTE = {"winget", "winget-font"}

# ¿winget es el original? Paquete App Installer y firma digital de su winget.exe
SCRIPT_APPX = (
    "$p = Get-AppxPackage -Name Microsoft.DesktopAppInstaller | Sort-Object Version -Descending | "
    "Select-Object -First 1; "
    "$r = [ordered]@{}; "
    "if ($p) { "
    "$exe = Join-Path $p.InstallLocation 'winget.exe'; "
    "$s = if (Test-Path -LiteralPath $exe) { Get-AuthenticodeSignature -LiteralPath $exe } else { $null }; "
    "$r = [ordered]@{ Version = [string]$p.Version; SignatureKind = [string]$p.SignatureKind; "
    "Publisher = [string]$p.Publisher; Status = [string]$p.Status; Exe = $exe; "
    "Firma = if ($s) { [string]$s.Status } else { 'NoEncontrado' }; "
    "Firmante = if ($s -and $s.SignerCertificate) { $s.SignerCertificate.Subject } else { $null } } }; "
    "'" + MARCA_JSON + "' + ($r | ConvertTo-Json -Compress)"
)


def ps_texto(valor) -> str:
    """Cadena literal de PowerShell (comillas simples: nada se interpreta)."""
    return "'" + str(valor).replace("'", "''") + "'"


def script_firma_archivo(ruta: str) -> str:
    """Firma digital y SHA256 de un archivo descargado (Get-AuthenticodeSignature y Get-FileHash)."""
    return ("$f = " + ps_texto(ruta) + "; "
            "$s = Get-AuthenticodeSignature -LiteralPath $f; "
            "$r = [ordered]@{ Estado = [string]$s.Status; "
            "Firmante = if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { $null }; "
            "Emisor = if ($s.SignerCertificate) { $s.SignerCertificate.Issuer } else { $null }; "
            "SelloDeTiempo = [bool]$s.TimeStamperCertificate; "
            "Sha256 = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash }; "
            "'" + MARCA_JSON + "' + ($r | ConvertTo-Json -Compress)")


def comando_powershell(script: str) -> tuple[str, list[str]]:
    return POWERSHELL, ["-NoProfile", "-Command", PREAMBULO_PS + script]


def comando_winget(winget: str, args: list[str]) -> tuple[str, list[str]]:
    """Programa y argumentos para winget (o para el winget simulado de las pruebas, si es un .cmd)."""
    if winget.lower().endswith((".cmd", ".bat")):
        return CMD, ["/d", "/s", "/c", winget] + list(args)
    return winget, list(args)


def linea_de_comando(programa: str, args: list[str]) -> list[str] | str:
    """
    Lo que recibe Popen. Con «cmd /s /c» la orden completa va entre un par de comillas extra:
    si no, cmd quita las comillas equivocadas cuando hay rutas con espacios o paréntesis
    (ej. --location "C:\\Program Files (x86)\\...").
    """
    if programa == CMD and "/c" in args:
        i = args.index("/c") + 1
        return (subprocess.list2cmdline([programa] + args[:i])
                + ' "' + subprocess.list2cmdline(args[i:]) + '"')
    return [programa] + list(args)


def es_administrador() -> bool:
    if not ES_WINDOWS:
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def comando_visible(args: list[str]) -> str:
    """Cómo se escribiría en PowerShell (sin comillas si no hacen falta)."""
    return "winget " + " ".join(a if re.fullmatch(r"[\w.:+\-/<>=@]+", a) else ps_texto(a) for a in args)


def codigo_hex(codigo: int) -> str:
    return f"0x{codigo & 0xFFFFFFFF:08X}"


# Códigos de salida de winget (los mismos nombres que muestra «winget error <código>»)
CODIGOS_WINGET = {
    0x8A150008: ("error", "No se pudo descargar el instalador (revisa tu conexión)."),
    0x8A150010: ("error", "No hay un instalador compatible con este equipo."),
    0x8A150011: ("error", "El SHA256 del instalador NO coincide con el manifiesto: winget lo bloqueó por seguridad."),
    0x8A150014: ("error", "No se encontró el paquete en el origen."),
    0x8A150019: ("error", "Necesita permisos de administrador."),
    0x8A15002B: ("aviso", "No hay una actualización aplicable (puede que ya esté al día o que el instalador cambió)."),
    0x8A15002D: ("error", "El instalador no pasó la comprobación de seguridad del antivirus."),
    0x8A150041: ("error", "No se aceptaron los acuerdos del paquete."),
    0x8A15005F: ("error", "El instalador pide la carpeta de instalación (--location) y no se pudo averiguar: "
                          "actualízalo desde el propio programa."),
    0x8A150101: ("error", "El programa está abierto: ciérralo y vuelve a intentarlo."),
    0x8A150102: ("error", "Hay otra instalación en curso; espera a que termine."),
    0x8A150103: ("error", "Un archivo del programa está en uso."),
    0x8A150104: ("error", "Falta una dependencia."),
    0x8A150105: ("error", "El disco está lleno."),
    0x8A150106: ("error", "No hay memoria suficiente."),
    0x8A150107: ("error", "Sin conexión a internet."),
    0x8A150108: ("error", "El instalador falló (el fabricante recomienda contactar a soporte)."),
    0x8A150109: ("reinicio", "Actualizado: reinicia el equipo para terminar."),
    0x8A15010A: ("error", "Falló: reinicia el equipo y vuelve a intentarlo."),
    0x8A15010B: ("reinicio", "El instalador reinició (o reiniciará) el equipo."),
    0x8A15010C: ("aviso", "Cancelado en el instalador."),
    0x8A15010D: ("aviso", "Ya hay otra versión instalada y el instalador no la reemplaza."),
    0x8A15010E: ("aviso", "Ya hay una versión más nueva instalada."),
    0x8A15010F: ("error", "Bloqueado por una directiva del sistema."),
    0x8A150110: ("error", "Fallaron las dependencias del paquete."),
    0x8A150111: ("error", "Otra aplicación está usando el programa: ciérrala y vuelve a intentarlo."),
    0x8A150112: ("error", "El instalador recibió un parámetro no válido."),
    0x8A150113: ("error", "Este sistema no es compatible con el paquete."),
    0x8A150114: ("error", "Este instalador no permite actualizar: desinstala e instala de nuevo."),
    0x800704C7: ("aviso", "Cancelado (¿rechazaste el permiso de administrador?)."),
    0xFFFFFFFF: ("error", "No se pudo ejecutar winget (revisa el registro)."),
}


def describir_codigo_winget(codigo: int) -> tuple[str | None, str]:
    """(tipo, texto). tipo None = código desconocido (se pregunta a «winget error»)."""
    codigo &= 0xFFFFFFFF
    if codigo == 0:
        return "ok", "Actualizado correctamente."
    if codigo in CODIGOS_WINGET:
        return CODIGOS_WINGET[codigo]
    return None, f"winget terminó con el código {codigo_hex(codigo)}."


# ─── Lectura de la salida de winget ─────────────────────────────────────────

RE_GUIONES_WINGET = re.compile(r"^\s*-{10,}\s*$")
RE_SHA256 = re.compile(r"\b[0-9a-fA-F]{64}\b")
RE_URL = re.compile(r"https?://[^\s\"'<>]+")
RE_HASH_OK = re.compile(r"hash.*(verific|validat)|(verific|validat).*hash", re.I)
RE_SOLO_GIRO = re.compile(r"^\s*[-\\|/]?\s*$")
RE_TAMANOS = re.compile(r"([\d.,]+\s*[KMG]?B)\s*/\s*([\d.,]+\s*[KMG]?B)")


def ancho_visual(c: str) -> int:
    """Columnas que ocupa un carácter en la consola (los ideogramas ocupan 2)."""
    if unicodedata.combining(c):
        return 0
    return 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1


def ancho_texto(texto: str) -> int:
    return sum(ancho_visual(c) for c in texto)


def inicios_de_columnas(cabecera: str) -> list[int]:
    inicios, col, tras_espacio = [], 0, True
    for c in cabecera:
        if not c.isspace() and tras_espacio:
            inicios.append(col)
        tras_espacio = c.isspace()
        col += ancho_visual(c)
    return inicios


def cortar_columnas(linea: str, inicios: list[int]) -> list[str]:
    """Corta una fila de la tabla de winget por columnas visuales."""
    celdas = [""] * len(inicios)
    col, idx = 0, 0
    for c in linea:
        while idx + 1 < len(inicios) and col >= inicios[idx + 1]:
            idx += 1
        celdas[idx] += c
        col += ancho_visual(c)
    return [c.strip() for c in celdas]


def _tokens_desde_la_derecha(linea: str, n: int) -> list[str] | None:
    """n columnas separadas por espacios; la primera (el nombre) puede llevar espacios."""
    tokens: list[str] = []
    for t in linea.split():
        if tokens and tokens[-1] in ("<", ">"):     # «< 1.2.3» es una sola versión
            tokens[-1] += " " + t
        else:
            tokens.append(t)
    if len(tokens) < n:
        return None
    return [" ".join(tokens[:len(tokens) - (n - 1)])] + tokens[len(tokens) - (n - 1):]


def _parece_version(v: str) -> bool:
    return v == "Unknown" or any(ch.isdigit() for ch in v)


def _validar_celdas(celdas: list[str], origenes: set, origen_unico: str | None) -> dict | None:
    if len(celdas) == 5:
        nombre, id_, instalada, disponible, origen = celdas
        if origen not in origenes:
            return None
    elif len(celdas) == 4 and origen_unico:
        nombre, id_, instalada, disponible = celdas
        origen = origen_unico
    else:
        return None
    if not nombre or not id_ or not re.fullmatch(r"\S+", id_):
        return None
    if not _parece_version(instalada) or not _parece_version(disponible):
        return None
    return {"nombre": nombre, "id": id_, "instalada": instalada, "disponible": disponible,
            "origen": origen, "id_cortado": id_.endswith("…"),
            "desconocida": instalada.strip().lower() == "unknown"}


def parsear_fila_winget(linea: str, inicios: list[int], origenes: set, origen_unico: str | None) -> dict | None:
    if not linea.strip():
        return None
    candidatos = []
    if len(inicios) in (4, 5):
        candidatos.append(cortar_columnas(linea, inicios))
    for n in ((len(inicios),) if len(inicios) in (4, 5) else (5, 4)):
        tokens = _tokens_desde_la_derecha(linea, n)
        if tokens:
            candidatos.append(tokens)
    for celdas in candidatos:
        fila = _validar_celdas(celdas, origenes, origen_unico)
        if fila:
            return fila
    return None


def parsear_lista_winget(texto: str, origenes: set, origen_unico: str | None = None) -> list[dict]:
    """
    Filas de «winget upgrade» (o «winget list»). No depende del idioma: busca la línea de
    guiones, toma la anterior como cabecera y lee filas hasta la primera que no encaje. Si hay
    una segunda tabla (paquetes que necesitan actualización explícita) se marca.
    """
    lineas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    filas, tabla, i = [], 0, 1
    while i < len(lineas):
        if RE_GUIONES_WINGET.match(lineas[i]) and lineas[i - 1].strip():
            tabla += 1
            inicios = inicios_de_columnas(lineas[i - 1])
            j = i + 1
            while j < len(lineas):
                fila = parsear_fila_winget(lineas[j], inicios, origenes, origen_unico)
                if fila is None:
                    break
                fila["explicito"] = tabla > 1
                filas.append(fila)
                j += 1
            i = j + 1
            continue
        i += 1
    return filas


def parsear_show(texto: str, id_: str) -> dict:
    """SHA256, URL del instalador, editor y versión de «winget show» (en cualquier idioma)."""
    lineas = [x.rstrip() for x in texto.replace("\r\n", "\n").split("\n")]
    info = {"sha256": None, "url": None, "editor": None, "version": None}
    # Tras «Encontrado Nombre [Id]» siempre vienen la versión y el editor
    for k, linea in enumerate(lineas):
        if f"[{id_}]".lower() in linea.lower():
            siguientes = [x for x in lineas[k + 1:k + 5] if x.strip()]
            if len(siguientes) >= 1 and ":" in siguientes[0]:
                info["version"] = siguientes[0].split(":", 1)[1].strip()
            if len(siguientes) >= 2 and ":" in siguientes[1]:
                info["editor"] = siguientes[1].split(":", 1)[1].strip()
            break
    # El SHA256 va en el bloque del instalador, justo después de su URL
    for k, linea in enumerate(lineas):
        m = RE_SHA256.search(linea)
        if m and "sha256" in linea.lower():
            info["sha256"] = m.group(0).lower()
            for kk in range(k - 1, max(k - 4, -1), -1):
                u = RE_URL.search(lineas[kk])
                if u:
                    info["url"] = u.group(0)
                    break
            break
    return info


RE_RUTA_WINDOWS = re.compile(r"^[A-Za-z]:\\")


def leer_ubicacion_instalada(texto: str) -> str | None:
    """
    Carpeta donde ya está instalado, de «winget list --id X --exact --details»
    («Ubicación instalada: C:\\...»; el nombre del campo cambia con el idioma, la ruta no).
    """
    for linea in texto.splitlines():
        _, sep, valor = linea.partition(": ")
        valor = valor.strip().strip('"')
        if sep and RE_RUTA_WINDOWS.match(valor) and os.path.isdir(valor):
            return valor
    return None


def dominio(url: str | None) -> str:
    if not url:
        return ""
    try:
        return urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return ""


def nombre_del_certificado(sujeto: str | None) -> str:
    if not sujeto:
        return ""
    m = re.search(r'CN=("[^"]+"|[^,]+)', sujeto)
    return (m.group(1) if m else sujeto).strip().strip('"')


def evaluar_manifiesto(info: dict, codigo: int, estricto: bool) -> tuple[str, str]:
    """Resultado de «winget show»: (tipo, texto corto para la tabla)."""
    if codigo != 0 and not info.get("sha256"):
        return ("error" if estricto else "aviso"), f"No se pudo leer el manifiesto ({codigo_hex(codigo)})"
    if not info.get("sha256"):
        return ("error" if estricto else "aviso"), "El manifiesto no trae SHA256"
    sitio = dominio(info.get("url")) or "sitio desconocido"
    if (info.get("url") or "").lower().startswith("http://"):
        return "aviso", f"SHA256 · {sitio} (sin HTTPS)"
    return "ok", f"SHA256 · {sitio}"


def evaluar_firma(firma: dict | None, sha_manifiesto: str | None, codigo: int) -> tuple[str, str]:
    """Resultado de la descarga previa: (tipo, texto). tipo 'sin_firma' = descargado bien pero sin firmar."""
    if codigo != 0:
        tipo, texto = describir_codigo_winget(codigo)
        return "error", f"No se pudo descargar: {texto if tipo else codigo_hex(codigo)}"
    if not firma:
        return "error", "No se encontró el instalador descargado"
    if firma.get("Estado") == "SinRespuesta":
        return "aviso", "No se pudo revisar la firma: PowerShell no respondió (¿lo bloqueó el antivirus?)"
    if sha_manifiesto and (firma.get("Sha256") or "").lower() != sha_manifiesto.lower():
        return "error", "¡El SHA256 del archivo no coincide con el manifiesto!"
    estado = firma.get("Estado") or ""
    quien = nombre_del_certificado(firma.get("Firmante"))
    if estado == "Valid":
        return "ok", f"Firma válida: {quien}"
    if estado == "NotSigned":
        if (firma.get("Archivo") or "").lower().endswith((".zip", ".7z")):
            return "sin_firma", "Archivo comprimido (no lleva firma)"
        return "sin_firma", "El instalador no tiene firma digital"
    if estado == "HashMismatch":
        return "error", "¡La firma digital no corresponde al archivo!"
    return "aviso", f"Firma no confiable ({estado}){': ' + quien if quien else ''}"


NIVELES_SALTO = ["Mayor", "Menor", "Parche", "Compilación"]


def numeros_de_version(v: str | None) -> list[int] | None:
    if not v or v.strip().lower() == "unknown":
        return None
    numeros = [int(x) for x in re.findall(r"\d+", v)]
    return numeros or None


def salto_de_version(instalada: str, disponible: str) -> tuple[str, int]:
    """(texto, clave): a mayor clave, mayor salto. «Mayor +1» = cambió la primera cifra."""
    a, b = numeros_de_version(instalada), numeros_de_version(disponible)
    if a is None or b is None:
        return "?", 0
    n = max(len(a), len(b))
    a, b = a + [0] * (n - len(a)), b + [0] * (n - len(b))
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            if y < x:       # la nueva parece menor: el programa cambió de esquema de versiones
                return "Formato distinto", 1
            nivel = min(i, 3)
            texto = f"{NIVELES_SALTO[nivel]} +{y - x}" if nivel < 3 else NIVELES_SALTO[3]
            return texto, (5 - nivel) * 1_000_000 + min(y - x, 999_999)
    return "Igual", 1


def evaluar_seguridad(datos: dict) -> dict:
    """Convierte lo reunido (App Installer, ajustes y orígenes de winget) en comprobaciones [(tipo, texto)]."""
    seg = {"winget": datos.get("Usado"), "version": (datos.get("Version") or "").strip(),
           "admin": bool(datos.get("Admin")), "prueba": bool(datos.get("Prueba")),
           "genuino": False, "hash_obligatorio": False, "origenes": {}, "comprobaciones": []}
    c = seg["comprobaciones"]
    if not datos.get("Winget") and not seg["prueba"]:
        c.append(("error", "winget no está instalado. Instala «App Installer» desde la Microsoft Store."))
        return seg

    # 1. winget original de Microsoft
    appx = datos.get("Appx") or {}
    microsoft = "O=Microsoft Corporation"
    motivos = []
    if not appx:
        motivos.append(datos.get("AppxError") or "no se encontró el paquete App Installer")
    else:
        if appx.get("Status") != "Ok":
            motivos.append(f"estado del paquete: {appx.get('Status')}")
        if appx.get("SignatureKind") not in ("Store", "System"):
            motivos.append(f"tipo de firma: {appx.get('SignatureKind')}")
        if microsoft not in (appx.get("Publisher") or ""):
            motivos.append("el editor no es Microsoft")
        if appx.get("Firma") != "Valid" or microsoft not in (appx.get("Firmante") or ""):
            motivos.append(f"firma de winget.exe: {appx.get('Firma')}")
    seg["genuino"] = not motivos
    if seg["genuino"]:
        c.append(("ok", f"winget {seg['version']} es el original: App Installer {appx.get('Version')} "
                        "firmado por Microsoft (firma válida)."))
    else:
        c.append(("error", "No se pudo confirmar que winget sea el original de Microsoft ("
                           + "; ".join(motivos) + "). No se actualizará nada."))
    if seg["prueba"]:
        c.append(("aviso", f"MODO PRUEBA: se está usando un winget simulado ({seg['winget']})."))

    # 2. Opciones de administrador de winget
    ajustes = {}
    try:
        ajustes = (json.loads(datos.get("Ajustes") or "{}").get("adminSettings") or {})
    except (ValueError, AttributeError):
        pass
    if ajustes.get("InstallerHashOverride") is False:
        seg["hash_obligatorio"] = True
        c.append(("ok", "Comprobación de SHA256 obligatoria: «InstallerHashOverride» está desactivado, "
                        "así que winget no instala nada cuyo SHA256 no coincida con el manifiesto."))
    elif ajustes.get("InstallerHashOverride") is True:
        c.append(("error", "«InstallerHashOverride» está ACTIVADO: se podría saltar la comprobación del SHA256. "
                           "Desactívalo (como administrador): winget settings --disable InstallerHashOverride"))
    else:
        c.append(("aviso", "No se pudo leer «InstallerHashOverride»; winget comprueba el SHA256 igual, "
                           "pero no se pudo confirmar que nadie lo haya desactivado."))
        seg["hash_obligatorio"] = True
    for clave, texto in (("LocalManifestFiles", "permite instalar desde manifiestos locales"),
                         ("BypassCertificatePinningForMicrosoftStore", "no fija el certificado de la Store"),
                         ("LocalArchiveMalwareScanOverride", "salta el análisis antivirus de los .zip")):
        if ajustes.get(clave) is True:
            c.append(("aviso", f"Opción de administrador «{clave}» activada: {texto}."))

    # 3. Orígenes
    for linea in datos.get("Origenes") or []:
        try:
            o = json.loads(linea)
        except ValueError:
            continue
        nombre = o.get("Name") or ""
        oficial = ORIGENES_OFICIALES.get(nombre)
        o["oficial"] = bool(oficial) and (o.get("Arg"), o.get("Identifier"), o.get("Type")) == oficial[:3]
        seg["origenes"][nombre] = o
    w = seg["origenes"].get("winget")
    if w and w["oficial"]:
        c.append(("ok", f"Origen «winget» oficial de Microsoft: {w.get('Arg')}"))
    elif w:
        c.append(("error", f"El origen «winget» NO es el oficial (apunta a {w.get('Arg')}). "
                           "Sus paquetes quedan para revisión manual."))
    else:
        c.append(("error", "No está configurado el origen oficial «winget»."))
    otros = []
    for nombre, o in seg["origenes"].items():
        if nombre == "winget":
            continue
        if o["oficial"]:
            otros.append(f"{nombre} ({ORIGENES_OFICIALES[nombre][3]})")
        else:
            c.append(("aviso", f"Origen de terceros «{nombre}» ({o.get('Arg')}): sus paquetes van a revisión manual."))
    if otros:
        c.append(("info", "Otros orígenes oficiales: " + ", ".join(otros) + "."))

    # 4. Permisos
    if seg["admin"]:
        c.append(("info", "La app corre como administrador: los instaladores no pedirán permiso."))
    else:
        c.append(("info", "Sin permisos de administrador: si un instalador los necesita, Windows mostrará "
                          "su aviso (UAC) y tendrás que aceptarlo."))
    return seg


def clasificar_paquete(p: dict, seg: dict) -> tuple[str, str]:
    """('lote' | 'manual', motivo). Solo va en lote lo verificable del origen oficial."""
    if p["id_cortado"]:
        return "manual", "winget recortó el Id en su salida: no se puede identificar con seguridad."
    origen = p["origen"]
    info = seg["origenes"].get(origen)
    if origen in ORIGENES_EN_LOTE:
        if info and info.get("oficial"):
            return "lote", ""
        return "manual", f"El origen «{origen}» no coincide con el oficial de Microsoft."
    if origen == "msstore" and info and info.get("oficial"):
        return "manual", ("Microsoft Store: la Store firma el paquete, pero su manifiesto no trae un "
                          "SHA256 que winget pueda comprobar.")
    return "manual", f"Origen de terceros «{origen}»: no es de Microsoft."


# ─── Ejecutor de PowerShell ─────────────────────────────────────────────────

class ResultadoProceso:
    def __init__(self, codigo: int, lineas: list[str], datos, arranco: bool, abortado: bool, tiempo: bool):
        self.codigo, self.lineas, self.datos = codigo, lineas, datos
        self.arranco, self.abortado, self.tiempo_agotado = arranco, abortado, tiempo

    @property
    def texto(self) -> str:
        return "\n".join(self.lineas)


class ProcesoExterno(QObject):
    """
    Un programa a la vez (winget o PowerShell), sin trabar la interfaz. Se lanza desde un hilo:
    si un antivirus retiene el arranque (Avast lo hace a veces con programas sin firma), espera
    ese hilo y no la ventana. La salida llega línea a línea por señales, en orden.
    """
    linea = pyqtSignal(str)
    terminado = pyqtSignal(object, bool)        # código de salida, si llegó a arrancar
    _linea_hilo = pyqtSignal(int, str)          # (corrida, línea) desde el hilo
    _fin_hilo = pyqtSignal(int, object, bool)   # (corrida, código, arrancó) desde el hilo

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineas: list[str] = []
        self._corrida = 0                       # descarta señales atrasadas de una corrida anterior
        self._popen: subprocess.Popen | None = None
        self._hilo: threading.Thread | None = None
        self._matar_al_arrancar = False
        self._linea_hilo.connect(self._recibir_linea)
        self._fin_hilo.connect(self._recibir_fin)

    def activo(self) -> bool:
        return self._hilo is not None

    def iniciar(self, programa: str, args: list[str]):
        self._corrida += 1
        self.lineas = []
        self._popen = None
        self._matar_al_arrancar = False
        self._hilo = threading.Thread(target=self._trabajar, args=(self._corrida, programa, list(args)),
                                      daemon=True, name="proceso_externo")
        self._hilo.start()

    def _trabajar(self, corrida: int, programa: str, args: list[str]):
        try:
            proc = subprocess.Popen(linea_de_comando(programa, args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, creationflags=FLAGS_SIN_VENTANA)
        except OSError:
            self._fin_hilo.emit(corrida, 0xFFFFFFFF, False)
            return
        self._popen = proc
        if self._matar_al_arrancar:             # se canceló mientras arrancaba
            self._matar_arbol(proc.pid)
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        resto = ""
        while True:
            bloque = proc.stdout.read1(65536)
            if not bloque:
                break
            partes = (resto + decoder.decode(bloque)).split("\n")
            resto = partes.pop()
            for linea in partes:
                self._linea_hilo.emit(corrida, linea.rstrip("\r").lstrip("\ufeff"))
        resto += decoder.decode(b"", final=True)
        if resto.strip():
            self._linea_hilo.emit(corrida, resto.rstrip("\r").lstrip("\ufeff"))
        proc.stdout.close()
        self._fin_hilo.emit(corrida, proc.wait() & 0xFFFFFFFF, True)

    def _recibir_linea(self, corrida: int, linea: str):
        if corrida == self._corrida:
            self.lineas.append(linea)
            self.linea.emit(linea)

    def _recibir_fin(self, corrida: int, codigo, arranco: bool):
        if corrida != self._corrida:
            return
        self._hilo = self._popen = None
        self.terminado.emit(codigo, arranco)

    @staticmethod
    def _matar_arbol(pid: int):
        try:
            subprocess.Popen([TASKKILL, "/PID", str(pid), "/T", "/F"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=FLAGS_SIN_VENTANA)
        except OSError:
            pass

    def matar(self):
        """Termina el proceso y todo lo que lanzó (winget y el instalador)."""
        if self._hilo is None:
            return
        p = self._popen
        if p is None:
            self._matar_al_arrancar = True
            return
        self._matar_arbol(p.pid)

        def rematar():
            if p.poll() is None:
                try:
                    p.kill()
                except OSError:
                    pass
        QTimer.singleShot(3000, rematar)

    def esperar(self, ms: int):
        if self._hilo is not None:
            self._hilo.join(ms / 1000)


# ─── Página ─────────────────────────────────────────────────────────────────

MODOS_INSTALACION = [
    ("silencioso", "Silencioso (--silent)", ["--silent"]),
    ("normal", "Con la ventana de progreso del instalador", []),
    ("interactivo", "Interactivo: el instalador pregunta todo (--interactive)", ["--interactive"]),
]

DEFAULT_ACTUALIZAR = {
    "actualizar_origenes": True,
    "incluir_desconocidas": True,
    "incluir_ancladas": True,
    "mostrar_ignorados": False,
    "modo": "silencioso",
    "verificar_antes": True,
    "comprobar_firma": False,
    "omitir_sin_firma": False,
    "reanalizar": True,
    "detener_si_falla": False,
    "tiempo_max": 30,
    "guardar_reporte": True,
    "ignorados": [],
    "orden": 0,
}

COL_NOMBRE, COL_ID, COL_INSTALADA, COL_DISPONIBLE, COL_SALTO, COL_ORIGEN, COL_VERIF, COL_ESTADO = range(8)
COLUMNAS_ACTUALIZAR = ["NOMBRE", "ID", "INSTALADA", "DISPONIBLE", "SALTO", "ORIGEN", "VERIFICACIÓN", "ESTADO"]
COLUMNAS_MANUAL = ["NOMBRE", "ID", "INSTALADA", "DISPONIBLE", "ORIGEN", "MOTIVO"]
ORDENES_ACTUALIZAR = [
    ("Nombre (A → Z)", COL_NOMBRE, Qt.SortOrder.AscendingOrder),
    ("Nombre (Z → A)", COL_NOMBRE, Qt.SortOrder.DescendingOrder),
    ("Mayor salto de versión primero", COL_SALTO, Qt.SortOrder.DescendingOrder),
    ("Menor salto de versión primero", COL_SALTO, Qt.SortOrder.AscendingOrder),
    ("Id (A → Z)", COL_ID, Qt.SortOrder.AscendingOrder),
    ("Origen", COL_ORIGEN, Qt.SortOrder.AscendingOrder),
    ("Estado", COL_ESTADO, Qt.SortOrder.AscendingOrder),
]
ROL_CLAVE = Qt.ItemDataRole.UserRole
ROL_ORDEN = Qt.ItemDataRole.UserRole + 1
ICONOS_TIPO = {"ok": "✓", "aviso": "⚠", "error": "✗", "info": "•", "reinicio": "⟳", "sin_firma": "⚠",
               "omitido": "↷", "cancelado": "■", "pendiente": "…"}
ORDEN_ESTADOS = {"error": 0, "aviso": 1, "sin_firma": 1, "reinicio": 2, "cancelado": 3, "omitido": 4,
                 "info": 5, "pendiente": 6, "ok": 7}


def color_de(tipo: str | None) -> QColor | None:
    color = {"ok": "ok", "reinicio": "ok", "aviso": "aviso", "sin_firma": "aviso", "error": "error",
             "cancelado": "aviso", "omitido": "suave", "info": "titulo"}.get(tipo or "")
    return QColor(COLOR_LOG[color]) if color else None


class PestanasAjustadas(QTabWidget):
    """QTabWidget que mide solo la pestaña visible: no deja un hueco del alto de la más grande."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(lambda *_: self.updateGeometry())

    def _medida(self, base: QSize, pagina: QSize) -> QSize:
        return QSize(base.width(), self.tabBar().sizeHint().height() + pagina.height())

    def sizeHint(self) -> QSize:
        w = self.currentWidget()
        return self._medida(super().sizeHint(), w.sizeHint()) if w is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        w = self.currentWidget()
        if w is None:
            return super().minimumSizeHint()
        return self._medida(super().minimumSizeHint(), w.minimumSizeHint().expandedTo(w.minimumSize()))


class ItemOrden(QTableWidgetItem):
    """Celda que ordena por su clave (ROL_ORDEN) en vez de por el texto."""

    def __lt__(self, otro):
        a, b = self.data(ROL_ORDEN), otro.data(ROL_ORDEN)
        if a is not None and b is not None:
            try:
                return a < b
            except TypeError:
                pass
        return self.text().lower() < otro.text().lower()


def tabla_paquetes(columnas: list[str], estirar: int) -> QTableWidget:
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(30)
    t.setAlternatingRowColors(True)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setWordWrap(False)
    t.setTextElideMode(Qt.TextElideMode.ElideRight)
    cab = t.horizontalHeader()
    for i in range(len(columnas)):
        cab.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
    cab.setSectionResizeMode(estirar, QHeaderView.ResizeMode.Stretch)
    cab.setSortIndicatorShown(True)
    cab.setSectionsClickable(True)
    return t


def fuente_mono() -> QFont:
    f = QFont(elegir_fuente(FUENTES_MONO))
    f.setPixelSize(TXT_LABEL_MD)
    return f


def version_visible(v: str | None) -> str:
    return "desconocida" if not v or v == "Unknown" else v


class DialogoTexto(QDialog):
    """
    Ventana con un texto largo (licencia, salida de winget) y botones de copiar/guardar.
    datos: filas (ETIQUETA, valor[, clase]) que se muestran arriba como ficha.
    ajustar_ancho: la ventana toma el ancho justo del texto (hasta 100 columnas).
    """

    def __init__(self, parent, titulo: str, subtitulo: str = "", texto: str = "",
                 nombre_archivo: str | None = None, datos: list | None = None,
                 titulo_texto: str | None = None, ajustar_ancho: bool = False):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self._texto, self._nombre = texto, nombre_archivo
        v = QVBoxLayout(self)
        v.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        v.setSpacing(SPACING_MD)
        cab = QVBoxLayout()
        cab.setSpacing(SPACING_XS)
        t = QLabel(titulo)
        t.setProperty("class", "titulo-pagina")
        cab.addWidget(t)
        if subtitulo:
            s = etiqueta(subtitulo, "suave")
            s.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            cab.addWidget(s)
        v.addLayout(cab)
        if datos:
            ficha = QFrame()
            ficha.setProperty("class", "dato-reporte")
            g = grid_opciones()
            g.setContentsMargins(SPACING_MD, SPACING_SM + SPACING_XS, SPACING_MD, SPACING_SM + SPACING_XS)
            ficha.setLayout(g)
            for i, (nombre, valor, *clase) in enumerate(datos):
                g.addWidget(etiqueta(nombre), i, 0, Qt.AlignmentFlag.AlignTop)
                lbl = QLabel(valor)
                lbl.setWordWrap(True)
                lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                if clase and clase[0]:
                    lbl.setProperty("class", clase[0])
                g.addWidget(lbl, i, 1)
            v.addWidget(ficha)
        if titulo_texto:
            v.addWidget(etiqueta(titulo_texto))
        caja = QPlainTextEdit()
        caja.setObjectName("consola")
        caja.setReadOnly(True)
        caja.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        caja.setPlainText(texto)
        v.addWidget(caja, 1)
        fila = QHBoxLayout()
        fila.setSpacing(SPACING_SM)
        b = boton("Copiar")
        b.clicked.connect(lambda: QApplication.clipboard().setText(self._texto))
        fila.addWidget(b)
        if nombre_archivo:
            b = boton("Guardar como…")
            b.clicked.connect(self._guardar)
            fila.addWidget(b)
        fila.addStretch(1)
        b = boton("Cerrar", "primario")
        b.clicked.connect(self.accept)
        fila.addWidget(b)
        v.addLayout(fila)
        self._dimensionar(texto, ajustar_ancho, con_ficha=bool(datos))

    def _dimensionar(self, texto: str, ajustar_ancho: bool, con_ficha: bool):
        padre = self.parentWidget()
        pantalla = ((padre.screen() if padre is not None else None) or QApplication.primaryScreen()).availableGeometry()
        ancho, alto = 920, (720 if con_ficha else 640)
        if ajustar_ancho:
            # Ancho del renglón más largo (la licencia GPL tiene ~78 columnas) + márgenes y barra
            columnas = max((len(x.expandtabs(8)) for x in texto.splitlines()), default=60)
            columnas = min(max(columnas, 60), 100)
            ancho = (QFontMetrics(fuente_mono()).horizontalAdvance("0" * columnas)
                     + 2 * SPACING_LG + 2 * SPACING_SM + 44)
            alto = int(pantalla.height() * 0.85)
        self.resize(min(ancho, int(pantalla.width() * 0.95)), min(alto, int(pantalla.height() * 0.9)))

    def _guardar(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar", str(CARPETA_REGISTROS / self._nombre),
                                              "Texto (*.txt);;Todos (*)")
        if ruta:
            try:
                Path(ruta).write_text(self._texto, encoding="utf-8")
            except OSError as e:
                QMessageBox.warning(self, APP_NOMBRE, f"No se pudo guardar: {e}")


# Resultados que se pueden volver a intentar desde el reporte
TIPOS_REINTENTABLES = ("error", "cancelado", "omitido")
# Fallos que se arreglan cerrando el programa
CODIGOS_PROGRAMA_ABIERTO = (0x8A150101, 0x8A150103, 0x8A150111)


class DialogoReporte(QDialog):
    """Reporte al terminar de actualizar: cifras de lo que salió bien o mal y el detalle de cada programa."""

    CIFRAS = [("ok", "Actualizados"), ("reinicio", "Piden reiniciar"), ("aviso", "Con avisos"),
              ("error", "Fallaron"), ("omitido", "Omitidos"), ("cancelado", "Cancelados")]

    def __init__(self, pagina, reporte: dict):
        super().__init__(pagina)
        self.pagina, self.reporte = pagina, reporte
        self.setWindowTitle(f"Reporte de actualizaciones · {APP_NOMBRE}")
        filas = [reporte["filas"][c] for c in reporte["orden"]]
        cuenta = defaultdict(int)
        for f in filas:
            cuenta[f["tipo"]] += 1

        v = QVBoxLayout(self)
        v.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        v.setSpacing(SPACING_MD)

        # ─── Cabecera ───
        cab = QHBoxLayout()
        cab.setSpacing(SPACING_MD)
        textos = QVBoxLayout()
        textos.setSpacing(SPACING_XS)
        t = QLabel("Reporte de actualizaciones")
        t.setProperty("class", "titulo-pagina")
        textos.addWidget(t)
        textos.addWidget(etiqueta(self._cuando(), "suave"))
        cab.addLayout(textos, 1)
        if cuenta["error"]:
            texto, clase = f"✗ {cuenta['error']} con fallo", "chip-error"
        elif cuenta["cancelado"] or cuenta["omitido"] or cuenta["aviso"]:
            texto, clase = "⚠ Revisa los avisos", "chip-aviso"
        else:
            texto, clase = "✓ Todo salió bien", "chip-ok"
        chip = QLabel(texto)
        chip.setProperty("class", clase)
        cab.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(cab)

        # ─── Cifras ───
        cifras = QHBoxLayout()
        cifras.setSpacing(SPACING_SM)
        cifras.addWidget(self._cifra(len(filas), "Programas", None), 1)
        for tipo, nombre in self.CIFRAS:
            if cuenta[tipo]:
                cifras.addWidget(self._cifra(cuenta[tipo], nombre, tipo), 1)
        v.addLayout(cifras)

        # ─── Detalle por programa ───
        columnas = ["", "PROGRAMA", "ANTES", "DESPUÉS", "SEGURIDAD", "RESULTADO"]
        tabla = tabla_paquetes(columnas, len(columnas) - 1)
        tabla.verticalHeader().setDefaultSectionSize(36)
        tabla.horizontalHeader().setSortIndicatorShown(False)
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        for col, ancho in ((0, 40), (1, 220), (2, 110), (3, 110), (4, 170)):
            tabla.setColumnWidth(col, ancho)
        for f in filas:
            self._agregar_fila(tabla, f)
        tabla.setWordWrap(True)
        self.tabla = tabla
        PaginaActualizar._ajustar_alto(tabla, min_filas=1, max_filas=10)
        v.addWidget(tabla)

        pistas = []
        if any(f.get("codigo") in CODIGOS_PROGRAMA_ABIERTO for f in filas):
            pistas.append("Algunos fallaron porque el programa estaba abierto: ciérralo y pulsa «Reintentar».")
        if any(f.get("ubicacion") for f in filas):
            pistas.append("A los que pedían la carpeta de instalación se les pasó la que ya tenían (--location).")
        if cuenta["reinicio"]:
            pistas.append("Reinicia el equipo para terminar las actualizaciones marcadas con ⟳.")
        if pistas:
            caja = QVBoxLayout()
            caja.setSpacing(SPACING_XS)
            for texto in pistas:
                caja.addWidget(etiqueta("• " + texto, "suave"))
            v.addLayout(caja)
        v.addStretch(1)

        # ─── Pie ───
        if reporte.get("archivo"):
            fila = QHBoxLayout()
            fila.setSpacing(SPACING_SM)
            lbl = QLabel(f"Guardado en registros\\{Path(reporte['archivo']).name}")
            lbl.setProperty("class", "suave")
            lbl.setToolTip(reporte["archivo"])
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            fila.addWidget(lbl, 1)
            b = boton("Abrir carpeta", "fantasma")
            b.clicked.connect(lambda: abrir_en_sistema(Path(reporte["archivo"]).parent))
            fila.addWidget(b)
            v.addLayout(fila)
        botones = QHBoxLayout()
        botones.setSpacing(SPACING_SM)
        b = boton("Copiar texto", tooltip="El mismo reporte en texto, para pegarlo donde quieras")
        b.clicked.connect(lambda: QApplication.clipboard().setText(pagina._texto_reporte(reporte)))
        botones.addWidget(b)
        b = boton("Guardar como…")
        b.clicked.connect(self._guardar)
        botones.addWidget(b)
        botones.addStretch(1)
        self._pendientes = self._ids_pendientes()
        if self._pendientes:
            b = boton(f"Reintentar ({len(self._pendientes)})",
                      tooltip="Vuelve a intentar los que fallaron, se cancelaron o se omitieron "
                              "(pide confirmación antes)")
            b.clicked.connect(self._reintentar)
            botones.addWidget(b)
        b = boton("Cerrar", "primario")
        b.clicked.connect(self.accept)
        botones.addWidget(b)
        v.addLayout(botones)

        area = (pagina.screen() or QApplication.primaryScreen()).availableGeometry()
        self.resize(min(1060, int(area.width() * 0.95)), min(self.sizeHint().height() + 20, int(area.height() * 0.9)))

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._primer_ajuste)

    def _primer_ajuste(self):
        """Ya con el ancho real: filas a su medida y la ventana del alto justo."""
        self._ajustar_filas()
        area = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        self.resize(self.width(), min(self.sizeHint().height(), int(area.height() * 0.9)))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.isVisible():
            self._ajustar_filas()

    def _ajustar_filas(self):
        """Filas del alto justo de su texto (el resultado puede ocupar dos líneas)."""
        t = self.tabla
        t.resizeRowsToContents()
        alto = t.horizontalHeader().sizeHint().height() + 2 * t.frameWidth() + 4
        for r in range(t.rowCount()):
            t.setRowHeight(r, max(t.rowHeight(r) + SPACING_SM, 36))
            if r < 10:
                alto += t.rowHeight(r)
        t.setFixedHeight(alto)

    def _cuando(self) -> str:
        r = self.reporte
        try:
            inicio = time.mktime(time.strptime(r["inicio"], "%Y-%m-%d %H:%M:%S"))
            fin = time.mktime(time.strptime(r.get("fin") or r["inicio"], "%Y-%m-%d %H:%M:%S"))
        except (KeyError, ValueError):
            return r.get("inicio", "")
        return (f"{time.strftime('%d/%m/%Y', time.localtime(inicio))} · de "
                f"{time.strftime('%H:%M', time.localtime(inicio))} a {time.strftime('%H:%M', time.localtime(fin))}"
                f" ({formatear_duracion(fin - inicio)})")

    @staticmethod
    def _cifra(numero: int, nombre: str, tipo: str | None) -> QFrame:
        marco = QFrame()
        marco.setProperty("class", "dato-reporte")
        lay = QVBoxLayout(marco)
        lay.setContentsMargins(SPACING_MD, SPACING_SM + SPACING_XS, SPACING_MD, SPACING_SM + SPACING_XS)
        lay.setSpacing(0)
        n = QLabel(str(numero))
        n.setProperty("class", "numero-reporte")
        color = color_de(tipo)
        if color is not None:
            n.setStyleSheet(f"color: {color.name()};")
        lay.addWidget(n)
        texto = etiqueta(nombre.upper())
        texto.setWordWrap(False)
        lay.addWidget(texto)
        return marco

    @staticmethod
    def _agregar_fila(tabla: QTableWidget, f: dict):
        r = tabla.rowCount()
        tabla.insertRow(r)
        color = color_de(f["tipo"])

        def celda(col: int, texto: str, color_texto: QColor | None = None, tip: str | None = None,
                  negrita: bool = False) -> QTableWidgetItem:
            it = QTableWidgetItem(texto)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if color_texto is not None:
                it.setForeground(color_texto)
            if negrita:
                fuente = it.font()
                fuente.setBold(True)
                it.setFont(fuente)
            it.setToolTip(tip or texto)
            tabla.setItem(r, col, it)
            return it

        icono = celda(0, ICONOS_TIPO.get(f["tipo"], "•"), color, negrita=True)
        icono.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        celda(1, f["nombre"], None, f"{f['nombre']}\n{f['id']} · origen {f['origen']}")
        antes = version_visible(f["antes"])
        despues = f["despues"] or "—"
        cambio = despues not in ("—", f["antes"], "(sin comprobar)", "ya no aparece", "desconocida")
        celda(2, antes)
        celda(3, version_visible(despues) if despues != "—" else despues,
              color_de("ok") if cambio else color_de("omitido"))
        if f.get("hash"):
            celda(4, "✓ SHA256 comprobado", color_de("ok"),
                  "winget comprobó el SHA256 del instalador antes de ejecutarlo")
        elif f.get("verificacion"):
            celda(4, "Manifiesto revisado", color_de("omitido"), f["verificacion"])
        else:
            celda(4, "—", color_de("omitido"))
        detalle = [f["texto"]]
        if f.get("verificacion"):
            detalle.append(f"Verificación: {f['verificacion']}")
        if f.get("ubicacion"):
            detalle.append(f"Carpeta de instalación: {f['ubicacion']}")
        if f.get("codigo"):
            detalle.append(f"Código de winget: {codigo_hex(f['codigo'])}")
        celda(5, f["texto"], color, "\n".join(detalle))

    def _ids_pendientes(self) -> list[str]:
        en_lista = {p["id"].lower() for p in self.pagina._paquetes.values() if p["grupo"] == "lote"}
        filas = [self.reporte["filas"][c] for c in self.reporte["orden"]]
        return [f["id"] for f in filas if f["tipo"] in TIPOS_REINTENTABLES and f["id"].lower() in en_lista]

    def _reintentar(self):
        ids = list(self._pendientes)
        self.accept()
        QTimer.singleShot(0, lambda: self.pagina.reintentar(ids))

    def _guardar(self):
        nombre = (Path(self.reporte["archivo"]).name if self.reporte.get("archivo")
                  else time.strftime("actualizaciones_%Y-%m-%d.txt"))
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar", str(CARPETA_REGISTROS / nombre),
                                              "Texto (*.txt);;Todos (*)")
        if ruta:
            try:
                Path(ruta).write_text(self.pagina._texto_reporte(self.reporte), encoding="utf-8")
            except OSError as e:
                QMessageBox.warning(self, APP_NOMBRE, f"No se pudo guardar: {e}")


class PaginaActualizar(QWidget):
    """
    Busca actualizaciones con winget, las muestra en una tabla (seleccionar, ordenar, filtrar),
    verifica cada paquete y lo actualiza uno por uno, con reporte final.
    """

    def __init__(self, ventana):
        super().__init__()
        self.setObjectName("pagina")
        self.ventana = ventana
        self.config: Config = ventana.config
        self.sec = self.config.seccion("actualizar")
        for clave, valor in DEFAULT_ACTUALIZAR.items():
            self.sec.setdefault(clave, copy.deepcopy(valor))
        self.sin_dialogos = False        # la autoprueba no puede esperar clics
        self.salio_bien = True

        self._seguridad: dict | None = None
        self._paquetes: dict[str, dict] = {}      # clave → paquete
        self._seleccion: set[str] = set()
        self._analizado = False
        self._origenes_actualizados = ""
        self._reporte: dict | None = None
        self._flujo = None
        self._al_terminar = None
        self._modo_flujo = ""
        self._abortado = self._detener = self._tiempo_agotado = False
        self._mostrar_salida = False
        self._datos_ps = None
        self._programa = ""
        self._en_curso: dict | None = None
        self._ordenando = False

        self._proceso = ProcesoExterno(self)
        self._proceso.linea.connect(self._linea_proceso)
        self._proceso.terminado.connect(self._proceso_terminado)
        self._limite = QTimer(self)
        self._limite.setSingleShot(True)
        self._limite.timeout.connect(self._limite_superado)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        # Toda la pestaña se desplaza hacia abajo; la barra de acciones queda fija abajo
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        contenido = QWidget()
        contenido.setObjectName("contenidoScroll")
        self.scroll.setWidget(contenido)
        raiz.addWidget(self.scroll, 1)
        cuerpo = QVBoxLayout(contenido)
        cuerpo.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_LG)
        cuerpo.setSpacing(SPACING_LG)

        # ─── Cabecera ───
        cab = QHBoxLayout()
        cab.setSpacing(SPACING_SM)
        textos = QVBoxLayout()
        textos.setSpacing(SPACING_XS)
        t = QLabel("Actualizaciones (winget)")
        t.setProperty("class", "titulo-pagina")
        textos.addWidget(t)
        textos.addWidget(etiqueta("Busca actualizaciones con winget, comprueba que cada instalador sea el original "
                                  "y actualiza solo los programas que elijas.", "suave"))
        cab.addLayout(textos, 1)
        cab.addSpacing(SPACING_SM)
        self.chip_seguridad = QLabel("Seguridad: sin revisar")
        self.chip_seguridad.setProperty("class", "chip-info")
        cab.addWidget(self.chip_seguridad, 0, Qt.AlignmentFlag.AlignVCenter)
        cab.addSpacing(SPACING_SM)
        self.btn_opciones = boton("Opciones", tooltip="Modo de instalación, verificación, firma digital, "
                                                      "paquetes ignorados…")
        self.btn_opciones.setObjectName("btnOpciones")
        self.btn_opciones.clicked.connect(self._abrir_opciones)
        cab.addWidget(self.btn_opciones, 0, Qt.AlignmentFlag.AlignVCenter)
        self.btn_analizar = boton("Buscar actualizaciones", "primario",
                                  "winget source update (si está activado) y winget upgrade")
        self.btn_analizar.clicked.connect(lambda: self.analizar())
        cab.addWidget(self.btn_analizar, 0, Qt.AlignmentFlag.AlignVCenter)
        cuerpo.addLayout(cab)

        # ─── Paquetes ───
        card, lay = tarjeta()
        lay.setSpacing(SPACING_MD)
        barra = QHBoxLayout()
        barra.setSpacing(SPACING_SM)
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar por nombre o Id…")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.textChanged.connect(lambda *_: self._filtrar())
        barra.addWidget(self.buscar, 3)
        barra.addSpacing(SPACING_SM)
        barra.addWidget(etiqueta("ORDEN"))
        self.combo_orden = ComboSinRueda()
        for texto, _, _ in ORDENES_ACTUALIZAR:
            self.combo_orden.addItem(texto)
        self.combo_orden.setCurrentIndex(min(max(int(self.sec.get("orden", 0)), 0), len(ORDENES_ACTUALIZAR) - 1))
        self.combo_orden.currentIndexChanged.connect(self._orden_elegido)
        barra.addWidget(self.combo_orden, 2)
        barra.addStretch(1)
        barra.addWidget(etiqueta("MARCAR"))
        self.btn_todas = boton("Todas", "fantasma", "Marca todos los paquetes visibles (también los marcados ⚠)")
        self.btn_recomendadas = boton("Recomendadas", "fantasma",
                                      "Marca solo los que tienen versión conocida y no están anclados")
        self.btn_ninguna = boton("Ninguna", "fantasma")
        self.btn_invertir = boton("Invertir", "fantasma")
        self.btn_todas.clicked.connect(lambda: self._marcar("todas"))
        self.btn_recomendadas.clicked.connect(lambda: self._marcar("recomendadas"))
        self.btn_ninguna.clicked.connect(lambda: self._marcar("ninguna"))
        self.btn_invertir.clicked.connect(lambda: self._marcar("invertir"))
        for b in (self.btn_todas, self.btn_recomendadas, self.btn_ninguna, self.btn_invertir):
            barra.addWidget(b)
        lay.addLayout(barra)

        # Antes de buscar (o si todo está al día) se ve un mensaje en vez de la tabla vacía
        self.vacio = QWidget()
        vv = QVBoxLayout(self.vacio)
        vv.setContentsMargins(SPACING_LG, SPACING_LG + SPACING_MD, SPACING_LG, SPACING_LG + SPACING_MD)
        vv.setSpacing(SPACING_SM)
        self.lbl_vacio_titulo = QLabel()
        self.lbl_vacio_titulo.setProperty("class", "titulo-card")
        self.lbl_vacio_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vv.addWidget(self.lbl_vacio_titulo)
        self.lbl_vacio = etiqueta("", "suave")
        self.lbl_vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vv.addWidget(self.lbl_vacio)
        lay.addWidget(self.vacio)

        self.pestanas = PestanasAjustadas()
        self.pestanas.setObjectName("pestanasPaquetes")
        self.pestanas.setDocumentMode(True)
        self.pestanas.tabBar().setDrawBase(False)
        self.tabla = tabla_paquetes(COLUMNAS_ACTUALIZAR, COL_ESTADO)
        self.tabla.itemChanged.connect(self._item_cambiado)
        self.tabla.itemDoubleClicked.connect(lambda it: self._detalles(self._clave_de_fila(self.tabla, it.row())))
        self.tabla.horizontalHeader().sectionClicked.connect(self._cabecera_clic)
        self.tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabla.customContextMenuRequested.connect(self._menu_tabla)
        for col, ancho in ((COL_NOMBRE, 220), (COL_ID, 170), (COL_INSTALADA, 110), (COL_DISPONIBLE, 110),
                           (COL_SALTO, 100), (COL_ORIGEN, 80), (COL_VERIF, 210)):
            self.tabla.setColumnWidth(col, ancho)
        self.pestanas.addTab(self.tabla, "Actualizables")

        manual = QWidget()
        vm = QVBoxLayout(manual)
        vm.setContentsMargins(0, SPACING_SM, 0, 0)
        vm.setSpacing(SPACING_SM)
        vm.addWidget(etiqueta("Estos paquetes no vienen del repositorio oficial de winget (o no se pudieron "
                              "identificar bien), así que NUNCA se actualizan junto con los demás. Revisa cada "
                              "uno y, si confías en él, actualízalo por separado.", "suave"))
        self.tabla_manual = tabla_paquetes(COLUMNAS_MANUAL, len(COLUMNAS_MANUAL) - 1)
        self.tabla_manual.itemSelectionChanged.connect(self._actualizar_botones)
        self.tabla_manual.itemDoubleClicked.connect(
            lambda it: self._detalles(self._clave_de_fila(self.tabla_manual, it.row())))
        for col, ancho in ((0, 220), (1, 190), (2, 100), (3, 100), (4, 90)):
            self.tabla_manual.setColumnWidth(col, ancho)
        vm.addWidget(self.tabla_manual)
        fila = QHBoxLayout()
        fila.setSpacing(SPACING_SM)
        self.btn_manual_detalles = boton("Ver detalles")
        self.btn_manual_detalles.clicked.connect(
            lambda: self._detalles(self._clave_seleccionada(self.tabla_manual)))
        self.btn_manual_actualizar = boton("Actualizar solo este…", tooltip="Pide confirmación antes de empezar")
        self.btn_manual_actualizar.clicked.connect(self._actualizar_manual)
        self.btn_manual_copiar = boton("Copiar comando", "fantasma")
        self.btn_manual_copiar.clicked.connect(self._copiar_comando_manual)
        for b in (self.btn_manual_detalles, self.btn_manual_actualizar, self.btn_manual_copiar):
            fila.addWidget(b)
        fila.addStretch(1)
        vm.addLayout(fila)
        self.pestanas.addTab(manual, "Revisión manual")
        lay.addWidget(self.pestanas)
        self.fila_resumen = QHBoxLayout()
        self.fila_resumen.setSpacing(SPACING_SM)
        lay.addLayout(self.fila_resumen)
        cuerpo.addWidget(card)

        # ─── Comandos ───
        card, lay = tarjeta()
        cab_c = QHBoxLayout()
        cab_c.addWidget(titulo_card("Comandos"))
        cab_c.addStretch(1)
        b = boton("Copiar comandos", "fantasma", "Copia todos los comandos para pegarlos en PowerShell")
        b.clicked.connect(lambda: QApplication.clipboard().setText(self._texto_comandos(completo=True)))
        cab_c.addWidget(b)
        lay.addLayout(cab_c)
        self.lbl_modo = etiqueta("", "suave")
        lay.addWidget(self.lbl_modo)
        self.lbl_comando = QLabel()
        self.lbl_comando.setProperty("class", "comando")
        self.lbl_comando.setWordWrap(True)
        self.lbl_comando.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl_comando)
        cuerpo.addWidget(card)

        # ─── Registro ───
        card, lay = tarjeta()
        cab_r = QHBoxLayout()
        cab_r.addWidget(titulo_card("Registro"))
        cab_r.addStretch(1)
        b = boton("Limpiar", "fantasma")
        cab_r.addWidget(b)
        lay.addLayout(cab_r)
        self.consola = Consola()
        self.consola.setMinimumHeight(300)
        b.clicked.connect(self.consola.limpiar)
        lay.addWidget(self.consola, 1)
        cuerpo.addWidget(card, 1)

        # ─── Seguridad ───
        card, lay = tarjeta()
        cab_s = QHBoxLayout()
        cab_s.addWidget(titulo_card("Seguridad"))
        cab_s.addStretch(1)
        self.btn_como = boton("¿Cómo se protege cada actualización?", "fantasma")
        self.btn_como.setCheckable(True)
        cab_s.addWidget(self.btn_como)
        lay.addLayout(cab_s)
        self.caja_seguridad = QVBoxLayout()
        self.caja_seguridad.setSpacing(SPACING_SM)
        lay.addLayout(self.caja_seguridad)
        como = etiqueta(
            "• winget descarga el instalador y calcula su SHA256; si no coincide con el del manifiesto oficial, "
            "lo rechaza y no lo ejecuta.\n"
            "• «Verificar» lee el manifiesto (winget show): muestra el SHA256 y desde qué sitio se descarga.\n"
            "• «Revisar la firma digital» (en Opciones) descarga el instalador aparte y comprueba con PowerShell "
            "quién lo firmó (Get-AuthenticodeSignature).\n"
            "• Lo de la Microsoft Store, de otros orígenes o mal identificado queda en «Revisión manual».", "suave")
        como.setVisible(False)
        self.btn_como.toggled.connect(como.setVisible)
        lay.addWidget(como)
        cuerpo.addWidget(card)
        self._mostrar_seguridad(None)

        # ─── Acciones (fijas abajo, siempre a la vista) ───
        barra_acciones = QFrame()
        barra_acciones.setObjectName("barraAcciones")
        acciones = QHBoxLayout(barra_acciones)
        acciones.setContentsMargins(SPACING_LG, SPACING_SM + SPACING_XS, SPACING_LG, SPACING_SM + SPACING_XS)
        acciones.setSpacing(SPACING_SM)
        self.btn_actualizar = boton("Actualizar seleccionadas", "primario")
        self.btn_actualizar.clicked.connect(self.actualizar_seleccionadas)
        self.btn_verificar = boton("Verificar selección",
                                   tooltip="winget show de cada paquete marcado (y su firma, si la opción está activa)")
        self.btn_verificar.clicked.connect(self.verificar_seleccion)
        self.btn_reporte = boton("Ver último reporte", "fantasma")
        self.btn_reporte.clicked.connect(self._ver_reporte)
        for b in (self.btn_actualizar, self.btn_verificar, self.btn_reporte):
            acciones.addWidget(b)
        acciones.addSpacing(SPACING_MD)
        progreso = QVBoxLayout()
        progreso.setSpacing(SPACING_XS)
        self.lbl_estado = QLabel("Listo.")
        self.lbl_estado.setProperty("class", "suave")
        self.lbl_estado.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        progreso.addWidget(self.lbl_estado)
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setRange(0, 1)
        self.barra.setValue(0)
        progreso.addWidget(self.barra)
        acciones.addLayout(progreso, 1)
        acciones.addSpacing(SPACING_MD)
        self.btn_detener = boton("Detener tras el actual", tooltip="Termina el paquete en curso y no sigue con los demás")
        self.btn_detener.clicked.connect(self.detener_tras_actual)
        self.btn_cancelar = boton("Cancelar ya", "peligro", "Corta también el paquete que se está instalando")
        self.btn_cancelar.clicked.connect(self._cancelar_confirmando)
        acciones.addWidget(self.btn_detener)
        acciones.addWidget(self.btn_cancelar)
        raiz.addWidget(barra_acciones)

        self._crear_opciones()

        # Opciones guardadas
        self.chk_origenes.setChecked(bool(self.sec["actualizar_origenes"]))
        self.chk_desconocidas.setChecked(bool(self.sec["incluir_desconocidas"]))
        self.chk_ancladas.setChecked(bool(self.sec["incluir_ancladas"]))
        self.chk_ignorados.setChecked(bool(self.sec["mostrar_ignorados"]))
        modos = [m for m, _, _ in MODOS_INSTALACION]
        self.combo_modo.setCurrentIndex(modos.index(self.sec["modo"]) if self.sec["modo"] in modos else 0)
        self.chk_verificar.setChecked(bool(self.sec["verificar_antes"]))
        self.chk_firma.setChecked(bool(self.sec["comprobar_firma"]))
        self.chk_sin_firma.setChecked(bool(self.sec["omitir_sin_firma"]))
        self.chk_reanalizar.setChecked(bool(self.sec["reanalizar"]))
        self.chk_detener.setChecked(bool(self.sec["detener_si_falla"]))
        self.sp_limite.setValue(int(self.sec["tiempo_max"]))
        self.chk_reporte.setChecked(bool(self.sec["guardar_reporte"]))
        self.lista_ignorados.establecer(self.sec.get("ignorados") or [])
        for sig in (self.chk_origenes.toggled, self.chk_desconocidas.toggled, self.chk_ancladas.toggled,
                    self.chk_ignorados.toggled, self.combo_modo.currentIndexChanged, self.chk_verificar.toggled,
                    self.chk_firma.toggled, self.chk_sin_firma.toggled, self.chk_reanalizar.toggled,
                    self.chk_detener.toggled, self.sp_limite.valueChanged, self.chk_reporte.toggled):
            sig.connect(self._opciones_cambiadas)
        self.lista_ignorados.cambiado.connect(self._ignorados_cambiados)
        self._opciones_cambiadas()
        self._ajustar_alto(self.tabla)
        self._ajustar_alto(self.tabla_manual)
        self._mostrar_vacio()
        self._actualizar_botones()
        if not ES_WINDOWS:
            self.consola.agregar("winget solo existe en Windows.", "aviso")

    # ─── interfaz común con las demás páginas ───
    def ocupada(self) -> bool:
        return self._flujo is not None

    def cancelar(self):
        """Al cerrar la ventana: corta ya (la ventana ya pidió confirmación)."""
        if self._flujo is not None:
            self._abortado = True
            self._proceso.matar()

    def esperar(self, ms: int = 3000):
        self._proceso.esperar(ms)

    def estado(self, texto: str):
        self.lbl_estado.setText(texto)

    def error(self, texto: str):
        if not self.sin_dialogos:
            QMessageBox.warning(self, APP_NOMBRE, texto)
        else:
            self.consola.agregar(texto, "aviso")

    # ─── opciones ───
    def _crear_opciones(self):
        """Las opciones avanzadas van en su propia ventana (botón «Opciones»): la pestaña queda despejada."""
        d = QDialog(self)
        d.setWindowTitle(f"Opciones de Actualizaciones · {APP_NOMBRE}")
        self.dlg_opciones = d
        v = QVBoxLayout(d)
        v.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        v.setSpacing(SPACING_MD)
        t = QLabel("Opciones de Actualizaciones")
        t.setProperty("class", "titulo-pagina")
        v.addWidget(t)
        v.addWidget(etiqueta("Se guardan al momento y se usan en la próxima búsqueda o actualización.", "suave"))

        def casilla(texto: str, ayuda: str) -> QCheckBox:
            c = QCheckBox(texto)
            c.setToolTip(ayuda)
            return c

        self.chk_origenes = casilla("Actualizar el catálogo antes de buscar",
                                    "winget source update: así aparecen las versiones más recientes")
        self.chk_desconocidas = casilla("Incluir los de versión desconocida (⚠)",
                                        "--include-unknown: winget no sabe qué versión tienes instalada. "
                                        "Salen marcados y sin seleccionar.")
        self.chk_ancladas = casilla("Incluir los anclados con winget pin (‖)",
                                    "--include-pinned: programas que anclaste para que no se actualicen. "
                                    "Salen marcados y sin seleccionar.")
        self.chk_ignorados = casilla("Mostrar también los ignorados (⊘)",
                                     "Los de la lista «Paquetes ignorados» salen marcados en la tabla")
        self.combo_modo = ComboSinRueda()
        for _, texto, _ in MODOS_INSTALACION:
            self.combo_modo.addItem(texto)
        self.chk_verificar = casilla("Verificar cada paquete antes de instalarlo",
                                     "winget show: comprueba que el manifiesto tenga SHA256 y de qué sitio se descarga")
        self.chk_firma = casilla("Revisar la firma digital del instalador (más lento)",
                                 "Lo descarga antes a una carpeta temporal y revisa quién lo firmó con PowerShell")
        self.chk_sin_firma = casilla("No instalar los que no tengan firma digital",
                                     "Si el instalador no está firmado, se omite")
        self.chk_detener = casilla("Detener todo si una actualización falla",
                                   "Los que falten quedan como «omitidos» en el reporte")
        self.sp_limite = SpinSinRueda()
        self.sp_limite.setRange(0, 600)
        self.sp_limite.setSuffix(" min")
        self.sp_limite.setSpecialValueText("Sin límite")
        self.sp_limite.setToolTip("Si un instalador se queda colgado más tiempo, se cancela y se sigue con el siguiente")
        self.chk_reanalizar = casilla("Volver a buscar para comprobar las versiones",
                                      "Así el reporte dice qué versión quedó instalada de verdad")
        self.chk_reporte = casilla("Guardar el reporte en la carpeta «registros»",
                                   str(CARPETA_REGISTROS))
        self.lista_ignorados = ListaEditable(
            "PAQUETES IGNORADOS (Id)", "No se muestran ni se actualizan. También: clic derecho en un paquete → Ignorar.",
            "Agregar Id, ej. Mozilla.Firefox")
        self.lista_ignorados.lista.setMaximumHeight(140)

        rejilla = QGridLayout()
        rejilla.setSpacing(SPACING_MD)
        card, lay = tarjeta("Al buscar")
        for c in (self.chk_origenes, self.chk_desconocidas, self.chk_ancladas, self.chk_ignorados):
            lay.addWidget(c)
        lay.addStretch(1)
        rejilla.addWidget(card, 0, 0)
        card, lay = tarjeta("Al terminar")
        for c in (self.chk_reanalizar, self.chk_reporte):
            lay.addWidget(c)
        lay.addStretch(1)
        rejilla.addWidget(card, 0, 1)
        card, lay = tarjeta("Al actualizar")
        lay.addWidget(etiqueta("MODO DE INSTALACIÓN"))
        lay.addWidget(self.combo_modo)
        lay.addSpacing(SPACING_XS)
        lay.addWidget(self.chk_verificar)
        lay.addWidget(self.chk_firma)
        sangria = QHBoxLayout()
        sangria.addSpacing(SPACING_LG + SPACING_XS)
        sangria.addWidget(self.chk_sin_firma, 1)
        lay.addLayout(sangria)
        lay.addWidget(self.chk_detener)
        lay.addSpacing(SPACING_XS)
        fila = QHBoxLayout()
        fila.addWidget(etiqueta("TIEMPO MÁXIMO POR PAQUETE"), 1)
        fila.addWidget(self.sp_limite)
        lay.addLayout(fila)
        lay.addStretch(1)
        rejilla.addWidget(card, 1, 0)
        card, lay = tarjeta()
        lay.addWidget(self.lista_ignorados)
        lay.addStretch(1)
        rejilla.addWidget(card, 1, 1)
        rejilla.setColumnStretch(0, 1)
        rejilla.setColumnStretch(1, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        contenido = QWidget()
        contenido.setObjectName("contenidoScroll")
        contenido.setLayout(rejilla)
        rejilla.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(contenido)
        v.addWidget(scroll, 1)

        botones = QHBoxLayout()
        b = boton("Restablecer", "fantasma", "Vuelve a las opciones de fábrica (la lista de ignorados no se toca)")
        b.clicked.connect(self._restablecer_opciones)
        botones.addWidget(b)
        botones.addStretch(1)
        b = boton("Listo", "primario")
        b.clicked.connect(d.accept)
        botones.addWidget(b)
        v.addLayout(botones)
        self._contenido_opciones = contenido

    def _abrir_opciones(self):
        if self._flujo is not None:
            return
        d = self.dlg_opciones
        if not d.property("dimensionado"):
            d.setProperty("dimensionado", True)
            pantalla = (self.screen() or QApplication.primaryScreen()).availableGeometry()
            alto = self._contenido_opciones.sizeHint().height() + 220
            d.resize(min(900, int(pantalla.width() * 0.9)), min(alto, int(pantalla.height() * 0.9)))
        if self.sin_dialogos:
            return
        d.exec()

    def _restablecer_opciones(self):
        o = DEFAULT_ACTUALIZAR
        self.chk_origenes.setChecked(o["actualizar_origenes"])
        self.chk_desconocidas.setChecked(o["incluir_desconocidas"])
        self.chk_ancladas.setChecked(o["incluir_ancladas"])
        self.chk_ignorados.setChecked(o["mostrar_ignorados"])
        self.combo_modo.setCurrentIndex([m for m, _, _ in MODOS_INSTALACION].index(o["modo"]))
        self.chk_verificar.setChecked(o["verificar_antes"])
        self.chk_firma.setChecked(o["comprobar_firma"])
        self.chk_sin_firma.setChecked(o["omitir_sin_firma"])
        self.chk_reanalizar.setChecked(o["reanalizar"])
        self.chk_detener.setChecked(o["detener_si_falla"])
        self.sp_limite.setValue(o["tiempo_max"])
        self.chk_reporte.setChecked(o["guardar_reporte"])

    def _resumen_opciones(self) -> str:
        """Cómo se van a ejecutar (va debajo de «Comandos»)."""
        o = self.opciones()
        modo = {"silencioso": "modo silencioso", "normal": "con la ventana del instalador",
                "interactivo": "modo interactivo"}.get(o["modo"], o["modo"])
        partes = ["Uno por uno, en el orden de la tabla", modo]
        if o["verificar_antes"]:
            partes.append("verifica el manifiesto antes")
        if o["comprobar_firma"]:
            partes.append("revisa la firma digital" + (" (omite los que no tengan)" if o["omitir_sin_firma"] else ""))
        partes.append(f"máx. {o['tiempo_max']} min por paquete" if o["tiempo_max"] else "sin límite de tiempo")
        if o["detener_si_falla"]:
            partes.append("se detiene si uno falla")
        return " · ".join(partes) + ". Se cambia en «Opciones»."

    def opciones(self) -> dict:
        return {
            "actualizar_origenes": self.chk_origenes.isChecked(),
            "incluir_desconocidas": self.chk_desconocidas.isChecked(),
            "incluir_ancladas": self.chk_ancladas.isChecked(),
            "mostrar_ignorados": self.chk_ignorados.isChecked(),
            "modo": MODOS_INSTALACION[max(self.combo_modo.currentIndex(), 0)][0],
            "verificar_antes": self.chk_verificar.isChecked(),
            "comprobar_firma": self.chk_firma.isChecked(),
            "omitir_sin_firma": self.chk_sin_firma.isChecked(),
            "reanalizar": self.chk_reanalizar.isChecked(),
            "detener_si_falla": self.chk_detener.isChecked(),
            "tiempo_max": self.sp_limite.value(),
            "guardar_reporte": self.chk_reporte.isChecked(),
        }

    def _opciones_cambiadas(self, *_):
        self.chk_sin_firma.setEnabled(self.chk_firma.isChecked())
        self.sec.update(self.opciones())
        self.config.guardar()
        if self._paquetes:
            self._llenar_tablas()      # mostrar u ocultar desconocidas / ancladas / ignoradas
        self.lbl_modo.setText(self._resumen_opciones())
        self._actualizar_comando()

    def _ignorados(self) -> set[str]:
        return {x.lower() for x in self.lista_ignorados.activos()}

    def _ignorados_cambiados(self):
        self.sec["ignorados"] = self.lista_ignorados.valores()
        self.config.guardar()
        if self._paquetes:
            self._llenar_tablas()

    def _orden_elegido(self, idx: int):
        self.sec["orden"] = idx
        self.config.guardar()
        self._aplicar_orden()

    # ─── argumentos de winget ───
    def _args_lista(self) -> list[str]:
        args = ["upgrade"]
        if self.chk_desconocidas.isChecked():
            args.append("--include-unknown")
        if self.chk_ancladas.isChecked():
            args.append("--include-pinned")
        return args + ["--accept-source-agreements", "--disable-interactivity"]

    @staticmethod
    def _args_show(p: dict) -> list[str]:
        return ["show", "--id", p["id"], "--exact", "--source", p["origen"], "--version", p["disponible"],
                "--accept-source-agreements", "--disable-interactivity"]

    def _args_actualizar(self, p: dict, opciones: dict | None = None, ubicacion: str | None = None) -> list[str]:
        opciones = opciones or self.opciones()
        args = ["upgrade", "--id", p["id"], "--exact", "--source", p["origen"]]
        if _parece_version(p["disponible"]) and p["disponible"] != "Unknown":
            args += ["--version", p["disponible"]]      # justo la versión que se revisó
        if ubicacion:
            args += ["--location", ubicacion]
        if p["desconocida"]:
            args.append("--include-unknown")
        if p["anclado"]:
            args.append("--include-pinned")
        modo = next((m for m in MODOS_INSTALACION if m[0] == opciones["modo"]), MODOS_INSTALACION[0])
        return args + modo[2] + ["--accept-package-agreements", "--accept-source-agreements",
                                 "--disable-interactivity"]

    # ─── lanzador de flujos (generadores que piden programas: winget o PowerShell) ───
    @staticmethod
    def _winget(winget: str, args: list[str], mostrar: bool, limite: float | None):
        return (*comando_winget(winget, args), mostrar, limite)

    @staticmethod
    def _powershell(script: str, limite: float | None):
        return (*comando_powershell(script), False, limite)

    def _iniciar_flujo(self, generador, modo: str, texto_estado: str, al_terminar=None):
        if self._flujo is not None:
            return
        self._flujo, self._modo_flujo, self._al_terminar = generador, modo, al_terminar
        self._abortado = self._detener = False
        self.salio_bien = True
        self._set_ocupado(True)
        self.estado(texto_estado)
        QTimer.singleShot(0, lambda: self._avanzar(None))

    def _avanzar(self, valor):
        if self._flujo is None:
            return
        try:
            programa, args, mostrar, limite = self._flujo.send(valor)
        except StopIteration:
            self._terminar_flujo()
            return
        except Exception as e:
            import traceback
            escribir_fallo(f"[Error en Actualizaciones]\n{traceback.format_exc()}")
            self.consola.agregar(f"Error interno: {type(e).__name__}: {e}", "error")
            self.salio_bien = False
            self._terminar_flujo()
            return
        self._mostrar_salida, self._programa = mostrar, programa
        self._datos_ps, self._tiempo_agotado = None, False
        if limite:
            self._limite.start(int(limite * 1000))
        self._proceso.iniciar(programa, args)

    def _proceso_terminado(self, codigo: int, arranco: bool):
        self._limite.stop()
        if self._mostrar_salida:
            self.consola.cerrar_linea()
        # La señal de Qt lo entrega como entero con signo: 0x8A150014 llega como -1978335212
        codigo &= 0xFFFFFFFF
        if not arranco:
            self.consola.agregar(f"No se pudo iniciar {self._programa}.", "error")
            codigo = 0xFFFFFFFF
        resultado = ResultadoProceso(codigo, list(self._proceso.lineas), self._datos_ps, arranco,
                                     self._abortado, self._tiempo_agotado)
        QTimer.singleShot(0, lambda: self._avanzar(resultado))

    def _limite_superado(self):
        self._tiempo_agotado = True
        self.consola.agregar("Se superó el tiempo máximo: se cancela este paso.", "aviso")
        self._proceso.matar()

    def _terminar_flujo(self):
        self._flujo = None
        self._en_curso = None
        if self._abortado:
            self.salio_bien = False
            self.estado("Cancelado.")
        self._set_ocupado(False)
        accion, self._al_terminar = self._al_terminar, None
        if accion is not None:
            QTimer.singleShot(0, accion)

    def _set_ocupado(self, ocupado: bool):
        if ocupado:
            self.barra.setRange(0, 0)
        else:
            self.barra.setRange(0, 1)
            self.barra.setValue(1 if self.salio_bien else 0)
        self._actualizar_botones()

    def detener_tras_actual(self):
        if self._flujo is not None:
            self._detener = True
            self.btn_detener.setEnabled(False)
            self.consola.agregar("Se detendrá al terminar el paquete actual.", "aviso")

    def _cancelar_confirmando(self):
        if self._flujo is None:
            return
        if self._en_curso is not None and not self.sin_dialogos:
            r = QMessageBox.question(
                self, APP_NOMBRE,
                f"Se está instalando «{self._en_curso['nombre']}». Cortarlo a la mitad puede dejar ese "
                "programa dañado.\n\n¿Cancelar ya? (Para no arriesgar, usa «Detener tras el actual»).")
            if r != QMessageBox.StandardButton.Yes:
                return
        self._abortado = True
        self.estado("Cancelando…")
        self._proceso.matar()

    # ─── salida de winget y de PowerShell ───
    def _linea_proceso(self, linea: str):
        if linea.startswith(MARCA_JSON):
            try:
                self._datos_ps = json.loads(linea[len(MARCA_JSON):])
            except ValueError:
                pass
            return
        if not self._mostrar_salida:
            return
        visible = linea.split("\r")[-1]            # lo que quedaría en pantalla tras los \r
        if RE_SOLO_GIRO.match(visible):
            return
        if "█" in visible or "▒" in visible:       # barra de progreso: al estado, no al registro
            m = RE_TAMANOS.search(visible)
            if m:
                self.estado(f"Descargando… {m.group(1)} de {m.group(2)}")
            return
        self.consola.alimentar(visible + "\n")
        if RE_HASH_OK.search(visible):
            self.consola.agregar("✓ SHA256 del instalador comprobado por winget: coincide con el manifiesto.", "ok")
            if self._en_curso is not None:
                self._en_curso["hash_winget"] = True

    # ─── flujos ───
    def analizar(self, actualizar_origenes: bool | None = None):
        if not ES_WINDOWS:
            self.error("winget solo existe en Windows.")
            return
        if actualizar_origenes is None:
            actualizar_origenes = self.chk_origenes.isChecked()
        self._iniciar_flujo(self._flujo_analizar(actualizar_origenes), "analizar", "Buscando actualizaciones…")

    def _flujo_analizar(self, actualizar_origenes: bool, reporte: dict | None = None):
        self.consola.agregar("Revisando que winget sea el original y sus orígenes oficiales…", "titulo")
        real = shutil.which("winget")
        prueba = os.environ.get("UTILIDADES_WINGET_PRUEBA")
        datos = {"Winget": real, "Usado": prueba or real, "Prueba": bool(prueba), "Admin": es_administrador()}
        r = yield self._powershell(SCRIPT_APPX, 120)
        if r.abortado:
            return
        if r.datos is None:
            datos["AppxError"] = "PowerShell no respondió al revisar la firma de winget (¿lo bloqueó el antivirus?)"
            for linea in r.lineas[-5:]:
                self.consola.agregar(linea, "suave")
        else:
            datos["Appx"] = r.datos
        if datos["Usado"]:
            for clave, args in (("Version", ["--version"]), ("Ajustes", ["settings", "export"]),
                                ("Origenes", ["source", "export"])):
                r = yield self._winget(datos["Usado"], args, False, 60)
                if r.abortado:
                    return
                datos[clave] = ([x for x in r.lineas if x.strip().startswith("{")] if clave == "Origenes"
                                else r.texto.strip())
        seg = evaluar_seguridad(datos)
        self._seguridad = seg
        self._mostrar_seguridad(seg)
        for tipo, texto in seg["comprobaciones"]:
            self.consola.agregar(f"{ICONOS_TIPO[tipo]} {texto}", tipo if tipo != "info" else "suave")
        if not seg["winget"]:
            self.salio_bien = False
            return
        w = seg["winget"]

        if actualizar_origenes:
            args = ["source", "update", "--disable-interactivity"]
            self.consola.agregar("▶ " + comando_visible(args), "titulo")
            self.estado("Actualizando los orígenes de winget…")
            r = yield self._winget(w, args, True, 600)
            if r.abortado:
                return
            if r.codigo == 0:
                self._origenes_actualizados = time.strftime("%H:%M")
                self.consola.agregar("Orígenes al día: el análisis usa el catálogo más reciente.", "ok")
            else:
                self.consola.agregar(f"No se pudieron actualizar los orígenes ({codigo_hex(r.codigo)}); "
                                     "se usará el catálogo que ya tenías.", "aviso")
            self._mostrar_seguridad(seg)

        args = self._args_lista()
        self.consola.agregar("▶ " + comando_visible(args), "titulo")
        self.estado("Buscando actualizaciones…")
        r = yield self._winget(w, args, True, 600)
        if r.abortado:
            return
        nombres = set(seg["origenes"])
        implicitos = [n for n, o in seg["origenes"].items() if not o.get("Explicit")]
        filas = parsear_lista_winget(r.texto, nombres, implicitos[0] if len(implicitos) == 1 else None)
        for linea in r.lineas:
            if any(linea.rstrip().endswith(": " + n) for n in nombres) and not RE_GUIONES_WINGET.match(linea):
                self.consola.agregar(f"Aviso de winget: {linea.strip()}", "aviso")

        anclados = ""
        if filas:
            r2 = yield self._winget(w, ["pin", "list", "--accept-source-agreements", "--disable-interactivity"],
                                    False, 120)
            if r2.abortado:
                return
            anclados = r2.texto
        self._cargar_paquetes(filas, anclados, seg)
        if not filas:
            if r.codigo in (0, 0x8A15002B):
                self.consola.agregar("✓ Todo al día: winget no encontró actualizaciones.", "ok")
            else:
                self.salio_bien = False
                self.consola.agregar(f"No se pudo leer la lista de winget ({codigo_hex(r.codigo)}). "
                                     "Revisa su salida arriba.", "error")
        else:
            lote = [p for p in self._paquetes.values() if p["grupo"] == "lote"]
            manual = [p for p in self._paquetes.values() if p["grupo"] == "manual"]
            marcados = [p for p in lote if p["desconocida"] or p["anclado"]]
            self.consola.agregar(f"{len(filas)} actualizaciones: {len(lote)} del repositorio oficial"
                                 + (f" ({len(marcados)} marcadas)" if marcados else "")
                                 + f", {len(manual)} para revisión manual.", "ok")
        if reporte is not None:
            self._completar_reporte(reporte)
        self.estado("Listo." if self.salio_bien else "Terminó con avisos.")

    def verificar_seleccion(self):
        claves = self._claves_marcadas()
        if not claves:
            self.error("Marca al menos un paquete.")
            return
        con_firma = self.chk_firma.isChecked()
        self._iniciar_flujo(self._flujo_verificar(claves, con_firma), "verificar", "Verificando…")

    def _flujo_verificar(self, claves: list[str], con_firma: bool):
        self.consola.agregar(f"Verificando {len(claves)} paquete(s)…", "titulo")
        for i, clave in enumerate(claves, 1):
            if self._abortado or self._detener:
                return
            p = self._paquetes.get(clave)
            if p is None:
                continue
            self.estado(f"Verificando {i} de {len(claves)}: {p['nombre']}")
            yield from self._pasos_verificar(p, con_firma, estricto=p["grupo"] == "lote")
        self.estado("Verificación terminada.")

    def _pasos_verificar(self, p: dict, con_firma: bool, estricto: bool):
        """Devuelve True si el paquete se puede instalar (con estricto=False, solo informa)."""
        w = self._seguridad["winget"]
        args = self._args_show(p)
        self.consola.agregar(f"🔍 {p['nombre']}: " + comando_visible(args), "suave")
        r = yield self._winget(w, args, False, 180)
        if r.abortado:
            return False
        info = parsear_show(r.texto, p["id"])
        v = p["verif"]
        v.update(info)
        v["show"] = r.texto
        v["tipo"], v["texto"] = evaluar_manifiesto(info, r.codigo, estricto)
        self.consola.agregar(f"{ICONOS_TIPO[v['tipo']]} {p['nombre']}: {v['texto']}"
                             + (f" · editor: {info['editor']}" if info.get("editor") else "")
                             + (f"\n   SHA256 {info['sha256']}\n   {info['url']}" if info.get("sha256") else ""),
                             v["tipo"])
        self._refrescar_fila(p)
        if v["tipo"] == "error":
            return False
        if con_firma and p["origen"] in ORIGENES_EN_LOTE:
            # winget comprueba el SHA256 al descargar; luego PowerShell revisa la firma y lo recalcula.
            # La carpeta temporal se borra siempre, aunque se cancele.
            carpeta = Path(tempfile.mkdtemp(prefix="utilidades_winget_"))
            firma = None
            try:
                args = ["download", "--id", p["id"], "--exact", "--source", p["origen"], "--version",
                        p["disponible"], "--download-directory", str(carpeta), "--accept-package-agreements",
                        "--accept-source-agreements", "--disable-interactivity"]
                self.consola.agregar(f"⬇ {p['nombre']}: " + comando_visible(args), "suave")
                self.estado(f"Descargando el instalador de {p['nombre']} para revisar su firma…")
                r = yield self._winget(w, args, True, 1800)
                if r.abortado or r.tiempo_agotado:
                    return False
                if r.codigo == 0:
                    archivos = [f for f in carpeta.rglob("*")
                                if f.is_file() and f.suffix.lower() not in (".yaml", ".yml")]
                    archivo = max(archivos, key=lambda f: f.stat().st_size, default=None)
                    if archivo is not None:
                        self.consola.agregar(f"🔏 {p['nombre']}: Get-AuthenticodeSignature y Get-FileHash "
                                             f"de «{archivo.name}»", "suave")
                        r2 = yield self._powershell(script_firma_archivo(str(archivo)), 300)
                        if r2.abortado:
                            return False
                        firma = dict(r2.datos or {"Estado": "SinRespuesta"}, Archivo=archivo.name,
                                     Bytes=archivo.stat().st_size)
            finally:
                shutil.rmtree(carpeta, ignore_errors=True)
            tipo, texto = evaluar_firma(firma, v.get("sha256"), r.codigo)
            v["firma"] = {"tipo": tipo, "texto": texto, "datos": firma}
            if tipo != "error":
                v["texto"] += f" · {texto}"
            else:
                v["texto"] = texto
            if tipo in ("error", "aviso", "sin_firma") and v["tipo"] == "ok":
                v["tipo"] = "error" if tipo == "error" else "aviso"
            self.consola.agregar(f"{ICONOS_TIPO[tipo]} {p['nombre']}: {texto}"
                                 + (f" (emitido por {nombre_del_certificado((firma or {}).get('Emisor'))})"
                                    if tipo == "ok" else ""), tipo if tipo != "sin_firma" else "aviso")
            self._refrescar_fila(p)
            if tipo == "error" or (tipo == "sin_firma" and self.chk_sin_firma.isChecked()):
                return False
        return True

    def actualizar_seleccionadas(self):
        if not self._seguridad or not self._seguridad.get("genuino"):
            self.error("No se pudo confirmar que winget sea el original de Microsoft: no se actualizará nada.")
            return
        if not self._seguridad.get("hash_obligatorio"):
            self.error("La comprobación de SHA256 de winget está desactivada (InstallerHashOverride). "
                       "Desactiva esa opción antes de actualizar en lote.")
            return
        claves = self._claves_marcadas()
        if not claves:
            self.error("Marca al menos un paquete.")
            return
        opciones = self.opciones()
        if not self.sin_dialogos:
            lineas = [f"• {self._paquetes[c]['nombre']}: {self._paquetes[c]['instalada']} → "
                      f"{self._paquetes[c]['disponible']}" for c in claves[:12]]
            if len(claves) > 12:
                lineas.append(f"… y {len(claves) - 12} más")
            r = QMessageBox.question(
                self, APP_NOMBRE,
                f"Se van a actualizar {len(claves)} programa(s), uno por uno:\n\n" + "\n".join(lineas)
                + "\n\nCierra esos programas antes de empezar. Algunos instaladores pueden pedir permiso "
                  "de administrador.\n\n¿Continuar?")
            if r != QMessageBox.StandardButton.Yes:
                return
        self._iniciar_flujo(self._flujo_actualizar(claves, opciones), "actualizar", "Actualizando…",
                            al_terminar=self._al_terminar_actualizacion)

    def _flujo_actualizar(self, claves: list[str], opciones: dict):
        w = self._seguridad["winget"]
        reporte = {"inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "orden": list(claves), "filas": {}}
        for c in claves:
            p = self._paquetes[c]
            reporte["filas"][c] = {"nombre": p["nombre"], "id": p["id"], "origen": p["origen"],
                                   "antes": p["instalada"], "objetivo": p["disponible"], "despues": "",
                                   "tipo": "pendiente", "texto": "No se ejecutó.", "codigo": None,
                                   "hash": False, "verificacion": ""}
            self._poner_estado(p, "pendiente", "En cola")
        self._reporte = reporte
        total = len(claves)
        for i, clave in enumerate(claves, 1):
            p = self._paquetes[clave]
            fila = reporte["filas"][clave]
            if self._abortado:
                break
            if self._detener:
                fila["tipo"], fila["texto"] = "omitido", "Detenido antes de empezar."
                self._poner_estado(p, "omitido", "Omitido (detenido)")
                continue
            self.barra.setRange(0, total)
            self.barra.setValue(i - 1)

            # 1. Verificación previa
            v = p["verif"]
            falta_firma = opciones["comprobar_firma"] and not v.get("firma") and p["origen"] in ORIGENES_EN_LOTE
            if (opciones["verificar_antes"] and v.get("tipo") is None) or falta_firma:
                self._poner_estado(p, "info", "Verificando…")
                self.estado(f"[{i}/{total}] Verificando {p['nombre']}…")
                ok = yield from self._pasos_verificar(p, opciones["comprobar_firma"], estricto=p["grupo"] == "lote")
                if self._abortado:
                    break
                if not ok:
                    fila["tipo"], fila["texto"] = "omitido", f"No pasó la verificación: {v.get('texto')}"
                    fila["verificacion"] = v.get("texto") or ""
                    self._poner_estado(p, "omitido", "Omitido: no pasó la verificación")
                    if opciones["detener_si_falla"]:
                        self._detener = True
                    continue
            elif v.get("tipo") == "error" and p["grupo"] == "lote":
                fila["tipo"], fila["texto"] = "omitido", f"No pasó la verificación: {v.get('texto')}"
                self._poner_estado(p, "omitido", "Omitido: no pasó la verificación")
                continue
            fila["verificacion"] = v.get("texto") or ""

            # 2. Actualización
            args = self._args_actualizar(p, opciones)
            self.consola.agregar(f"▶ [{i}/{total}] {p['nombre']}: {p['instalada']} → {p['disponible']}", "titulo")
            self.consola.agregar(comando_visible(args), "suave")
            self._poner_estado(p, "info", "Actualizando…")
            self.estado(f"[{i}/{total}] Actualizando {p['nombre']}…")
            p["hash_winget"] = False
            self._en_curso = p
            limite = opciones["tiempo_max"] * 60 if opciones["tiempo_max"] else None
            r = yield self._winget(w, args, True, limite)
            self._en_curso = None
            if r.codigo == 0x8A15005F and not (r.abortado or r.tiempo_agotado):
                # Algunos instaladores (ej. Battle.net) piden la carpeta: se usa en la que ya está instalado
                ubicacion = yield from self._ubicacion_instalada(w, p)
                if ubicacion and not self._abortado:
                    self.consola.agregar(f"winget pide la carpeta de instalación: se reintenta con la que ya "
                                         f"tiene ({ubicacion}).", "aviso")
                    args = self._args_actualizar(p, opciones, ubicacion)
                    self.consola.agregar(comando_visible(args), "suave")
                    fila["ubicacion"] = ubicacion
                    self._en_curso = p
                    r = yield self._winget(w, args, True, limite)
                    self._en_curso = None
            fila["hash"] = bool(p.get("hash_winget"))
            if r.tiempo_agotado:
                fila["tipo"], fila["texto"] = "error", f"Tiempo agotado ({opciones['tiempo_max']} min): se canceló."
            elif r.abortado:
                fila["tipo"], fila["texto"] = "cancelado", "Cancelado mientras se instalaba."
            else:
                tipo, texto = describir_codigo_winget(r.codigo)
                if tipo is None:        # código que no está en la tabla: se le pregunta a winget
                    r2 = yield self._winget(w, ["error", codigo_hex(r.codigo)], False, 60)
                    explicacion = [x.strip() for x in r2.lineas if x.strip()]
                    tipo = "error"
                    if len(explicacion) >= 2:
                        texto = f"{explicacion[1]} ({codigo_hex(r.codigo)})"
                fila["tipo"], fila["texto"], fila["codigo"] = tipo, texto, r.codigo
            self._poner_estado(p, fila["tipo"], fila["texto"])
            self.consola.agregar(f"{ICONOS_TIPO.get(fila['tipo'], '•')} {p['nombre']}: {fila['texto']}",
                                 {"ok": "ok", "reinicio": "ok", "error": "error"}.get(fila["tipo"], "aviso"))
            if fila["tipo"] == "error":
                self.salio_bien = False
                if opciones["detener_si_falla"]:
                    self._detener = True
                    self.consola.agregar("Se detiene: falló una actualización y la opción lo pide.", "aviso")
            if self._abortado:
                break
        for clave in claves:
            fila = reporte["filas"][clave]
            if fila["tipo"] == "pendiente":
                fila["tipo"], fila["texto"] = "cancelado", "Cancelado antes de empezar."
                if clave in self._paquetes:
                    self._poner_estado(self._paquetes[clave], "cancelado", "Cancelado")
        self.barra.setRange(0, 0)
        if opciones["reanalizar"] and not self._abortado:
            self.consola.agregar("Comprobando cómo quedaron las versiones…", "titulo")
            yield from self._flujo_analizar(False, reporte)
        else:
            self._completar_reporte(reporte, comprobado=False)
        reporte["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if opciones["guardar_reporte"]:
            self._guardar_reporte(reporte)

    def _ubicacion_instalada(self, w: str, p: dict):
        args = ["list", "--id", p["id"], "--exact", "--details", "--accept-source-agreements",
                "--disable-interactivity"]
        self.consola.agregar(comando_visible(args), "suave")
        r = yield self._winget(w, args, False, 120)
        if r.abortado:
            return None
        return leer_ubicacion_instalada(r.texto)

    def _al_terminar_actualizacion(self):
        if self._reporte:
            resumen = self._resumen_reporte(self._reporte)
            self.consola.agregar(f"Reporte: {resumen}", "titulo")
            self.estado(resumen)
            if not self.sin_dialogos:
                self._ver_reporte()

    def _actualizar_manual(self):
        clave = self._clave_seleccionada(self.tabla_manual)
        p = self._paquetes.get(clave or "")
        if p is None:
            return
        if not self._seguridad or not self._seguridad.get("genuino"):
            self.error("No se pudo confirmar que winget sea el original de Microsoft.")
            return
        if p["id_cortado"]:
            self.error("winget recortó el Id de este paquete: no se puede actualizar con seguridad desde aquí.")
            return
        comando = comando_visible(self._args_actualizar(p))
        if not self.sin_dialogos:
            r = QMessageBox.question(
                self, APP_NOMBRE,
                f"«{p['nombre']}» ({p['id']})\nOrigen: {p['origen']} · {p['instalada']} → {p['disponible']}\n\n"
                f"Motivo de la revisión manual:\n{p['motivo']}\n\nSe ejecutará:\n{comando}\n\n"
                "¿Confías en este paquete y quieres actualizarlo?")
            if r != QMessageBox.StandardButton.Yes:
                return
        opciones = self.opciones()
        opciones["verificar_antes"] = True
        self._iniciar_flujo(self._flujo_actualizar([clave], opciones), "actualizar", "Actualizando…",
                            al_terminar=self._al_terminar_actualizacion)

    def _detalles(self, clave: str | None):
        p = self._paquetes.get(clave or "")
        if p is None:
            return
        if p["verif"].get("show"):
            self._abrir_detalles(p)
        elif self._flujo is None and self._seguridad:
            def flujo():
                yield from self._pasos_verificar(p, False, estricto=False)
            self._iniciar_flujo(flujo(), "detalles", f"Leyendo el manifiesto de {p['nombre']}…",
                                al_terminar=lambda: self._abrir_detalles(p))

    def _dialogo_detalles(self, p: dict) -> DialogoTexto:
        v = p["verif"]
        oficial = (self._seguridad or {}).get("origenes", {}).get(p["origen"], {}).get("oficial")
        datos = [("ID", p["id"], "mono"),
                 ("ORIGEN", p["origen"] + (" (oficial de Microsoft)" if oficial else "")),
                 ("VERSIÓN", f"{version_visible(p['instalada'])}  →  {p['disponible']}")]
        if v.get("editor"):
            datos.append(("EDITOR", v["editor"]))
        if v.get("url"):
            datos.append(("INSTALADOR", v["url"], "mono"))
        if v.get("sha256"):
            datos.append(("SHA256", v["sha256"], "mono"))
        if v.get("tipo"):
            datos.append(("VERIFICACIÓN", f"{ICONOS_TIPO[v['tipo']]} {v['texto']}",
                          {"ok": "ok", "aviso": "aviso", "sin_firma": "aviso", "error": "error-texto"}.get(v["tipo"])))
        if p["grupo"] == "manual":
            datos.append(("REVISIÓN MANUAL", p["motivo"], "aviso"))
        return DialogoTexto(self, p["nombre"], "Datos del manifiesto oficial que winget va a usar.", v["show"],
                            datos=datos, titulo_texto="SALIDA COMPLETA DE WINGET SHOW")

    def _abrir_detalles(self, p: dict):
        if self.sin_dialogos or not p["verif"].get("show"):
            return
        self._dialogo_detalles(p).exec()

    # ─── modelo y tablas ───
    def _cargar_paquetes(self, filas: list[dict], anclados_texto: str, seg: dict):
        previos = self._paquetes
        nuevos: dict[str, dict] = {}
        for f in filas:
            clave = f"{f['id']}|{f['instalada']}".lower()
            if clave in nuevos:
                continue
            p = dict(f)
            p["clave"] = clave
            p["anclado"] = bool(re.search(r"(?<!\S)" + re.escape(f["id"]) + r"(?!\S)", anclados_texto))
            p["grupo"], p["motivo"] = clasificar_paquete(p, seg)
            p["salto"] = salto_de_version(p["instalada"], p["disponible"])
            anterior = previos.get(clave)
            p["verif"] = anterior["verif"] if anterior and anterior["disponible"] == p["disponible"] else {"tipo": None, "texto": ""}
            p["resultado"] = anterior.get("resultado") if anterior else None
            nuevos[clave] = p
        if not self._analizado:
            self._seleccion = {c for c, p in nuevos.items() if self._recomendado(p)}
        else:
            # Se conserva lo que marcaste; lo nuevo se marca según la recomendación
            self._seleccion = {c for c, p in nuevos.items()
                               if c in self._seleccion or (c not in previos and self._recomendado(p))}
        self._paquetes = nuevos
        self._analizado = True
        self.btn_analizar.setText("Volver a analizar")
        self._llenar_tablas()

    def _recomendado(self, p: dict) -> bool:
        return (p["grupo"] == "lote" and not p["desconocida"] and not p["anclado"]
                and p["id"].lower() not in self._ignorados())

    def _visible_en_lote(self, p: dict) -> bool:
        if p["grupo"] != "lote":
            return False
        if p["id"].lower() in self._ignorados() and not self.chk_ignorados.isChecked():
            return False
        return True

    def _llenar_tablas(self):
        ignorados = self._ignorados()
        t = self.tabla
        t.blockSignals(True)
        t.setRowCount(0)
        for p in self._paquetes.values():
            if not self._visible_en_lote(p):
                continue
            r = t.rowCount()
            t.insertRow(r)
            nombre = ItemOrden(p["nombre"])
            nombre.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
            nombre.setCheckState(Qt.CheckState.Checked if p["clave"] in self._seleccion else Qt.CheckState.Unchecked)
            nombre.setData(ROL_CLAVE, p["clave"])
            nombre.setData(ROL_ORDEN, p["nombre"].lower())
            nombre.setToolTip(p["nombre"])
            t.setItem(r, COL_NOMBRE, nombre)
            self._celda(t, r, COL_ID, p["id"], p["id"].lower())
            self._celda(t, r, COL_INSTALADA, "desconocida" if p["desconocida"] else p["instalada"],
                        tuple(numeros_de_version(p["instalada"]) or ()),
                        "aviso" if p["desconocida"] else None,
                        "winget no puede leer la versión instalada: al actualizar instala la disponible"
                        if p["desconocida"] else None)
            self._celda(t, r, COL_DISPONIBLE, p["disponible"], tuple(numeros_de_version(p["disponible"]) or ()))
            self._celda(t, r, COL_SALTO, p["salto"][0], p["salto"][1],
                        "aviso" if p["salto"][0] in ("?", "Formato distinto") else None)
            oficial = (self._seguridad or {}).get("origenes", {}).get(p["origen"], {}).get("oficial")
            self._celda(t, r, COL_ORIGEN, p["origen"] + (" ✓" if oficial else ""), p["origen"],
                        None, ORIGENES_OFICIALES.get(p["origen"], ("", "", "", "origen"))[3])
            self._celda(t, r, COL_VERIF, "", 0)
            self._celda(t, r, COL_ESTADO, "", 0)
            self._pintar_fila(t, r, p, p["id"].lower() in ignorados)
        self._aplicar_orden()
        t.blockSignals(False)

        m = self.tabla_manual
        m.setRowCount(0)
        for p in self._paquetes.values():
            if p["grupo"] != "manual":
                continue
            r = m.rowCount()
            m.insertRow(r)
            nombre = ItemOrden(p["nombre"])
            nombre.setData(ROL_CLAVE, p["clave"])
            m.setItem(r, 0, nombre)
            self._celda(m, r, 1, p["id"], p["id"].lower(), "aviso" if p["id_cortado"] else None)
            self._celda(m, r, 2, "desconocida" if p["desconocida"] else p["instalada"], None,
                        "aviso" if p["desconocida"] else None)
            self._celda(m, r, 3, p["disponible"], None)
            self._celda(m, r, 4, p["origen"], None)
            self._celda(m, r, 5, p["motivo"], None, "aviso", p["motivo"])
        n_manual = m.rowCount()
        self.pestanas.setTabText(0, f"Actualizables ({t.rowCount()})")
        self.pestanas.setTabText(1, f"Revisión manual ({n_manual})")
        self._ajustar_alto(t)
        self._ajustar_alto(m)
        self._mostrar_vacio()
        self._filtrar()
        self._actualizar_resumen()
        self._actualizar_comando()
        self._actualizar_botones()

    @staticmethod
    def _celda(t: QTableWidget, r: int, col: int, texto: str, orden, tipo: str | None = None,
               tooltip: str | None = None):
        it = ItemOrden(texto)
        it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        if orden is not None:
            it.setData(ROL_ORDEN, orden)
        color = color_de(tipo)
        if color is not None:
            it.setForeground(color)
        it.setToolTip(tooltip or texto)
        t.setItem(r, col, it)

    def _pintar_fila(self, t: QTableWidget, r: int, p: dict, ignorado: bool):
        """Columnas de verificación y estado (con las marcas de desconocida/anclado/ignorado)."""
        v = p["verif"]
        it = t.item(r, COL_VERIF)
        if v.get("tipo"):
            it.setText(f"{ICONOS_TIPO[v['tipo']]} {v['texto']}")
            partes = [v["texto"]]
            if v.get("editor"):
                partes.append(f"Editor: {v['editor']}")
            if v.get("url"):
                partes.append(f"Instalador: {v['url']}")
            if v.get("sha256"):
                partes.append(f"SHA256: {v['sha256']}")
            it.setToolTip("\n".join(partes))
        else:
            it.setText("sin verificar")
            it.setToolTip("Se verifica al actualizar (o con «Verificar selección»).")
        it.setData(ROL_ORDEN, ORDEN_ESTADOS.get(v.get("tipo") or "pendiente", 6))
        color = color_de(v.get("tipo"))
        it.setForeground(color if color is not None else color_de("omitido"))

        estado = t.item(r, COL_ESTADO)
        res = p.get("resultado")
        if res:
            tipo, texto = res
        else:
            marcas = []
            if p["desconocida"]:
                marcas.append("⚠ versión desconocida")
            if p["anclado"]:
                marcas.append("‖ anclado (winget pin)")
            if p.get("explicito"):
                marcas.append("requiere actualización explícita")
            if ignorado:
                marcas.append("⊘ ignorado")
            tipo, texto = ("aviso", " · ".join(marcas)) if marcas else (None, "")
        estado.setText(texto if not res else f"{ICONOS_TIPO.get(tipo, '')} {texto}")
        estado.setToolTip(texto)
        estado.setData(ROL_ORDEN, ORDEN_ESTADOS.get(tipo or "pendiente", 6))
        color = color_de(tipo)
        estado.setForeground(color if color is not None else color_de("omitido"))

    def _fila_de(self, clave: str) -> int:
        for r in range(self.tabla.rowCount()):
            it = self.tabla.item(r, COL_NOMBRE)
            if it is not None and it.data(ROL_CLAVE) == clave:
                return r
        return -1

    def _refrescar_fila(self, p: dict):
        r = self._fila_de(p["clave"])
        if r >= 0:
            self.tabla.blockSignals(True)
            self._pintar_fila(self.tabla, r, p, p["id"].lower() in self._ignorados())
            self.tabla.blockSignals(False)

    def _poner_estado(self, p: dict, tipo: str, texto: str):
        p["resultado"] = (tipo, texto)
        self._refrescar_fila(p)

    @staticmethod
    def _clave_de_fila(t: QTableWidget, r: int) -> str | None:
        it = t.item(r, 0)
        return it.data(ROL_CLAVE) if it is not None else None

    def _clave_seleccionada(self, t: QTableWidget) -> str | None:
        filas = t.selectionModel().selectedRows()
        return self._clave_de_fila(t, filas[0].row()) if filas else None

    def _claves_marcadas(self) -> list[str]:
        """Las marcadas, en el orden en que se ven en la tabla."""
        claves = []
        for r in range(self.tabla.rowCount()):
            it = self.tabla.item(r, COL_NOMBRE)
            if it is not None and it.checkState() == Qt.CheckState.Checked:
                claves.append(it.data(ROL_CLAVE))
        return claves

    def _item_cambiado(self, it: QTableWidgetItem):
        if it.column() != COL_NOMBRE:
            return
        clave = it.data(ROL_CLAVE)
        marcado = it.checkState() == Qt.CheckState.Checked
        if self._flujo is not None:            # durante una operación no se cambia la selección
            self.tabla.blockSignals(True)
            it.setCheckState(Qt.CheckState.Checked if clave in self._seleccion else Qt.CheckState.Unchecked)
            self.tabla.blockSignals(False)
            return
        if marcado:
            self._seleccion.add(clave)
        else:
            self._seleccion.discard(clave)
        self._actualizar_resumen()
        self._actualizar_comando()
        self._actualizar_botones()

    def _marcar(self, como: str):
        if self._flujo is not None:
            return
        self.tabla.blockSignals(True)
        for r in range(self.tabla.rowCount()):
            if self.tabla.isRowHidden(r):
                continue
            it = self.tabla.item(r, COL_NOMBRE)
            clave = it.data(ROL_CLAVE)
            p = self._paquetes[clave]
            actual = it.checkState() == Qt.CheckState.Checked
            nuevo = {"todas": True, "ninguna": False, "invertir": not actual,
                     "recomendadas": self._recomendado(p)}[como]
            it.setCheckState(Qt.CheckState.Checked if nuevo else Qt.CheckState.Unchecked)
            (self._seleccion.add if nuevo else self._seleccion.discard)(clave)
        self.tabla.blockSignals(False)
        self._actualizar_resumen()
        self._actualizar_comando()
        self._actualizar_botones()

    def _filtrar(self):
        texto = self.buscar.text().strip().lower()
        for t in (self.tabla, self.tabla_manual):
            for r in range(t.rowCount()):
                nombre, id_ = t.item(r, 0), t.item(r, 1)
                visible = not texto or any(texto in (x.text().lower() if x else "") for x in (nombre, id_))
                t.setRowHidden(r, not visible)

    def _aplicar_orden(self):
        _, col, orden = ORDENES_ACTUALIZAR[max(self.combo_orden.currentIndex(), 0)]
        self.tabla.sortItems(col, orden)
        self.tabla.horizontalHeader().setSortIndicator(col, orden)
        self.tabla_manual.sortItems(0, Qt.SortOrder.AscendingOrder)
        self._actualizar_comando()

    def _cabecera_clic(self, col: int):
        cab = self.tabla.horizontalHeader()
        orden = cab.sortIndicatorOrder()
        self.tabla.sortItems(col, orden)
        self._actualizar_comando()

    def _menu_tabla(self, pos):
        it = self.tabla.itemAt(pos)
        if it is None:
            return
        clave = self._clave_de_fila(self.tabla, it.row())
        p = self._paquetes.get(clave)
        if p is None:
            return
        menu = QMenu(self)
        menu.addAction("Ver detalles (winget show)", lambda: self._detalles(clave))
        menu.addAction("Copiar comando", lambda: QApplication.clipboard().setText(
            comando_visible(self._args_actualizar(p))))
        menu.addAction("Copiar Id", lambda: QApplication.clipboard().setText(p["id"]))
        menu.addSeparator()
        if p["id"].lower() in self._ignorados():
            menu.addAction("Dejar de ignorar", lambda: self._ignorar(p["id"], False))
        else:
            menu.addAction("Ignorar este paquete", lambda: self._ignorar(p["id"], True))
        menu.exec(self.tabla.viewport().mapToGlobal(pos))

    def _ignorar(self, id_: str, ignorar: bool):
        valores = [v for v in self.lista_ignorados.valores() if v[0].lower() != id_.lower()]
        if ignorar:
            valores.append([id_, True])
            self._seleccion = {c for c in self._seleccion if not c.startswith(id_.lower() + "|")}
        self.lista_ignorados.establecer(valores)
        self._ignorados_cambiados()

    @staticmethod
    def _ajustar_alto(t: QTableWidget, min_filas: int = 5, max_filas: int = 14):
        """La tabla crece con los paquetes (hasta 14 filas; más allá tiene su propia barra)."""
        filas = min(max(t.rowCount(), min_filas), max_filas)
        alto = (t.horizontalHeader().sizeHint().height() + filas * t.verticalHeader().defaultSectionSize()
                + 2 * t.frameWidth() + 4)
        t.setFixedHeight(alto)

    def _mostrar_vacio(self):
        hay = bool(self._paquetes)
        self.pestanas.setVisible(hay)
        self.vacio.setVisible(not hay)
        if hay:
            return
        if not self._analizado:
            self.lbl_vacio_titulo.setText("Todavía no se ha buscado")
            self.lbl_vacio.setText("Pulsa «Buscar actualizaciones»: primero se revisa que winget sea el original "
                                   "de Microsoft y se actualiza su catálogo; luego verás aquí cada programa con "
                                   "la versión que tienes y la nueva.")
        else:
            self.lbl_vacio_titulo.setText("✓ Todo al día")
            self.lbl_vacio.setText("winget no encontró actualizaciones para tus programas.")

    def _poner_chips(self, chips: list[tuple[str, str]]):
        while self.fila_resumen.count():
            item = self.fila_resumen.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for texto, clase in chips:
            c = QLabel(texto)
            c.setProperty("class", clase)
            self.fila_resumen.addWidget(c)
        self.fila_resumen.addStretch(1)

    def _actualizar_resumen(self):
        if not self._analizado:
            self._poner_chips([])
            return
        lote = [p for p in self._paquetes.values() if p["grupo"] == "lote"]
        visibles = [p for p in lote if self._visible_en_lote(p)]
        ignorados = self._ignorados()
        n_ign = sum(1 for p in lote if p["id"].lower() in ignorados)
        marcados = sum(1 for p in visibles if p["desconocida"] or p["anclado"])
        manual = sum(1 for p in self._paquetes.values() if p["grupo"] == "manual")
        sel = len(self._claves_marcadas())
        chips = []
        if self._paquetes:
            chips = [(f"{len(visibles)} actualizables", "chip-info"), (f"{sel} seleccionadas", "chip-primario")]
            if marcados:
                chips.append((f"⚠ {marcados} marcadas", "chip-aviso"))
            if manual:
                chips.append((f"{manual} en revisión manual", "chip-aviso"))
            if n_ign:
                chips.append((f"⊘ {n_ign} ignoradas", "chip-info"))
        if self._origenes_actualizados:
            chips.append((f"✓ Catálogo actualizado a las {self._origenes_actualizados}", "chip-ok"))
        self._poner_chips(chips)

    def _texto_comandos(self, completo: bool = False) -> str:
        lineas = []
        if self.chk_origenes.isChecked():
            lineas.append("# Antes de analizar:")
            lineas.append(comando_visible(["source", "update", "--disable-interactivity"]))
            lineas.append(comando_visible(self._args_lista()))
        claves = self._claves_marcadas()
        if claves:
            opciones = self.opciones()
            lineas.append(f"# Actualizar {len(claves)} paquete(s), uno por uno:")
            if opciones["verificar_antes"]:
                lineas.append("#   (antes de cada uno: winget show --id <Id> --exact → SHA256 del manifiesto)")
            if opciones["comprobar_firma"]:
                lineas.append("#   (y winget download + Get-AuthenticodeSignature para revisar la firma)")
            limite = len(claves) if completo else 6
            for c in claves[:limite]:
                lineas.append(comando_visible(self._args_actualizar(self._paquetes[c], opciones)))
            if len(claves) > limite:
                lineas.append(f"# … y {len(claves) - limite} más («Copiar comandos» los copia todos)")
        elif self._analizado:
            lineas.append("# Marca los paquetes que quieras actualizar.")
        return "\n".join(lineas)

    def _actualizar_comando(self):
        self.lbl_comando.setText(self._texto_comandos() or comando_visible(self._args_lista()))

    def _actualizar_botones(self):
        libre = self._flujo is None
        seguro = bool(self._seguridad and self._seguridad.get("genuino"))
        marcadas = len(self._claves_marcadas()) if self._analizado else 0
        self.btn_analizar.setEnabled(libre and ES_WINDOWS)
        self.btn_opciones.setEnabled(libre)
        self.btn_actualizar.setEnabled(libre and seguro and marcadas > 0)
        self.btn_actualizar.setText(f"Actualizar seleccionadas ({marcadas})" if marcadas else "Actualizar seleccionadas")
        self.btn_verificar.setEnabled(libre and seguro and marcadas > 0)
        self.btn_reporte.setEnabled(libre and self._reporte is not None)
        for b in (self.btn_todas, self.btn_recomendadas, self.btn_ninguna, self.btn_invertir):
            b.setEnabled(libre and self._analizado)
        hay_manual = self._clave_seleccionada(self.tabla_manual) is not None
        self.btn_manual_detalles.setEnabled(libre and seguro and hay_manual)
        self.btn_manual_actualizar.setEnabled(libre and seguro and hay_manual)
        self.btn_manual_copiar.setEnabled(hay_manual)
        self.btn_detener.setEnabled(not libre and self._modo_flujo == "actualizar" and not self._detener)
        self.btn_cancelar.setEnabled(not libre)

    def _copiar_comando_manual(self):
        p = self._paquetes.get(self._clave_seleccionada(self.tabla_manual) or "")
        if p is not None:
            QApplication.clipboard().setText(comando_visible(self._args_actualizar(p)))

    def _mostrar_seguridad(self, seg: dict | None):
        while self.caja_seguridad.count():
            item = self.caja_seguridad.takeAt(0)
            if item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
            if item.widget():
                item.widget().deleteLater()
        if seg is None:
            self.caja_seguridad.addWidget(etiqueta("Se revisa al buscar actualizaciones.", "suave"))
            return
        comprobaciones = list(seg["comprobaciones"])
        if self._origenes_actualizados:
            comprobaciones.append(("ok", f"Orígenes actualizados a las {self._origenes_actualizados} "
                                         "(winget source update)."))
        for tipo, texto in comprobaciones:
            fila = QHBoxLayout()
            fila.setSpacing(SPACING_SM)
            icono = QLabel(ICONOS_TIPO[tipo])
            icono.setProperty("class", {"ok": "ok", "aviso": "aviso", "error": "error-texto"}.get(tipo, "suave"))
            icono.setFixedWidth(16)
            icono.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            fila.addWidget(icono)
            lbl = etiqueta(texto, "suave" if tipo == "info" else "normal")
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            fila.addWidget(lbl, 1)
            self.caja_seguridad.addLayout(fila)
        tipos = {t for t, _ in seg["comprobaciones"]}
        if "error" in tipos:
            texto, clase = "✗ Seguridad: revisa los avisos", "chip-error"
        elif "aviso" in tipos:
            texto, clase = "⚠ Seguridad: con avisos", "chip-aviso"
        else:
            texto, clase = "✓ winget original y SHA256 obligatorio", "chip-ok"
        self.chip_seguridad.setText(texto)
        self.chip_seguridad.setProperty("class", clase)
        refrescar_estilo(self.chip_seguridad)

    # ─── reporte ───
    def _completar_reporte(self, reporte: dict, comprobado: bool = True):
        """Compara con el análisis nuevo: qué versión quedó realmente instalada."""
        ahora = {}
        for p in self._paquetes.values():
            ahora.setdefault(p["id"].lower(), p)
        for clave in reporte["orden"]:
            f = reporte["filas"][clave]
            actual = ahora.get(f["id"].lower())
            if not comprobado:
                f["despues"] = "(sin comprobar)"
                continue
            if actual is None:
                if f["tipo"] in ("ok", "reinicio"):
                    f["despues"] = f["objetivo"]
                    if f["tipo"] == "ok":
                        f["texto"] = "Actualizado y comprobado: ya no tiene actualización pendiente."
                else:
                    f["despues"] = "ya no aparece"
                continue
            f["despues"] = "desconocida" if actual["desconocida"] else actual["instalada"]
            if f["tipo"] == "ok":
                if actual["instalada"] == f["antes"]:
                    f["tipo"] = "aviso"
                    f["texto"] = ("winget terminó bien, pero sigue apareciendo con la misma versión"
                                  + (" (winget no sabe leer su versión)" if actual["desconocida"] else "") + ".")
                else:
                    f["texto"] = f"Actualizado a {actual['instalada']}; ya hay otra más nueva ({actual['disponible']})."
            # el paquete sigue en la tabla: muestra el resultado de esta vez
            actual["resultado"] = (f["tipo"], f["texto"])
        self._llenar_tablas()

    @staticmethod
    def _resumen_reporte(reporte: dict) -> str:
        cuenta = defaultdict(int)
        for f in reporte["filas"].values():
            cuenta[f["tipo"]] += 1
        partes = []
        for tipo, texto in (("ok", "actualizados"), ("reinicio", "con reinicio pendiente"), ("aviso", "con avisos"),
                            ("error", "con fallo"), ("omitido", "omitidos"), ("cancelado", "cancelados")):
            if cuenta[tipo]:
                partes.append(f"{cuenta[tipo]} {texto}")
        return ", ".join(partes) or "sin cambios"

    def _texto_reporte(self, reporte: dict) -> str:
        filas = [dict(reporte["filas"][c]) for c in reporte["orden"]]
        for f in filas:
            f["antes"], f["despues"] = version_visible(f["antes"]), f["despues"] or "—"
        anchos = {k: max([ancho_texto(t)] + [ancho_texto(str(f[k])) for f in filas])
                  for k, t in (("nombre", "PROGRAMA"), ("id", "ID"), ("antes", "ANTES"),
                               ("despues", "DESPUÉS"), ("objetivo", "OBJETIVO"))}
        anchos = {k: min(v, 40) for k, v in anchos.items()}

        def celda(texto, k):
            texto = str(texto)
            while ancho_texto(texto) > anchos[k]:
                texto = texto[:-2] + "…"
            return texto + " " * (anchos[k] - ancho_texto(texto))

        lineas = [f"REPORTE DE ACTUALIZACIONES · {APP_NOMBRE} {APP_VERSION}",
                  f"Inicio: {reporte['inicio']}   Fin: {reporte.get('fin', '—')}",
                  f"Resultado: {self._resumen_reporte(reporte)}", ""]
        cab = "  ".join([celda("PROGRAMA", "nombre"), celda("ID", "id"), celda("ANTES", "antes"),
                         celda("DESPUÉS", "despues"), celda("OBJETIVO", "objetivo"), "RESULTADO"])
        lineas += [cab, "-" * len(cab)]
        for f in filas:
            lineas.append("  ".join([celda(f["nombre"], "nombre"), celda(f["id"], "id"), celda(f["antes"], "antes"),
                                     celda(f["despues"], "despues"), celda(f["objetivo"], "objetivo"),
                                     f"{ICONOS_TIPO.get(f['tipo'], '•')} {f['texto']}"]))
        lineas += ["", "Detalle por paquete:"]
        for f in filas:
            lineas.append(f"· {f['nombre']} ({f['id']}, origen {f['origen']})")
            if f.get("verificacion"):
                lineas.append(f"    Verificación: {f['verificacion']}")
            if f.get("hash"):
                lineas.append("    winget comprobó el SHA256 del instalador antes de ejecutarlo.")
            if f.get("ubicacion"):
                lineas.append(f"    Carpeta de instalación (--location): {f['ubicacion']}")
            if f.get("codigo"):
                lineas.append(f"    Código de winget: {codigo_hex(f['codigo'])}")
        return "\n".join(lineas) + "\n"

    def _guardar_reporte(self, reporte: dict):
        ruta = CARPETA_REGISTROS / time.strftime("actualizaciones_%Y-%m-%d_%H-%M-%S.txt")
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(self._texto_reporte(reporte), encoding="utf-8")
            reporte["archivo"] = str(ruta)
            self.consola.agregar(f"Reporte guardado en «{ruta}».", "ok")
        except OSError as e:
            self.consola.agregar(f"No se pudo guardar el reporte: {e}", "aviso")

    def _ver_reporte(self):
        if not self._reporte or self.sin_dialogos:
            return
        DialogoReporte(self, self._reporte).exec()

    def reintentar(self, ids: list[str]):
        """Desde el reporte: vuelve a marcar solo esos paquetes y pide confirmación para actualizarlos."""
        buscados = {i.lower() for i in ids}
        claves = [c for c, p in self._paquetes.items() if p["id"].lower() in buscados and p["grupo"] == "lote"]
        if not claves or self._flujo is not None:
            return
        self._seleccion = set(claves)
        self._llenar_tablas()
        self.actualizar_seleccionadas()


# ═════════════════════════════════════════════════════════════════════════════
# 7. ACERCA DE
# ═════════════════════════════════════════════════════════════════════════════

HERRAMIENTAS = [
    ("Copiar", "Robocopy con exclusiones, % y tiempo restante, multihilo según el disco."),
    ("Organizar", "Mueve o copia archivos a una carpeta por extensión, sin sobrescribir."),
    ("Listar rutas", "Un .txt con las rutas de archivos y carpetas, con filtros."),
    ("Info entorno", "Versiones de Python y de cada librería de un venv o del global."),
    ("Licencias", "THIRD_PARTY_NOTICES.txt de un venv, con JSON extra opcional."),
    ("Actualizaciones", "winget upgrade con SHA256, firma digital (PowerShell) y reporte de cada paquete."),
]


class PaginaAcerca(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.setObjectName("pagina")
        self.ventana = ventana
        dpr = ventana.devicePixelRatioF() or 1.0

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        contenido = QWidget()
        contenido.setObjectName("contenidoScroll")
        scroll.setWidget(contenido)
        raiz.addWidget(scroll)
        v = QVBoxLayout(contenido)
        v.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_LG)
        v.setSpacing(SPACING_MD)

        lbl = QLabel("Acerca de")
        lbl.setProperty("class", "titulo-pagina")
        v.addWidget(lbl)

        # ─── Presentación + creador ───
        fila = QHBoxLayout()
        fila.setSpacing(SPACING_MD)
        heroe, lay = tarjeta()
        lay.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        cabeza = QHBoxLayout()
        cabeza.setSpacing(SPACING_LG)
        logo = QLabel()
        logo.setPixmap(pixmap_escalado("logo_app.png", 96, dpr))
        cabeza.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(SPACING_SM)
        nombre = QLabel(APP_NOMBRE)
        nombre.setProperty("class", "titulo-pagina")
        textos.addWidget(nombre)
        version = QLabel(f"Versión {APP_VERSION}")
        version.setProperty("class", "version")
        textos.addWidget(version, 0, Qt.AlignmentFlag.AlignLeft)
        textos.addWidget(etiqueta("Varias utilidades en una sola ventana: copiar, organizar, listar rutas, "
                                  "revisar entornos de Python y sus licencias, y actualizar programas con winget.",
                                  "suave"))
        textos.addStretch(1)
        cabeza.addLayout(textos, 1)
        lay.addLayout(cabeza)
        fila.addWidget(heroe, 3)

        autor, lay = tarjeta()
        lay.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        avatar = QLabel()
        avatar.setPixmap(pixmap_circular("avatar_DoMiN.jpg", 88, dpr))
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(avatar)
        for texto, clase in (("CREADO POR", "etiqueta"), (APP_AUTOR, "autor"),
                             (f"{APP_AUTOR_NOMBRE} · © {APP_ANIO}", "suave")):
            w = etiqueta(texto, clase)
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(w)
        fila.addWidget(autor, 2)
        v.addLayout(fila)

        # ─── Herramientas ───
        card, lay = tarjeta("Herramientas")
        g = grid_opciones()
        for i, (nombre_h, desc) in enumerate(HERRAMIENTAS):
            n = QLabel(nombre_h)
            n.setProperty("class", "dato")
            g.addWidget(n, i, 0)
            g.addWidget(etiqueta(desc, "suave"), i, 1)
        lay.addLayout(g)
        v.addWidget(card)

        # ─── Información técnica ───
        card, lay = tarjeta("Información")
        g = grid_opciones()
        datos = [
            ("VERSIÓN", APP_VERSION),
            ("EJECUCIÓN", forma_de_ejecucion()),
            ("PYTHON", sys.version.split()[0]),
            ("INTERFAZ", f"PyQt6 {PYQT_VERSION_STR} (GPL v3) · Qt {QT_VERSION_STR} (LGPL v3)"),
            ("CONFIGURACIÓN", str(CONFIG_PATH)),
            ("REGISTROS", str(CARPETA_REGISTROS)),
        ]
        for i, (nombre_d, valor) in enumerate(datos):
            g.addWidget(etiqueta(nombre_d), i, 0)
            lbl = QLabel(valor)
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            g.addWidget(lbl, i, 1)
        lay.addLayout(g)
        botones = QHBoxLayout()
        botones.setSpacing(SPACING_SM)
        b = boton("Abrir registros", tooltip="Reportes de Actualizaciones y registros completos de robocopy")
        b.clicked.connect(self._abrir_registros)
        botones.addWidget(b)
        b = boton("Abrir carpeta de datos", "fantasma",
                  "Configuración, sesiones guardadas, registros y fallo_grave.log")
        b.clicked.connect(lambda: abrir_en_sistema(CARPETA_DATOS))
        botones.addWidget(b)
        botones.addStretch(1)
        lay.addLayout(botones)
        v.addWidget(card)

        # ─── Licencia (avisos legales que pide la GPL v3 en programas interactivos) ───
        card, lay = tarjeta(f"Licencia: {APP_LICENCIA}")
        lay.addWidget(etiqueta(
            f"© {APP_ANIO} {APP_AUTOR_NOMBRE} ({APP_AUTOR}). Este programa es software libre: puedes "
            "redistribuirlo y/o modificarlo bajo los términos de la Licencia Pública General de GNU, versión 3 "
            "o (a tu elección) cualquier versión posterior. Se distribuye con la esperanza de que sea útil, pero "
            "SIN NINGUNA GARANTÍA; ni siquiera la garantía implícita de COMERCIABILIDAD o IDONEIDAD PARA UN "
            "PROPÓSITO PARTICULAR.", "suave"))
        lay.addWidget(etiqueta(
            f"El logo de la app y el avatar de {APP_AUTOR} NO están bajo la GPL: © {APP_ANIO} {APP_AUTOR_NOMBRE}, "
            "todos los derechos reservados. Se pueden compartir sin modificar solo junto con este programa; "
            "las versiones modificadas deben usar imágenes propias.", "suave"))
        lay.addWidget(etiqueta(
            f"Usa PyQt6 {PYQT_VERSION_STR} (GPL v3) y Qt {QT_VERSION_STR} (LGPL v3). Robocopy, PowerShell y "
            "winget son programas de Windows que la app solo ejecuta; no van incluidos.", "suave"))
        botones = QHBoxLayout()
        botones.setSpacing(SPACING_SM)
        b = boton("Ver licencia", tooltip="Texto completo de la GNU GPL v3")
        b.clicked.connect(lambda: self._ver_archivo_legal(
            "LICENSE", "Licencia Pública General de GNU v3", "https://www.gnu.org/licenses/gpl-3.0.html",
            "Texto oficial (en inglés) de la licencia del código · archivo LICENSE"))
        botones.addWidget(b)
        b = boton("Logo y avatar", "fantasma", "Condiciones de uso del logo y del avatar (no están bajo la GPL)")
        b.clicked.connect(lambda: self._ver_archivo_legal(
            "LICENCIA_LOGO_Y_AVATAR.txt", "Logo y avatar: condiciones de uso", None))
        b.setVisible(archivo_legal("LICENCIA_LOGO_Y_AVATAR.txt") is not None)
        botones.addWidget(b)
        b = boton("Avisos de terceros", "fantasma", "Licencias de PyQt6, Qt, sip y Python incluidos en el .exe")
        b.clicked.connect(lambda: self._ver_archivo_legal("THIRD_PARTY_NOTICES.txt", "Avisos de terceros", None))
        b.setVisible(archivo_legal("THIRD_PARTY_NOTICES.txt") is not None)   # solo existe en la versión compilada
        botones.addWidget(b)
        b = boton("Código fuente", "fantasma", APP_REPO)
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(APP_REPO)))
        botones.addWidget(b)
        botones.addStretch(1)
        lay.addLayout(botones)
        v.addWidget(card)

        v.addStretch(1)
        pie = etiqueta(f"© {APP_ANIO} {APP_AUTOR_NOMBRE} ({APP_AUTOR}) · {APP_LICENCIA}", "suave")
        pie.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(pie)

    @staticmethod
    def _abrir_registros():
        try:
            CARPETA_REGISTROS.mkdir(parents=True, exist_ok=True)     # aún no hay registros la primera vez
        except OSError:
            pass
        abrir_en_sistema(CARPETA_REGISTROS)

    def _ver_archivo_legal(self, nombre: str, titulo: str, url_respaldo: str | None, subtitulo: str = ""):
        ruta = archivo_legal(nombre)
        if ruta is None:
            if url_respaldo:
                QDesktopServices.openUrl(QUrl(url_respaldo))
            else:
                QMessageBox.information(self, APP_NOMBRE, f"No se encontró {nombre}.")
            return
        DialogoTexto(self, titulo, subtitulo or f"Archivo {ruta.name}", leer_texto(ruta), ajustar_ancho=True).exec()

    # Misma interfaz que las demás páginas (la ventana las recorre al cerrar)
    def ocupada(self) -> bool:
        return False

    def cancelar(self):
        pass

    def esperar(self, ms: int = 0):
        pass


# ═════════════════════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ═════════════════════════════════════════════════════════════════════════════

class VentanaPrincipal(QMainWindow):
    def __init__(self, app: QApplication, config: Config):
        super().__init__()
        self.app, self.config = app, config
        self.setWindowTitle(f"{APP_NOMBRE} {APP_VERSION}")
        self.setMinimumSize(900, 560)
        self._ajustar_a_pantalla()

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
        dpr = self.devicePixelRatioF() or 1.0
        logo = QLabel()
        logo.setPixmap(pixmap_escalado("logo_app.png", 32, dpr))
        h.addWidget(logo)
        titulo = QLabel(APP_NOMBRE)
        titulo.setProperty("class", "titulo-app")
        h.addWidget(titulo)
        sub = etiqueta("Copiar · Organizar · Listar rutas · Entornos Python · Licencias · Actualizaciones", "suave")
        sub.setWordWrap(False)
        sub.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        h.addWidget(sub, 1)
        # Creador: avatar + nombre; abre «Acerca de»
        self.btn_creador = boton(f"  {APP_AUTOR}", "creador",
                                 f"Creado por {APP_AUTOR_NOMBRE} ({APP_AUTOR}) · Acerca de")
        avatar = pixmap_circular("avatar_DoMiN.jpg", 24, dpr)
        if not avatar.isNull():
            self.btn_creador.setIcon(QIcon(avatar))
            self.btn_creador.setIconSize(QSize(24, 24))
        self.btn_creador.clicked.connect(lambda: self.tabs.setCurrentWidget(self.pagina_acerca))
        h.addWidget(self.btn_creador)
        self.btn_tema = boton("", "fantasma", "Cambiar entre tema claro y oscuro")
        self.btn_tema.clicked.connect(self.alternar_tema)
        h.addWidget(self.btn_tema)
        v.addWidget(barra)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)   # Fusion dibuja una línea clara que no sigue el tema
        self.paginas = [
            ("Copiar", PaginaCopiar(self)),
            ("Organizar", PaginaOrganizar(self)),
            ("Listar rutas", PaginaRutas(self)),
            ("Info entorno", PaginaEntorno(self)),
            ("Licencias", PaginaLicencias(self)),
            ("Actualizaciones", PaginaActualizar(self)),
        ]
        self.pagina_acerca = PaginaAcerca(self)
        self.paginas.append(("Acerca de", self.pagina_acerca))
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
        self.app.setPalette(paleta_qt(p))
        self.app.setStyleSheet(construir_qss(p, preparar_iconos(p, tema),
                                             self.f_cuerpo, self.f_titulo, self.f_mono))
        self.btn_tema.setText("☀  Tema claro" if tema == "oscuro" else "☾  Tema oscuro")
        self.btn_tema.setMinimumWidth(self.btn_tema.sizeHint().width() + SPACING_MD)

    def alternar_tema(self):
        self.aplicar_tema("claro" if self.config.datos["tema"] == "oscuro" else "oscuro")
        self.config.guardar()

    def _ajustar_a_pantalla(self):
        """Tamaño inicial que siempre cabe en la pantalla (o el último que usaste)."""
        geometria = self.config.datos.get("ventana")
        if isinstance(geometria, str) and geometria:
            try:
                if self.restoreGeometry(QByteArray.fromBase64(geometria.encode("ascii"))):
                    return
            except Exception:
                pass
        pantalla = QApplication.primaryScreen()
        if pantalla is None:
            self.resize(1280, 800)
            return
        area = pantalla.availableGeometry()
        ancho = min(1320, int(area.width() * 0.92))
        alto = min(860, int(area.height() * 0.90))
        self.resize(ancho, alto)
        self.move(area.x() + (area.width() - ancho) // 2, area.y() + (area.height() - alto) // 2)

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
        self.config.datos["ventana"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.config.guardar()
        e.accept()


# ═════════════════════════════════════════════════════════════════════════════
# AUTOPRUEBA (para revisar los .exe compilados sin mostrar la ventana)
# ═════════════════════════════════════════════════════════════════════════════

def autoprueba(app: QApplication, ventana: VentanaPrincipal) -> int:
    """
    `UtilidadesArchivos.exe --autoprueba`: con la ventana oculta y una configuración
    temporal, prueba recursos, complementos de Qt y cada pestaña con archivos de prueba
    (incluido el JSON extra de Licencias). Mide cuánto se llega a trabar la interfaz.
    Deja autoprueba.json en UTILIDADES_DATOS o junto al .exe. Código de salida 0 = todo bien.
    """
    import faulthandler
    from PyQt6.QtGui import QImageReader

    if _REGISTRO_FALLOS["archivo"] is not None:
        # Si algo se queda colgado, deja la pila en fallo_grave.log y termina
        faulthandler.dump_traceback_later(240, exit=True, file=_REGISTRO_FALLOS["archivo"])
    ventana.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    ventana.show()
    pag = dict(ventana.paginas)
    pag["Actualizaciones"].sin_dialogos = True
    pruebas: dict[str, dict] = {}
    # Latido cada 10 ms mientras la app trabaja: si tarda mucho más en llegar, la
    # interfaz estuvo trabada ese tiempo
    bloqueos: list[int] = []
    por_prueba: dict[str, int] = {}          # el peor bloqueo de cada prueba, para saber dónde fue
    prueba_actual = {"nombre": ""}
    reloj = QElapsedTimer()
    latido = QTimer()
    latido.setInterval(10)

    def latir():
        ms = reloj.restart()
        bloqueos.append(ms)
        nombre = prueba_actual["nombre"]
        por_prueba[nombre] = max(por_prueba.get(nombre, 0), ms)
    latido.timeout.connect(latir)

    def esperar(pagina, segundos: float) -> bool:
        limite = time.monotonic() + segundos
        reloj.start()
        latido.start()
        while pagina.ocupada() and time.monotonic() < limite:
            app.processEvents()
            time.sleep(0.005)
        latido.stop()
        for _ in range(20):           # que la consola termine de escribir
            app.processEvents()
            time.sleep(0.005)
        return not pagina.ocupada()

    def registrar(nombre: str, ok: bool, **detalle):
        pruebas[nombre] = {"ok": bool(ok), **detalle}

    # Bitácora paso a paso: si el proceso muere de golpe, dice en qué prueba iba
    bitacora = CARPETA_DATOS / "autoprueba_pasos.txt"

    def paso(texto: str):
        try:
            with open(bitacora, "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%H:%M:%S')} {texto}\n")
        except OSError:
            pass

    def probar(nombre: str, funcion):
        prueba_actual["nombre"] = nombre
        paso(f"inicio {nombre}")
        try:
            funcion()
        except Exception as e:
            registrar(nombre, False, error=f"{type(e).__name__}: {e}")
        paso(f"fin {nombre}: {pruebas.get(nombre)}")

    try:
        bitacora.unlink()
    except OSError:
        pass
    paso("inicio de la autoprueba")
    formatos = {bytes(f).decode().lower() for f in QImageReader.supportedImageFormats()}
    # Desde GitHub se puede compilar sin la carpeta recursos (el logo y el avatar no van en el repositorio)
    hay_recursos = carpeta_recursos().is_dir()
    if hay_recursos:
        registrar("recursos", not imagen("logo_app.png").isNull() and not imagen("avatar_DoMiN.jpg").isNull(),
                  carpeta=str(carpeta_recursos()))
    else:
        registrar("recursos", True, omitida="compilado sin la carpeta recursos (sin logo ni avatar)")
    registrar("formatos_imagen", {"png", "jpg", "svg"} <= formatos,
              encontrados=sorted(formatos & {"png", "jpg", "jpeg", "svg", "ico"}))
    registrar("menus_en_espanol", app.property("traduccion_es") is True)
    registrar("avisos_legales", archivo_legal("LICENSE") is not None
              and (not hay_recursos or archivo_legal("LICENCIA_LOGO_Y_AVATAR.txt") is not None))
    ventana.config.guardar()
    registrar("configuracion", CONFIG_PATH.exists() and ventana.config.error is None, ruta=str(CONFIG_PATH))

    tmp = Path(tempfile.mkdtemp(prefix="utilidades_autoprueba_"))
    try:
        origen = tmp / "origen con espacios (ñ)"
        for i in range(300):
            carpeta = origen / f"sub{i % 10}"
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / f"archivo{i}.txt").write_bytes(b"x" * 1024)
        (origen / "__pycache__").mkdir()
        (origen / "__pycache__" / "cache.pyc").write_bytes(b"c")
        (origen / "documento.pdf").write_bytes(b"%PDF")
        (origen / "foto.JPG").write_bytes(b"jpg")

        # 1. Copiar (robocopy)
        def copiar():
            p = pag["Copiar"]
            destino = tmp / "destino"
            p.origen.establecer(str(origen))
            p.destino.establecer(str(destino))
            p.chk_simular.setChecked(False)
            p.iniciar()
            terminado = esperar(p, 120)
            copia = destino / origen.name
            n = sum(1 for _ in copia.rglob("*.txt")) if copia.exists() else 0
            registrar("copiar", terminado and p.salio_bien and n == 300 and not (copia / "__pycache__").exists(),
                      archivos_copiados=n, estado=p.lbl_estado.text())
        if ES_WINDOWS:
            probar("copiar", copiar)

        # 2. Listar rutas
        def rutas():
            p = pag["Listar rutas"]
            p.carpeta.establecer(str(origen))
            p.carpeta_salida.establecer(str(tmp))
            p.rb_solo.setChecked(True)
            p.lista_ext.establecer([[".pdf", True], [".jpg", True]])
            p.generar()
            esperar(p, 60)
            lineas = Path(p._ultima_salida).read_text(encoding="utf-8").splitlines() if p._ultima_salida else []
            archivos = [x for x in lineas if Path(x).suffix]
            registrar("listar_rutas", len(archivos) == 2, rutas=len(lineas))
        probar("listar_rutas", rutas)

        # 3. Organizar (escanear y copiar los .pdf, sin la pregunta de confirmación)
        def organizar():
            p = pag["Organizar"]
            p.origen.establecer(str(origen))
            p.escanear()
            esperar(p, 60)
            destino = tmp / "Organizado"
            p.lanzar(tarea_organizar, (p._por_ext, [".pdf"], str(destino), False, True), p._organizado)
            esperar(p, 60)
            registrar("organizar", (destino / "pdf" / "documento.pdf").exists() and (origen / "documento.pdf").exists(),
                      extensiones=sorted(p._por_ext or {}))
        probar("organizar", organizar)

        # 4 y 5. Info entorno y Licencias con el Python global (si hay uno)
        try:
            python_global = buscar_python_global()
        except Exception:
            python_global = None
        if python_global is None:
            registrar("info_entorno", True, omitida="no hay un Python global en el PATH")
            registrar("licencias", True, omitida="no hay un Python global en el PATH")
        else:
            def info():
                p = pag["Info entorno"]
                p.selector.rb_global.setChecked(True)
                p.carpeta_salida.establecer(str(tmp))
                p.analizar()
                esperar(p, 180)
                registrar("info_entorno", bool(p._datos and p._datos["paquetes"]) and (tmp / "requirements.txt").exists(),
                          python=str(python_global), paquetes=len((p._datos or {}).get("paquetes", [])))
            probar("info_entorno", info)

            def licencias():
                (tmp / "LICENCIA_COMPONENTE.txt").write_text("Texto de la licencia de prueba", encoding="utf-8")
                extra = tmp / "licencias_extra.json"
                extra.write_text(json.dumps({
                    "encabezado": "Encabezado propio de la autoprueba",
                    "componentes": [{"nombre": "ComponentePrueba", "version": "1.0", "tipo": "MIT",
                                     "url": "https://example.com", "archivo": "LICENCIA_COMPONENTE.txt"}],
                }, ensure_ascii=False), encoding="utf-8")
                p = pag["Licencias"]
                p.selector.rb_global.setChecked(True)
                p.carpeta_salida.establecer(str(tmp))
                p.extra.establecer(str(extra))
                p.generar(False)
                esperar(p, 300)
                doc = tmp / "THIRD_PARTY_NOTICES.txt"
                texto = doc.read_text(encoding="utf-8") if doc.exists() else ""
                registrar("licencias", "Encabezado propio de la autoprueba" in texto
                          and "--- ComponentePrueba (1.0) ---" in texto and "Texto de la licencia de prueba" in texto,
                          kb=len(texto) // 1024)
            probar("licencias", licencias)

        # 6. Actualizaciones: lectura de la salida de winget (no depende de tener winget)
        def lectura_winget():
            muestra = ("Nombre        Id                   Versión  Disponible Origen\n"
                       "---------------------------------------------------------------\n"
                       "Programa Uno  Editor.ProgramaUno   1.2.0    2.0.1      winget\n"
                       "Programa Dos  Editor.ProgramaDos   Unknown  3.1        winget\n"
                       "2 actualizaciones disponibles.\n")
            filas = parsear_lista_winget(muestra, {"winget", "msstore"})
            show = ("Encontrado Programa Uno [Editor.ProgramaUno]\nVersión: 2.0.1\nEditor: Editor SA\n"
                    "Instalador:\n  Dirección URL del instalador: https://ejemplo.com/setup.exe\n"
                    "  Instalador SHA256: " + "ab" * 32 + "\n")
            info = parsear_show(show, "Editor.ProgramaUno")
            registrar("actualizaciones_lectura",
                      [f["id"] for f in filas] == ["Editor.ProgramaUno", "Editor.ProgramaDos"]
                      and filas[1]["desconocida"] and info["sha256"] == "ab" * 32 and info["editor"] == "Editor SA"
                      and salto_de_version("1.2.0", "2.0.1")[0] == "Mayor +1",
                      filas=len(filas))
        probar("actualizaciones_lectura", lectura_winget)

        # 7. Actualizaciones con el winget real: solo lectura (seguridad y lista), sin instalar nada
        def analisis_winget():
            p = pag["Actualizaciones"]
            p.analizar(False)
            esperar(p, 300)
            p.consola._vaciar()
            seg = p._seguridad or {}
            if seg and not seg.get("winget"):
                registrar("actualizaciones_winget", True, omitida="winget no está instalado")
                return
            registrar("actualizaciones_winget", bool(seg) and "Error interno" not in p.consola.toPlainText(),
                      winget_original=seg.get("genuino"), sha256_obligatorio=seg.get("hash_obligatorio"),
                      paquetes=len(p._paquetes))
        if ES_WINDOWS:
            probar("actualizaciones_winget", analisis_winget)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    maximo = max(bloqueos, default=0)
    registrar("interfaz_sin_congelarse", maximo < 500, max_bloqueo_ms=maximo, por_prueba=por_prueba)
    ok = all(p["ok"] for p in pruebas.values())
    informe = {
        "resultado": "OK" if ok else "FALLO",
        "version": APP_VERSION,
        "ejecucion": forma_de_ejecucion(),
        "python": sys.version.split()[0],
        "qt": QT_VERSION_STR,
        "rutas": {"app": str(carpeta_app()), "recursos": str(carpeta_recursos()), "datos": str(CARPETA_DATOS)},
        "pruebas": pruebas,
    }
    ventana.close()
    app.processEvents()
    texto = json.dumps(informe, ensure_ascii=False, indent=2)
    for carpeta in (Path(os.environ.get("UTILIDADES_DATOS") or carpeta_app()), CARPETA_DATOS):
        try:
            (carpeta / "autoprueba.json").write_text(texto, encoding="utf-8")
            break
        except OSError:
            continue
    return 0 if ok else 1


# Archivo de fallo_grave.log y el manejador de mensajes de Qt: deben seguir vivos toda la sesión
_REGISTRO_FALLOS: dict = {"archivo": None, "manejador": None}


def escribir_fallo(texto: str):
    archivo = _REGISTRO_FALLOS["archivo"]
    if archivo is None:
        return
    try:
        archivo.write(texto.rstrip("\n") + "\n")
        archivo.flush()
    except (OSError, ValueError):
        pass


def activar_registro_de_fallos():
    """
    fallo_grave.log (en la carpeta de datos) guarda la pila de Python si la app se cierra de
    golpe, los mensajes graves de Qt y los errores de Python no controlados: compilada sin
    consola no habría otra pista. Se sobrescribe en cada arranque.
    """
    import faulthandler
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
    try:
        CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
        archivo = open(CARPETA_DATOS / "fallo_grave.log", "w", encoding="utf-8")
        archivo.write(f"{APP_NOMBRE} {APP_VERSION} ({forma_de_ejecucion()}) · {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                      "Si la app falló o se cerró sola, aquí abajo queda el motivo:\n")
        archivo.flush()
        faulthandler.enable(archivo, all_threads=True)
    except OSError:
        return
    _REGISTRO_FALLOS["archivo"] = archivo

    graves = (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg)

    def mensaje_qt(tipo, contexto, texto):
        if tipo in graves:
            escribir_fallo(f"[Qt {tipo.name}] {texto}")
        if sys.stderr is not None:          # sin consola (compilada) es None
            try:
                print(texto, file=sys.stderr)
            except (OSError, ValueError):
                pass

    _REGISTRO_FALLOS["manejador"] = mensaje_qt
    qInstallMessageHandler(mensaje_qt)


def instalar_manejador_de_errores(ventana=None, mostrar: bool = True):
    """
    PyQt6 cierra la app de golpe si un botón o señal lanza una excepción no controlada.
    Así se registra en fallo_grave.log, se avisa con un mensaje y la app sigue abierta.
    """
    import traceback

    def al_error(tipo, valor, rastro):
        texto = "".join(traceback.format_exception(tipo, valor, rastro))
        escribir_fallo(f"[Error de Python] {time.strftime('%H:%M:%S')}\n{texto}")
        if sys.stderr is not None:
            try:
                sys.stderr.write(texto)
            except (OSError, ValueError):
                pass
        if mostrar:
            try:
                QMessageBox.critical(ventana, APP_NOMBRE,
                                     f"Ocurrió un error inesperado:\n\n{valor}\n\n"
                                     f"Los detalles quedaron en:\n{CARPETA_DATOS / 'fallo_grave.log'}")
            except Exception:
                pass

    sys.excepthook = al_error


def ruta_corta(ruta: str) -> str:
    """Ruta 8.3 de Windows (C:\\Users\\DOMINA~1\\...); si no se puede, la original."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(str(ruta), buf, 1024):
            return buf.value
    except Exception:
        pass
    return str(ruta)


def acortar_rutas_de_plugins():
    """
    Windows no carga DLLs con rutas de más de 260 caracteres. Si la app está en una carpeta
    muy profunda, ...\\plugins\\platforms\\qwindows.dll se pasa del límite y Qt se cierra con
    "no Qt platform plugin could be initialized". Se le da a Qt la ruta corta (8.3) de sus
    plugins, que apunta a la misma carpeta. Va antes de crear QApplication.
    """
    if not ES_WINDOWS:
        return
    from PyQt6.QtCore import QCoreApplication, QLibraryInfo
    plugins = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
    if len(plugins) + len("\\imageformats\\qwebp.dll") < 250:
        return
    corta = ruta_corta(plugins)
    if corta != plugins and os.path.isdir(corta):
        QCoreApplication.setLibraryPaths([corta] + QCoreApplication.libraryPaths())


def main():
    migrar_datos_viejos()
    activar_registro_de_fallos()
    acortar_rutas_de_plugins()
    if ES_WINDOWS:
        try:  # icono propio en la barra de tareas en vez del de python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except Exception:
            pass
    if "--autoprueba" in sys.argv and not os.environ.get("UTILIDADES_DATOS"):
        try:        # empezar con la configuración predeterminada
            CONFIG_PATH.unlink()
        except OSError:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NOMBRE)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_AUTOR)
    app.setStyle("Fusion")
    app.setProperty("traduccion_es", cargar_traduccion_qt(app))
    icono = recurso("app.ico") if recurso("app.ico").exists() else recurso("logo_app.png")
    app.setWindowIcon(QIcon(str(icono)))
    ventana = VentanaPrincipal(app, Config(CONFIG_PATH))
    autoprueba_activa = "--autoprueba" in sys.argv
    # En la autoprueba no se muestran mensajes (esperarían un clic): solo se registran
    instalar_manejador_de_errores(ventana, mostrar=not autoprueba_activa)
    if autoprueba_activa:
        sys.exit(autoprueba(app, ventana))
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
