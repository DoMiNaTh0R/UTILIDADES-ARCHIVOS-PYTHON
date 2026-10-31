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
    7. Acerca de         Versión, creador, licencia y datos de la app. Busca versiones nuevas en GitHub
                         y la actualiza (descarga comprobada + instalador de Inno Setup en silencio).

La configuración (tema, sesiones guardadas, último venv...) y los registros viven en
%LOCALAPPDATA%\\DEUS MACHINA\\UtilidadesArchivos (utilidades_config.json y registros\\), igual con el
código fuente que con el .exe compilado.

Requisitos: Python 3.9+ y PyQt6  (pip install PyQt6)

Se compila con PyInstaller (ver INSTALL.md y compilar.py). Tras compilar:
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
                             QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

# Datos de la app: los scripts de compilación los leen de aquí (sin importar PyQt6)
APP_NOMBRE = "Utilidades de archivos"
APP_ID = "UtilidadesArchivos"            # nombre del .exe y de su carpeta de datos
APP_EDITOR = "DEUS MACHINA"              # carpeta del editor en %LOCALAPPDATA%: los datos van en <editor>\<APP_ID>
APP_VERSION = "1.3.0"
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


def carpeta_local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))


def carpeta_datos() -> Path:
    """
    Dónde van la configuración, los registros y fallo_grave.log:
    %LOCALAPPDATA%\\DEUS MACHINA\\UtilidadesArchivos, igual con el código fuente que con el .exe.
    La variable UTILIDADES_DATOS la cambia (la usa la autoprueba).
    """
    if os.environ.get("UTILIDADES_DATOS"):
        return Path(os.environ["UTILIDADES_DATOS"])
    if "--autoprueba" in sys.argv:          # nunca toca tu configuración real
        return Path(tempfile.gettempdir()) / f"{APP_ID}_autoprueba"
    return carpeta_local() / APP_EDITOR / APP_ID


CARPETA_DATOS = carpeta_datos()
CONFIG_PATH = CARPETA_DATOS / "utilidades_config.json"
# Hasta la 1.1.0 los datos iban directo en %LOCALAPPDATA%\UtilidadesArchivos
CARPETA_DATOS_ANTERIOR = carpeta_local() / APP_ID


def _fusionar_carpeta(origen: Path, destino: Path) -> tuple[int, list[str]]:
    """
    Mueve lo de origen a destino sin pisar nada: si algo ya existe en destino (la app nueva ya lo
    creó), se queda el de destino y el viejo no se toca. Devuelve (cuántos movió, lo que no pudo).
    """
    movidos, quedaron = 0, []
    for item in list(origen.iterdir()):
        objetivo = destino / item.name
        try:
            if not objetivo.exists():
                shutil.move(str(item), str(objetivo))
                movidos += 1
            elif item.is_dir() and objetivo.is_dir():
                m, q = _fusionar_carpeta(item, objetivo)
                movidos, quedaron = movidos + m, quedaron + q
                try:
                    item.rmdir()                # solo si quedó vacía
                except OSError:
                    pass
            else:
                quedaron.append(str(item))
        except OSError:
            quedaron.append(str(item))          # en uso (ej. otra copia de la app abierta)
    return movidos, quedaron


def mover_datos_a_carpeta_nueva() -> tuple[str, str] | None:
    """
    La primera vez que abre esta versión, mueve %LOCALAPPDATA%\\UtilidadesArchivos a
    %LOCALAPPDATA%\\DEUS MACHINA\\UtilidadesArchivos. Si DEUS MACHINA ya existe se usa tal cual: de lo
    que tenga dentro solo se toca la carpeta UtilidadesArchivos. Devuelve (tipo, mensaje) para el
    registro, o None si no había nada que mover.
    """
    if os.environ.get("UTILIDADES_DATOS") or "--autoprueba" in sys.argv:
        return None
    viejo, nuevo = CARPETA_DATOS_ANTERIOR, CARPETA_DATOS
    if not viejo.is_dir() or norm(viejo) == norm(nuevo):
        return None
    try:
        nuevo.parent.mkdir(parents=True, exist_ok=True)         # DEUS MACHINA: se crea solo si no existe
        if not nuevo.exists():
            try:
                os.rename(viejo, nuevo)                         # misma unidad: se mueve de un solo paso
                return "ok", f"Los datos de la app (configuración, sesiones y registros) se movieron a «{nuevo}»."
            except OSError:
                pass                                            # algo abierto dentro: se mueve uno por uno
        nuevo.mkdir(exist_ok=True)
        movidos, quedaron = _fusionar_carpeta(viejo, nuevo)
        try:
            viejo.rmdir()
        except OSError:
            pass
    except OSError as e:
        return "aviso", f"No se pudieron mover los datos de «{viejo}» a «{nuevo}»: {e}"
    if not movidos:
        return None                 # lo que queda ya estaba en la carpeta nueva: no se avisa en cada arranque
    if quedaron:
        return "aviso", (f"Los datos de la app se movieron a «{nuevo}», salvo {len(quedaron)} elemento(s) que se "
                         f"quedaron en «{viejo}» (ya existían en la carpeta nueva o estaban en uso).")
    return "ok", f"Los datos de la app (configuración, sesiones y registros) se movieron a «{nuevo}»."


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
    "destaca": "#9b6dff",       # el resultado que más importa (ej. cómo queda el destino)
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

/* ─── Versión nueva de la app ────────────────────── */
QFrame#avisoApp {{
    background-color: {p['primario_suave']};
    border: none;
    border-bottom: 1px solid {p['borde']};
}}
QFrame#avisoApp QLabel {{ color: {p['texto_primario_suave']}; font-weight: 600; }}
QFrame#avisoApp[tipo="ok"] {{ background-color: rgba(46, 157, 91, 0.16); }}
QFrame#avisoApp[tipo="aviso"] {{ background-color: rgba(208, 135, 0, 0.16); }}
QFrame#avisoApp[tipo="ok"] QLabel, QFrame#avisoApp[tipo="aviso"] QLabel {{ color: {p['texto']}; }}
QTextBrowser#notasRelease {{
    background-color: {p['superficie']};
    border: 1px solid {p['borde']};
    border-radius: {RADIUS_DEFAULT}px;
    padding: {SPACING_SM}px;
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
# CONFIGURACIÓN (JSON en %LOCALAPPDATA%\DEUS MACHINA\UtilidadesArchivos)
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


def entorno_powershell() -> dict | None:
    """
    Si la app se abrió desde PowerShell 7, hereda su PSModulePath y Windows PowerShell 5.1 no puede cargar
    Get-AuthenticodeSignature: sin ella, usa sus módulos de siempre. None = el entorno de la app tal cual.
    """
    if "PSModulePath" not in os.environ:
        return None
    return {k: v for k, v in os.environ.items() if k.lower() != "psmodulepath"}


FLAGS_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Cancelado(Exception):
    pass


def ejecutar_cancelable(tarea, cmd, timeout=600, env: dict | None = None) -> subprocess.CompletedProcess:
    """subprocess.run que se puede cancelar desde la interfaz."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL, env=env or entorno_limpio(),
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


# ─── Entornos de conda (Anaconda, Miniconda, Miniforge, Mambaforge…) ────────

# Carpetas donde los instaladores dejan conda por defecto (para el usuario o para todos)
NOMBRES_CONDA = {"anaconda3": "Anaconda", "anaconda": "Anaconda", "miniconda3": "Miniconda",
                 "miniconda": "Miniconda", "miniforge3": "Miniforge", "miniforge": "Miniforge",
                 "mambaforge": "Mambaforge", "micromamba": "micromamba"}


def carpeta_escritorio() -> Path:
    """El Escritorio real (también si OneDrive lo movió)."""
    from PyQt6.QtCore import QStandardPaths
    ruta = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    return Path(ruta) if ruta else Path.home() / "Desktop"


def es_entorno_conda(carpeta) -> bool:
    try:
        return (Path(carpeta) / "conda-meta").is_dir()
    except OSError:
        return False


def python_de_conda(carpeta: Path) -> Path | None:
    for rel in ("python.exe", "bin/python3", "bin/python"):
        if (carpeta / rel).is_file():
            return carpeta / rel
    return None


def raiz_conda(entorno: Path) -> Path | None:
    """La instalación de conda a la que pertenece un entorno (la que tiene condabin\\)."""
    if (entorno / "condabin").is_dir():
        return entorno                                      # es el «base»
    if entorno.parent.name.lower() == "envs" and (entorno.parent.parent / "condabin").is_dir():
        return entorno.parent.parent
    # Entornos creados en otra carpeta (ej. %USERPROFILE%\.conda\envs): conda anota quién los creó
    try:
        with open(entorno / "conda-meta" / "history", encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                m = re.match(r"#\s*cmd:\s*(.+?[\\/])(Scripts|bin)[\\/]conda", linea, re.I)
                if m and (Path(m.group(1)) / "condabin").is_dir():
                    return Path(m.group(1))
    except OSError:
        pass
    return None


def conda_ejecutable(entorno: Path) -> str | None:
    """conda.exe (o conda.bat / mamba.exe) para exportar el entorno con «conda env export»."""
    raices = [r for r in (raiz_conda(entorno),) if r]
    if os.environ.get("CONDA_EXE"):
        raices.append(Path(os.environ["CONDA_EXE"]).parent.parent)
    raices += [Path(e["raiz"]) for e in detectar_entornos_conda() if e.get("raiz")]
    for raiz in raices:
        for rel in ("Scripts/conda.exe", "condabin/conda.bat", "Scripts/mamba.exe", "bin/conda"):
            if (raiz / rel).is_file():
                return str(raiz / rel)
    return shutil.which("conda")


def version_python_conda(carpeta: Path) -> str:
    """Versión de Python del entorno sin ejecutarlo (conda-meta\\python-3.11.5-….json)."""
    try:
        for f in (carpeta / "conda-meta").glob("python-*.json"):
            m = re.match(r"python-(\d+(?:\.\d+)+)-", f.name)
            if m:
                return m.group(1)
    except OSError:
        pass
    return ""


_CACHE_CONDA: list | None = None


def detectar_entornos_conda(refrescar: bool = False) -> list[dict]:
    """
    Entornos de conda con Python: {ruta, nombre, distribucion, version, raiz}. Solo mira carpetas
    (no ejecuta conda, que tarda): las instalaciones habituales, sus envs\\ y la lista que conda
    guarda en %USERPROFILE%\\.conda\\environments.txt.
    """
    global _CACHE_CONDA
    if _CACHE_CONDA is not None and not refrescar:
        return _CACHE_CONDA
    bases = [Path.home(), Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"),
             Path(os.environ.get("ProgramData") or r"C:\ProgramData"), Path((os.environ.get("SystemDrive") or "C:") + "\\")]
    raices = [b / n for b in bases for n in NOMBRES_CONDA]
    for var in ("CONDA_EXE", "MAMBA_EXE"):
        if os.environ.get(var):
            raices.append(Path(os.environ[var]).parent.parent)
    if os.environ.get("MAMBA_ROOT_PREFIX"):
        raices.append(Path(os.environ["MAMBA_ROOT_PREFIX"]))
    candidatas: list[Path] = []
    for raiz in raices:
        if es_entorno_conda(raiz) or (raiz / "envs").is_dir():
            candidatas.append(raiz)
            try:
                candidatas += sorted((x for x in (raiz / "envs").iterdir() if x.is_dir()), key=lambda x: x.name.lower())
            except OSError:
                pass
    try:
        candidatas += sorted((x for x in (Path.home() / ".conda" / "envs").iterdir() if x.is_dir()),
                             key=lambda x: x.name.lower())
    except OSError:
        pass
    try:
        with open(Path.home() / ".conda" / "environments.txt", encoding="utf-8", errors="replace") as fh:
            candidatas += [Path(x.strip()) for x in fh if x.strip()]
    except OSError:
        pass

    entornos, vistos = [], set()
    for c in candidatas:
        clave = norm(c)
        if clave in vistos or not es_entorno_conda(c) or python_de_conda(c) is None:
            continue
        vistos.add(clave)
        raiz = raiz_conda(c)
        distribucion = NOMBRES_CONDA.get((raiz or c).name.lower(), (raiz or c).name if raiz else "conda")
        entornos.append({"ruta": str(c), "nombre": "base" if raiz == c else c.name,
                         "distribucion": distribucion, "version": version_python_conda(c),
                         "raiz": str(raiz) if raiz else ""})
    _CACHE_CONDA = entornos
    return entornos


def nombre_entorno_conda(ruta: str) -> str:
    """Para los nombres de archivo: «py311», o la carpeta de la instalación si es el base (ej. «miniforge3»)."""
    return Path(ruta).name or "conda"


def nombre_python_global(version: str | None) -> str:
    """«3.14.0 (tags/…)» → «python314»: el nombre de archivo para lo del Python global."""
    m = re.match(r"\s*(\d+)\.(\d+)", version or "")
    return f"python{m.group(1)}{m.group(2)}" if m else "python_global"


def normalizar_saltos(texto: str) -> str:
    """
    Todo con «\\n». La salida de pip llega con «\\r\\n»: escrita tal cual en modo texto en Windows
    quedaba «\\r\\r\\n» y cada fila salía seguida de una vacía.
    """
    return texto.replace("\r\n", "\n").replace("\r", "\n")


def nombre_con_entorno(nombre: str, por_defecto: str, entorno: str) -> str:
    """Si dejaste el nombre predeterminado, se le añade el entorno: varios entornos al Escritorio no se pisan."""
    if nombre != por_defecto:
        return nombre
    base, ext = os.path.splitext(por_defecto)
    return f"{base}_{entorno}{ext}"


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
    «Sin guardar» se decide comparando con lo que había al cargar o guardar la sesión, no
    con cada señal: así no se marca por cambios automáticos (ej. los hilos según el disco)
    y se desmarca si deshaces el cambio.
    comparable(estado) quita lo que no cuenta como cambio (ej. los hilos si van en automático).
    """
    sesion_cargada = pyqtSignal(dict)

    def __init__(self, config: Config, clave: str, defaults: dict, obtener_estado, parent=None, comparable=None):
        super().__init__(parent)
        self.config, self.clave, self.defaults = config, clave, defaults
        self.obtener_estado = obtener_estado
        self.comparable = comparable or (lambda estado: estado)
        self._referencia: dict | None = None     # el estado de la sesión elegida (None = no coincide con ninguna)
        self._mod = False
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
        self._mod = valor
        self.lbl_mod.setVisible(valor)

    def _estado_comparable(self) -> dict:
        return self.comparable(copy.deepcopy(self.obtener_estado()))

    def _tomar_referencia(self):
        """Lo que hay en pantalla pasa a ser «guardado»."""
        self._referencia = self._estado_comparable()
        self._set_mod(False)

    def modificado(self) -> bool:
        return self._mod

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
        self._tomar_referencia()
        self._actualizar_botones()

    def marcar_modificado(self):
        """Avisa de un posible cambio: se marca solo si de verdad difiere de la sesión elegida."""
        if not self._cargando:
            self._set_mod(self._referencia is None or self._estado_comparable() != self._referencia)

    def guardar(self):
        nombre = self.combo.currentText()
        if nombre == PREDETERMINADA:
            self.guardar_como()
            return
        self._sesiones()[nombre] = self.obtener_estado()
        self.config.guardar()
        self._tomar_referencia()

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
        self._tomar_referencia()

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
        self._referencia = None
        self._set_mod(True)


class SelectorPython(QWidget):
    """Elegir un venv, un entorno de conda o el Python global."""
    cambiado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(SPACING_SM)
        self.rb_venv = QRadioButton("Un entorno virtual (venv)")
        self.rb_conda = QRadioButton("Un entorno de conda (Anaconda, Miniconda, Miniforge…)")
        self.rb_global = QRadioButton("Python global (el que sale en cmd sin activar ningún venv)")
        self.rb_venv.setChecked(True)
        grupo = QButtonGroup(self)
        for rb in (self.rb_venv, self.rb_conda, self.rb_global):
            grupo.addButton(rb)
            v.addWidget(rb)
        self.ruta = SelectorRuta("carpeta", "Carpeta del venv, ej. C:\\proyecto\\.venv")
        v.addWidget(self.ruta)
        # Entornos de conda encontrados en el equipo (o uno elegido a mano)
        self.fila_conda = QWidget()
        fc = QHBoxLayout(self.fila_conda)
        fc.setContentsMargins(0, 0, 0, 0)
        fc.setSpacing(SPACING_SM)
        self.combo_conda = ComboSinRueda()
        self.combo_conda.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fc.addWidget(self.combo_conda, 1)
        b = boton("Otra carpeta…", "fantasma", "Elegir a mano la carpeta de un entorno de conda")
        b.clicked.connect(self._elegir_conda)
        fc.addWidget(b)
        b = boton("↻", "fantasma", "Volver a buscar entornos de conda")
        b.clicked.connect(lambda: self._llenar_conda(self.venv(), refrescar=True))
        fc.addWidget(b)
        v.addWidget(self.fila_conda)
        self.info = etiqueta("", "suave")
        v.addWidget(self.info)
        self._llenar_conda("")
        self.rb_venv.toggled.connect(self._actualizar)
        self.rb_conda.toggled.connect(self._actualizar)
        self.ruta.cambiado.connect(self._actualizar)
        self.combo_conda.currentIndexChanged.connect(self._actualizar)
        self._actualizar()

    def usa_global(self) -> bool:
        return self.rb_global.isChecked()

    def es_conda(self) -> bool:
        return self.rb_conda.isChecked()

    def venv(self) -> str:
        """Carpeta del entorno elegido (venv o conda; vacío si es el global)."""
        if self.es_conda():
            return self.combo_conda.currentData() or ""
        return self.ruta.texto()

    def carpeta_venv(self) -> Path | None:
        """Carpeta del venv si es válida (para rutas de salida por defecto)."""
        if self.usa_global():
            return None
        try:
            return buscar_python_venv(self.venv())[1]
        except ValueError:
            return None

    def _llenar_conda(self, seleccion: str, refrescar: bool = False):
        self.combo_conda.blockSignals(True)
        self.combo_conda.clear()
        for e in detectar_entornos_conda(refrescar):
            texto = f"{e['nombre']} · {e['distribucion']}" + (f" · Python {e['version']}" if e["version"] else "")
            self.combo_conda.addItem(texto, e["ruta"])
            self.combo_conda.setItemData(self.combo_conda.count() - 1, e["ruta"], Qt.ItemDataRole.ToolTipRole)
        if seleccion:
            self._seleccionar_conda(seleccion)
        self.combo_conda.blockSignals(False)
        if refrescar:
            self._actualizar()

    def _seleccionar_conda(self, ruta: str):
        """Selecciona ese entorno; si no estaba en la lista (elegido a mano), lo agrega."""
        for i in range(self.combo_conda.count()):
            if norm(self.combo_conda.itemData(i) or "") == norm(ruta):
                self.combo_conda.setCurrentIndex(i)
                return
        self.combo_conda.addItem(f"{Path(ruta).name} · {ruta}", ruta)
        self.combo_conda.setCurrentIndex(self.combo_conda.count() - 1)

    def _elegir_conda(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Carpeta del entorno de conda", self.venv())
        if not carpeta:
            return
        if not es_entorno_conda(carpeta):
            QMessageBox.warning(self, APP_NOMBRE, f"«{carpeta}» no es un entorno de conda (no tiene conda-meta\\). "
                                                  "Si es un venv, elige «Un entorno virtual (venv)».")
            return
        self._seleccionar_conda(str(Path(carpeta)))

    def _actualizar(self, *_):
        conda = self.es_conda()
        self.ruta.setVisible(not conda)
        self.ruta.setEnabled(not self.usa_global())
        self.fila_conda.setVisible(conda)
        if self.usa_global():
            self.info.setText("Se detectará al ejecutar (primer python del PATH).\n"
                              "Los archivos se guardan por defecto en el Escritorio.")
            self.info.setProperty("class", "suave")
        elif conda and not self.venv():
            self.info.setText("No encontré entornos de conda con Python. Usa «Otra carpeta…» para elegirlo a mano.")
            self.info.setProperty("class", "aviso")
        elif conda:
            try:
                exe, _ = buscar_python_venv(self.venv())
                self.info.setText(f"✓ Python encontrado: {exe}\nLos archivos se guardan por defecto en el Escritorio.")
                self.info.setProperty("class", "ok")
            except ValueError as e:
                self.info.setText(str(e))
                self.info.setProperty("class", "aviso")
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
        return {"global": self.usa_global(), "venv": self.ruta.texto(), "conda": self.es_conda(),
                "conda_env": self.combo_conda.currentData() or ""}

    def establecer(self, d: dict):
        d = d or {}
        (self.rb_global if d.get("global") else self.rb_conda if d.get("conda") else self.rb_venv).setChecked(True)
        if d.get("venv"):
            self.ruta.establecer(d["venv"])
        if d.get("conda_env"):
            self.combo_conda.blockSignals(True)
            self._seleccionar_conda(d["conda_env"])
            self.combo_conda.blockSignals(False)
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

    def agregar_lineas(self, lineas: list[list[tuple[str, str]]], titulo: str = ""):
        """
        Varias líneas con partes de distinto color (ej. una tabla): [[(texto, tipo), …], …]. La hora (y el
        título) van en su propio renglón y las líneas debajo, pegadas a la izquierda.
        """
        self._pendiente.append(("lineas", lineas, time.strftime("%H:%M:%S"), titulo))
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
            if tipo in ("titulo", "destaca"):
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

    def _escribir_lineas(self, c: QTextCursor, lineas: list, hora: str, titulo: str = ""):
        c.movePosition(QTextCursor.MoveOperation.End)
        c.insertText(f"[{hora}]" + (" " if titulo else ""), self._formato("suave"))
        c.insertText(titulo + "\n", self._formato("titulo"))
        for partes in lineas:
            for texto, tipo in partes:
                c.insertText(texto, self._formato(tipo))
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
            elif item[0] == "lineas":
                self._escribir_lineas(c, item[1], item[2], item[3])
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

def describir_codigo_robocopy(codigo: int, borra: str | None = None, simulado: bool = False,
                              borrados: int | None = None) -> tuple[str, str]:
    """
    borra: «/MIR» o «/PURGE» si se usó (entonces lo extra del destino se borra, no se queda).
    borrados: cuántos borró de verdad, si se sabe (robocopy también cuenta como «extra» las
    carpetas omitidas con /XD que hay en el destino, y esas no las borra).
    """
    if codigo >= 16:
        return "error", f"Código {codigo}: error grave, robocopy no copió nada (revisa rutas y permisos)."
    partes = []
    if codigo == 0:
        partes.append("No había nada que copiar: el destino ya estaba al día.")
    if codigo & 1:
        partes.append("Hay archivos que copiar (es una simulación: no se copió nada)." if simulado
                      else "Se copiaron archivos correctamente.")
    if codigo & 2:
        if borra and simulado:
            partes.append(f"Hay cosas que solo están en el destino: con {borra} se borrarían.")
        elif borra and borrados == 0:
            partes.append(f"Hay cosas que solo están en el destino y {borra} no borró (por ejemplo, carpetas "
                          "omitidas con /XD).")
        elif borra:
            partes.append(f"Se BORRÓ del destino lo que ya no estaba en el origen ({borra}).")
        else:
            partes.append("Hay cosas que solo están en el destino: " + ("no se tocarían." if simulado
                                                                        else "no se tocaron."))
    if codigo & 4:
        partes.append("Se detectaron archivos no coincidentes.")
    if codigo & 8:
        partes.append("Algunos archivos o carpetas NO se " + ("podrían" if simulado else "pudieron")
                      + " copiar (revisa el registro).")
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
    """
    Totales del resumen final. Sin /BYTES la fila de bytes no trae números exactos («38.61 g»):
    entonces «bytes» y «bytes_extra» quedan en None.
    """
    filas = [tuple(int(x) for x in m.groups())
             for m in (RE_RESUMEN.match(linea) for linea in texto.splitlines()) if m]
    if len(filas) < 2:
        return None
    carpetas, archivos = filas[0], filas[1]
    bytes_ = filas[2] if len(filas) >= 3 else None
    return {"archivos": archivos[1], "bytes": bytes_[1] if bytes_ else None, "omitidos": archivos[2],
            "archivos_extra": archivos[5], "carpetas_extra": carpetas[5], "bytes_extra": bytes_[5] if bytes_ else None}


# La tabla completa del final, para explicarla: filas Carpetas, Archivos y Bytes con 6 columnas.
# Sin /BYTES, los bytes vienen como «29.371 g» (k, m, g y t de 1024).
RE_FILA_TABLA = re.compile(r"^\s*[^\d\s][^:]{0,20}:\s+(.+?)\s*$")
COLUMNAS_ROBOCOPY = ("total", "copiado", "omitido", "no_coincide", "error", "extras")
UNIDADES_ROBOCOPY = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3, "t": 1024 ** 4}


def _valores_fila_robocopy(resto: str) -> list[float] | None:
    valores: list[float] = []
    for token in resto.split():
        unidad = UNIDADES_ROBOCOPY.get(token.lower())
        if unidad and valores:
            valores[-1] *= unidad
        elif re.fullmatch(r"\d+(?:[.,]\d+)?", token):
            valores.append(float(token.replace(",", ".")))
        else:
            return None
    return valores


def leer_tabla_robocopy(texto: str) -> dict | None:
    """
    {"carpetas", "archivos", "bytes"} → {total, copiado, omitido, no_coincide, error, extras}.
    Las filas se reconocen por su forma y su orden, no por el texto (cambia con el idioma).
    «bytes» es None si esa fila no se pudo leer.
    """
    filas = []
    for linea in texto.splitlines():
        m = RE_FILA_TABLA.match(linea)
        valores = _valores_fila_robocopy(m.group(1)) if m else None
        if valores is not None and len(valores) == 6:
            filas.append(valores)
    if len(filas) < 2:
        return None
    filas = filas[-3:] if len(filas) >= 3 else filas
    return {"carpetas": dict(zip(COLUMNAS_ROBOCOPY, map(int, filas[0]))),
            "archivos": dict(zip(COLUMNAS_ROBOCOPY, map(int, filas[1]))),
            "bytes": dict(zip(COLUMNAS_ROBOCOPY, filas[2])) if len(filas) >= 3 else None}


RE_DURACION_ROBOCOPY = re.compile(r"(\d+):(\d{2}):(\d{2})")


def leer_tiempos_robocopy(texto: str) -> dict | None:
    """
    La fila de tiempos (Total, Copiado, ERROR, Extras) en segundos, la velocidad (bytes/s, si robocopy la
    escribe: con /MT no) y la línea de la hora en que terminó. None si no hay fila de tiempos.
    """
    tiempos = None
    velocidad = fin = None
    for linea in texto.splitlines():
        m = RE_FILA_TABLA.match(linea)
        if not m:
            continue
        tokens = m.group(1).split()
        if len(tokens) == 4 and all(RE_DURACION_ROBOCOPY.fullmatch(x) for x in tokens):
            segundos = [int(h) * 3600 + int(mi) * 60 + int(s)
                        for h, mi, s in (RE_DURACION_ROBOCOPY.fullmatch(x).groups() for x in tokens)]
            tiempos = dict(zip(("total", "copiando", "errores", "extras"), segundos))
            continue
        v = re.search(r"([\d.,]+)\s*Bytes/s", m.group(1), re.I)
        if v:
            velocidad = int(re.sub(r"\D", "", v.group(1)) or 0) or None
        elif re.search(r"\b(19|20)\d\d\b", m.group(1)) and re.search(r"\d:\d\d", m.group(1)):
            fin = m.group(1).strip()
    if tiempos is None:
        return None
    return dict(tiempos, velocidad=velocidad, fin=fin)


def dibujar_tabla(cabecera: list[str], filas: list[tuple[list[str], str]],
                  separar_antes: tuple[int, ...] = ()) -> list[list[tuple[str, str]]]:
    """
    Tabla con bordes para la consola (letra monoespaciada): una lista de líneas, cada una con sus
    partes [(texto, tipo de color)]. filas: [(celdas, tipo)]; la 1.ª columna va a la izquierda.
    separar_antes: índices de fila que llevan una raya encima.
    """
    anchos = [max(len(f[i]) for f in [cabecera] + [c for c, _ in filas]) for i in range(len(cabecera))]

    def raya(izq: str, medio: str, der: str) -> list[tuple[str, str]]:
        return [(izq + medio.join("─" * (a + 2) for a in anchos) + der, "suave")]

    def fila(celdas: list[str], tipo: str) -> list[tuple[str, str]]:
        partes = [("│", "suave")]
        for i, (celda, ancho) in enumerate(zip(celdas, anchos)):
            partes += [(" " + (celda.ljust(ancho) if i == 0 else celda.rjust(ancho)) + " ", tipo), ("│", "suave")]
        return partes
    lineas = [raya("┌", "┬", "┐"), fila(cabecera, "titulo"), raya("├", "┼", "┤")]
    for i, (celdas, tipo) in enumerate(filas):
        if i in separar_antes:
            lineas.append(raya("├", "┼", "┤"))
        lineas.append(fila(celdas, tipo))
    return lineas + [raya("└", "┴", "┘")]


def resumen_robocopy(t: dict, simulado: bool, borra: str | None, carpetas_borradas: int | None = None,
                     hay_exclusiones: bool = False) -> tuple[list, list[tuple[str, str]]]:
    """
    La tabla final de robocopy, ordenada para leerla: origen (y qué se copia y qué se omite), lo que
    solo está en el destino y CÓMO QUEDA EL DESTINO. Devuelve (líneas de la tabla, avisos [(tipo, texto)]).
    borra: «/MIR» o «/PURGE» si se usó. carpetas_borradas: las carpetas extra que borra de verdad (las
    excluidas con /XD que hay en el destino cuentan como «Extras», pero no se borran); None si no se sabe.
    """
    a, c, b = t["archivos"], t["carpetas"], t["bytes"]
    avisos: list[tuple[str, str]] = []

    def tam(col: str) -> float | None:
        return b[col] if b is not None else None

    def celdas(nombre: str, carpetas: int | None, archivos: int, tamano: float | None) -> list[str]:
        return [nombre, "—" if carpetas is None else f"{carpetas:,}", f"{archivos:,}",
                "?" if tamano is None else formatear_bytes(tamano)]

    # Con /MT robocopy cuenta de más las carpetas copiadas (el total y las omitidas sí salen bien)
    carpetas_copiadas = max(c["total"] - c["omitido"] - c["no_coincide"] - c["error"], 0)
    if c["copiado"] != carpetas_copiadas:
        avisos.append(("suave", ("Carpetas a copiar: " if simulado else "Carpetas copiadas: ")
                       + f"{carpetas_copiadas:,} (el total menos las omitidas). Robocopy decía {c['copiado']:,}: "
                         "con /MT (multihilo) las cuenta de más."))
    v = "se copiaría" if simulado else "se copió"
    filas = [(celdas("En el origen", c["total"], a["total"], tam("total")), "normal"),
             (celdas(f"  {v} (nuevo o cambiado)", carpetas_copiadas, a["copiado"], tam("copiado")), "ok"),
             (celdas("  " + ("se omitiría" if simulado else "se omitió") + " (ya igual o excluido)",
                     c["omitido"], a["omitido"], tam("omitido")), "suave")]
    if a["error"] or c["error"]:
        filas.append((celdas("  ERROR: " + ("no se podría copiar" if simulado else "no se pudo copiar"),
                             c["error"], a["error"], tam("error")), "error"))
        avisos.append(("error", f"⚠ {a['error'] + c['error']:,} elemento(s) " + ("darían" if simulado else "dieron")
                       + " ERROR aunque se reintentó (permisos, archivo en uso, ruta demasiado larga…): busca "
                         "«ERROR» en el registro."))
    if a["no_coincide"] or c["no_coincide"]:
        filas.append((celdas("  archivo y carpeta con el mismo nombre", c["no_coincide"], a["no_coincide"],
                             tam("no_coincide")), "aviso"))
        avisos.append(("aviso", f"⚠ {a['no_coincide'] + c['no_coincide']:,} choque(s) de nombre: hay un archivo en un "
                                "lado y una carpeta con el mismo nombre en el otro; robocopy no puede copiarlos."))

    # Lo que está en el destino y no en el origen: se queda, salvo con /MIR o /PURGE
    raya_destino = len(filas)
    if borra:
        carpetas_borrar = c["extras"] if carpetas_borradas is None else min(carpetas_borradas, c["extras"])
        filas.append((celdas("Solo en el destino: " + ("se BORRARÍA" if simulado else "se BORRÓ") + f" ({borra})",
                             carpetas_borrar, a["extras"], tam("extras")), "aviso"))
        quedan = (c["extras"] - carpetas_borrar, 0, 0.0)
        if quedan[0]:
            filas.append((celdas("Solo en el destino, excluido con /XD: se queda", quedan[0], 0, None), "normal"))
    else:
        filas.append((celdas("Solo en el destino: " + ("se queda" if simulado else "se quedó"),
                             c["extras"], a["extras"], tam("extras")), "normal"))
        quedan = (c["extras"], a["extras"], tam("extras"))

    # Cómo queda: lo del origen que no falló, más lo que solo estaba en el destino y no se borra
    final_c = c["total"] - c["error"] - c["no_coincide"] + quedan[0]
    final_a = a["total"] - a["error"] - a["no_coincide"] + quedan[1]
    final_b = (b["total"] - b["error"] - b["no_coincide"] + (quedan[2] or 0)) if b is not None else None
    raya_final = len(filas)
    filas.append((celdas("CÓMO QUEDARÍA EL DESTINO" if simulado else "CÓMO QUEDÓ EL DESTINO", final_c, final_a,
                         final_b), "destaca"))
    cabecera = ["Simulación (no se copió nada)" if simulado else "Copia", "Carpetas", "Archivos", "Tamaño"]
    lineas = dibujar_tabla(cabecera, filas, (raya_destino, raya_final))
    if hay_exclusiones:
        avisos.append(("suave", "«Cómo quedaría» es aproximado: lo que excluiste cuenta en el origen aunque no se "
                                "copie."))
    return lineas, avisos


def tabla_tiempos_robocopy(tiempos: dict, simulado: bool, bytes_copiados: float | None = None,
                           calculo: float | None = None) -> list:
    """
    Los tiempos de robocopy, cada uno con lo que significa, y debajo la hora en que terminó.
    calculo: lo que tardó la pasada previa que calcula el total para el % (segundos).
    """
    filas = [(["Total", formatear_duracion(tiempos["total"])], "normal"),
             (["  copiando archivos", "— (no copia)" if simulado else formatear_duracion(tiempos["copiando"])],
              "suave"),
             (["  reintentando lo que dio error", formatear_duracion(tiempos["errores"])],
              "error" if tiempos["errores"] else "suave"),
             (["  revisando lo que solo está en el destino", formatear_duracion(tiempos["extras"])], "suave")]
    separar = []
    if calculo:
        separar.append(len(filas))
        filas.append((["Antes: calcular el total (para el % y lo que falta)", formatear_duracion(calculo)], "suave"))
    velocidad = tiempos.get("velocidad")
    if not velocidad and bytes_copiados and tiempos["total"] >= 1:
        velocidad = bytes_copiados / tiempos["total"]
    if velocidad and not simulado:
        if not separar:
            separar.append(len(filas))
        filas.append((["Velocidad media", f"{formatear_bytes(velocidad)}/s"], "ok"))
    lineas = dibujar_tabla(["Tiempo de la simulación" if simulado else "Tiempo de la copia", "Duración"], filas,
                           tuple(separar[:1]))
    if tiempos.get("fin"):
        lineas.append([(f"Terminó: {tiempos['fin']}", "suave")])
    return lineas


# «*Archivo EXTRA  1234  F:\...», «*Directorio EXTRA  -1  F:\...\» (o «*EXTRA File» en inglés):
# está en el destino y no en el origen. Con /MIR o /PURGE robocopy lo borra.
RE_EXTRA_ROBOCOPY = re.compile(r"\*([^\t]*?EXTRA[^\t\d-]*)\s*(-?[\d.,]+(?:\s*[kmgt])?)\s*\t(.+?)\s*$", re.I)
OPCIONES_QUE_BORRAN = ("/MIR", "/PURGE")


def leer_extras_robocopy(texto: str) -> list[tuple[str, int]]:
    """
    (ruta, tamaño) de cada línea EXTRA; las carpetas terminan en «\\». Tamaño None si no viene
    en bytes exactos (sin /BYTES robocopy escribe «10.1 k»).
    """
    extras = []
    for linea in re.split(r"\r\n|\n|\r", texto):
        m = RE_EXTRA_ROBOCOPY.search(linea)
        if m:
            extras.append((m.group(3), int(m.group(2)) if re.fullmatch(r"-?\d+", m.group(2)) else None))
    return extras


def contar_extras(extras: list[tuple[str, int | None]]) -> dict:
    """Las mismas claves que el resumen de robocopy, pero contando solo lo que listó (lo que borra de verdad)."""
    archivos = [tam for ruta, tam in extras if not ruta.endswith(("\\", "/"))]
    exactos = all(t is not None for t in archivos)
    return {"archivos_extra": len(archivos), "carpetas_extra": len(extras) - len(archivos),
            "bytes_extra": sum(t for t in archivos if t and t > 0) if exactos else None}


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
        self._borra: str | None = None          # «/MIR» o «/PURGE» si la copia borra extras del destino
        self._final_salida = ""                 # el final de la salida (para leer el resumen de robocopy)
        self._t_calculo: float | None = None    # cuánto tardó la pasada previa (para el %)
        self._borrados: list = []               # líneas «*EXTRA» de la copia: lo que se borró de verdad
        self._linea_borrados = ""               # línea a medias entre dos lecturas
        self.sin_dialogos = False               # la autoprueba no puede esperar clics

        self.sesiones = BarraSesiones(self.config, "copiar", DEFAULT_COPIAR, self.obtener_estado,
                                      comparable=self._estado_comparable)
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
        self.lbl_aviso_extra = etiqueta("", "aviso")
        self.lbl_aviso_extra.setVisible(False)
        g.addWidget(self.lbl_aviso_extra, 9, 1)
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

    @staticmethod
    def _estado_comparable(e: dict) -> dict:
        """Con los hilos en automático, el número lo pone el disco detectado: no es un cambio tuyo."""
        if e.get("hilos_auto"):
            e.pop("hilos", None)
        return e

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
        avisos = []
        borra = self._opcion_borrado()
        if borra:
            avisos.append(f"⚠ {borra} BORRA del destino lo que ya no esté en el origen. Antes de copiar se "
                          "calcula qué se borraría y se te pregunta.")
        if {"/MOV", "/MOVE"} & {a.upper() for a in self._extra_args()}:
            avisos.append("⚠ /MOV y /MOVE borran los archivos del ORIGEN después de copiarlos.")
        self.lbl_aviso_extra.setText("\n".join(avisos))
        self.lbl_aviso_extra.setVisible(bool(avisos))

    def _opcion_borrado(self) -> str | None:
        """«/MIR» o «/PURGE» si están en los parámetros extra: con ellas robocopy borra en el destino."""
        extras = {a.upper() for a in self._extra_args()}
        return next((o for o in OPCIONES_QUE_BORRAN if o in extras), None)

    def _lista_completa(self) -> bool:
        """Si robocopy lista cada archivo y carpeta (con /NFL o /NDL en los extra no los nombra)."""
        return not ({"/NFL", "/NDL"} & {a.upper() for a in self._extra_args()})

    def _cuenta_extras(self, resumen: dict | None, extras: list) -> dict | None:
        """
        Qué se borra: lo que robocopy lista como EXTRA. Su resumen cuenta también las carpetas omitidas
        con /XD que hay en el destino (y esas no las borra); se usa solo si no lista los nombres.
        """
        if self._lista_completa():
            return contar_extras(extras)
        return resumen

    def _anotar_borrados(self, texto: str, final: bool = False):
        partes = re.split(r"\r\n|\n|\r", self._linea_borrados + texto)
        self._linea_borrados = "" if final else partes.pop()
        self._borrados += leer_extras_robocopy("\n".join(partes))

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
        """
        Pasada rápida sin copiar nada (/L): solo el resumen con los totales. Si la copia borra
        (/MIR, /PURGE) también lista los nombres, para enseñar qué se borraría antes de hacerlo.
        """
        args = self._base_args(extra_xd)
        args += ["/L"] + ([] if self._opcion_borrado() else ["/NFL", "/NDL"]) + ["/NJH", "/NP", "/BYTES", "/R:0", "/W:0"]
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
        self._borra = self._opcion_borrado()
        self._final_salida = self._linea_borrados = ""
        self._borrados = []
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
        # Con /MIR o /PURGE siempre se calcula antes (aunque no pidas el %): hay que saber qué se borraría
        self._t_calculo = None
        if self._con_progreso() or (self._borra and not self.chk_simular.isChecked()):
            self._fase = "calculo"
            self._t_calculo = time.monotonic()      # al acabar el cálculo pasa a ser su duración
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
        self._final_salida = (self._final_salida + texto)[-8000:]
        if self._borra:
            self._anotar_borrados(texto)
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
                self._final_salida = (self._final_salida + resto)[-8000:]
                if self._borra:
                    self._anotar_borrados(resto)
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
            simulado = self.chk_simular.isChecked()
            borrado = None
            if self._borra:
                self._anotar_borrados("", final=True)
                borrado = self._cuenta_extras(leer_resumen_robocopy(self._final_salida), self._borrados)
            n_borrados = borrado["archivos_extra"] + borrado["carpetas_extra"] if borrado and not simulado else None
            tipo, texto = describir_codigo_robocopy(codigo, self._borra, simulado, n_borrados)
            self.consola.agregar(texto, tipo)
            self.estado("Terminado." if tipo != "error" else "Terminó con errores.")
            self.salio_bien = tipo != "error"
            # La tabla de robocopy, ordenada y con cómo queda el destino (con /NJS robocopy no la escribe)
            tabla = leer_tabla_robocopy(self._final_salida)
            if tabla is not None:
                lineas, avisos = resumen_robocopy(
                    tabla, simulado, self._borra,
                    borrado["carpetas_extra"] if borrado and self._lista_completa() else None,
                    hay_exclusiones=bool(self.lista_carpetas.activos() or self.lista_archivos.activos()))
                self.consola.agregar_lineas(lineas, "Resumen:")
                for tipo_aviso, aviso in avisos:
                    self.consola.agregar(aviso, tipo_aviso)
                tiempos = leer_tiempos_robocopy(self._final_salida)
                if tiempos is not None:
                    self.consola.agregar_lineas(tabla_tiempos_robocopy(
                        tiempos, simulado, (tabla["bytes"] or {}).get("copiado"), self._t_calculo), "Tiempos:")
                self._resumen_final(mostrar=False)
            else:
                if self._borra and not simulado:
                    self._resumen_borrado(borrado)
                self._resumen_final()
        self._fin()

    @staticmethod
    def _texto_extras(t: dict) -> str:
        partes = []
        if t["archivos_extra"]:
            tam = f" ({formatear_bytes(t['bytes_extra'])})" if t.get("bytes_extra") else ""
            partes.append(f"{t['archivos_extra']:,} archivo(s){tam}")
        if t["carpetas_extra"]:
            partes.append(f"{t['carpetas_extra']:,} carpeta(s)")
        return " y ".join(partes)

    def _resumen_borrado(self, t: dict | None):
        """Lo que robocopy borró del destino (sus líneas «*EXTRA», o su resumen si no las escribió)."""
        if t is None:
            self.consola.agregar(f"No se pudo leer cuánto borró {self._borra}: revisa las líneas «*EXTRA» del "
                                 "registro.", "aviso")
        elif t["archivos_extra"] or t["carpetas_extra"]:
            self.consola.agregar(f"🗑 Borrado del destino ({self._borra}): {self._texto_extras(t)} que ya no estaban "
                                 "en el origen.", "aviso")
        else:
            self.consola.agregar(f"{self._borra}: no hubo nada que borrar en el destino.", "suave")

    def _calculo_listo(self, codigo: int):
        self._t_calculo = time.monotonic() - self._t_calculo
        salida = "".join(self._salida_calculo)
        self._totales = leer_resumen_robocopy(salida)
        if codigo >= 16 or self._totales is None or self._totales["bytes"] is None:
            self.consola.agregar("No se pudo calcular el total; se copiará sin porcentaje.", "aviso")
            self._totales = None
        else:
            t = self._totales
            texto = f"Hay que copiar {t['archivos']:,} archivos ({formatear_bytes(t['bytes'])})"
            if t["omitidos"]:
                texto += f"; {t['omitidos']:,} ya están iguales en el destino y se saltan"
            if self._borra:
                extras = self._texto_extras(self._cuenta_extras(t, leer_extras_robocopy(salida)))
                if extras:
                    texto += (f". Además se BORRARÁN del destino {extras} que ya no están en el origen "
                              f"({self._borra})")
            else:
                extras = self._texto_extras(t)
                if extras:
                    texto += f". En el destino hay {extras} que no están en el origen: no se tocan"
            self.consola.agregar(texto + ".", "aviso" if self._borra and extras else "ok")
        if self._borra and not self._confirmar_borrado(self._totales, leer_extras_robocopy(salida)):
            self.consola.agregar(f"No se copió ni se borró nada: cancelaste la copia con {self._borra}.", "aviso")
            self.estado("Cancelado.")
            self.salio_bien = False
            self._fin()
            return
        self._arrancar_copia()

    def _confirmar_borrado(self, resumen: dict | None, extras: list[tuple[str, int]]) -> bool:
        """Antes de que /MIR o /PURGE borren algo del destino: qué se va a borrar y si sigues."""
        totales = self._cuenta_extras(resumen, extras) if resumen is not None else None
        if totales is not None and not totales["archivos_extra"] and not totales["carpetas_extra"]:
            return True                         # no hay nada que borrar
        for ruta, _ in extras[:40]:
            self.consola.agregar(f"   se borraría: {ruta}", "aviso")
        if len(extras) > 40:
            self.consola.agregar(f"   … y {len(extras) - 40:,} más.", "aviso")
        if self.sin_dialogos:
            return True
        destino = self.destino_efectivo()
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Icon.Warning)
        caja.setWindowTitle(APP_NOMBRE)
        if totales is None:
            caja.setText(f"No se pudo calcular qué borraría {self._borra} en:\n{destino}\n\n"
                         f"{self._borra} BORRA del destino todo lo que no esté en el origen. Si no estás seguro, "
                         "cancela y prueba antes con «Solo simular (/L)».")
        else:
            caja.setText(f"{self._borra} va a BORRAR del destino {self._texto_extras(totales)} que ya no están "
                         f"en el origen:\n{destino}\n\nNo van a la Papelera: se borran de verdad.\n\n"
                         "¿Copiar y borrarlos?")
            if extras:
                caja.setInformativeText("La lista completa está en «Mostrar detalles…» y en el registro.")
                caja.setDetailedText("\n".join(ruta for ruta, _ in extras[:5000])
                                     + (f"\n… y {len(extras) - 5000:,} más" if len(extras) > 5000 else ""))
        si = caja.addButton("Copiar y borrar", QMessageBox.ButtonRole.DestructiveRole)
        no = caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caja.setDefaultButton(no)
        caja.exec()
        return caja.clickedButton() is si

    def _resumen_final(self, mostrar: bool = True):
        """mostrar=False: solo cierra el avance (los tiempos ya salen en la tabla de tiempos)."""
        if self._progreso is None or self.chk_simular.isChecked():
            return
        self._progreso.terminar()
        if not mostrar:
            return
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

def tarea_info(t: Tarea, usa_global: bool, venv: str, conda: bool = False, exportar_yml: bool = False) -> dict:
    exe, carpeta = resolver_python(t, usa_global, venv)
    t.log(f"Python: {exe}", "titulo")
    datos = leer_entorno(t, exe, "info")
    t.log(f"Versión: {datos['version'].split()[0]} | {len(datos['paquetes'])} paquetes")

    # En conda, «pip freeze» escribe «numpy @ file:///C:/b/abs_…» para lo instalado con conda;
    # «pip list --format=freeze» da paquete==versión, que sí se puede reinstalar
    comando = ["pip", "list", "--format=freeze"] if conda else ["pip", "freeze"]
    t.log(f"Ejecutando {' '.join(comando)}…", "suave")
    freeze, fuente = "", " ".join(comando)
    try:
        r = ejecutar_cancelable(t, [str(exe), "-m"] + comando, timeout=300)
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

    yml = None
    if conda and exportar_yml:
        programa = conda_ejecutable(Path(carpeta))
        if programa is None:
            t.log("No encontré conda.exe: no se generó el environment.yml.", "aviso")
        else:
            t.log(f"Ejecutando conda env export ({programa})…", "suave")
            try:
                r = ejecutar_cancelable(t, [programa, "env", "export", "-p", str(carpeta), "--no-builds"], timeout=300)
                if r.returncode == 0 and r.stdout.strip():
                    yml = r.stdout.replace("\r\n", "\n")
                else:
                    ultima = ((r.stderr or r.stdout).strip().splitlines() or ["sin salida"])[-1]
                    t.log(f"conda env export falló: {ultima}", "aviso")
            except (OSError, TimeoutError) as e:
                t.log(f"No se pudo ejecutar conda env export ({e}).", "aviso")

    datos.update({"exe": str(exe), "carpeta_venv": str(carpeta) if carpeta else None,
                  "freeze": freeze, "fuente": fuente, "conda": conda, "environment_yml": yml})
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
        self.chk_yml = QCheckBox("Conda: guardar también environment.yml (conda env export)")
        self.chk_yml.setToolTip("Con él se recrea el entorno completo: conda env create -f environment_<entorno>.yml")
        self.chk_yml.setChecked(True)
        lay.addWidget(self.chk_yml)
        lay.addWidget(etiqueta("CARPETA"))
        self.carpeta_salida = SelectorRuta(
            "carpeta", "Predeterminado: la carpeta del venv · el Escritorio si es de conda o el Python global")
        lay.addWidget(self.carpeta_salida)
        lay.addWidget(etiqueta("NOMBRE"))
        self.nombre_salida = QLineEdit("requirements.txt")
        self.nombre_salida.setToolTip("En conda, si lo dejas así se guarda como requirements_<entorno>.txt")
        lay.addWidget(self.nombre_salida)
        self.cuerpo.addWidget(card)
        self.selector.cambiado.connect(lambda: self.chk_yml.setEnabled(self.selector.es_conda()))
        self.chk_yml.setEnabled(self.selector.es_conda())

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
        conda = self.selector.es_conda()
        self.lanzar(tarea_info, (self.selector.usa_global(), self.selector.venv(), conda,
                                 conda and self.chk_yml.isChecked()),
                    self._listo, "Analizando entorno…")

    def _listo(self, d: dict):
        self._datos = d
        es_venv = d["prefix"] != d["base_prefix"]
        self.lbl_version.setText(d["version"].split()[0])
        self.lbl_exe.setText(d["exe"])
        if d.get("conda"):
            entorno = next((e for e in detectar_entornos_conda() if norm(e["ruta"]) == norm(d["carpeta_venv"])), None)
            self.lbl_tipo.setText("Entorno de conda" + (f" ({entorno['distribucion']})" if entorno else ""))
        else:
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
        nombre = self.nombre_salida.text().strip() or "requirements.txt"
        if d.get("conda") or not d.get("carpeta_venv"):
            # Conda y el Python global: al Escritorio, con el nombre del entorno para que varios no se pisen
            entorno = (nombre_entorno_conda(d["carpeta_venv"]) if d.get("conda")
                       else nombre_python_global(d.get("version")))
            carpeta = self.carpeta_salida.texto() or str(carpeta_escritorio())
            nombre = nombre_con_entorno(nombre, "requirements.txt", entorno)
        else:
            carpeta = self.carpeta_salida.texto() or d["carpeta_venv"]
        return Path(carpeta) / nombre

    def guardar(self, preguntar: bool):
        if not self._datos:
            return
        ruta = self._ruta_salida()
        archivos = [(ruta, self._datos["freeze"], self._datos["fuente"])]
        if self._datos.get("environment_yml"):
            yml = ruta.with_name(f"environment_{nombre_entorno_conda(self._datos['carpeta_venv'])}.yml")
            archivos.append((yml, self._datos["environment_yml"], "conda env export"))
        existentes = [r for r, _, _ in archivos if r.exists()]
        if preguntar and existentes:
            r = QMessageBox.question(self, APP_NOMBRE, "Ya existe:\n" + "\n".join(f"«{x}»" for x in existentes)
                                     + "\n\n¿Sobrescribir?")
            if r != QMessageBox.StandardButton.Yes:
                return
        for destino, contenido, fuente in archivos:
            try:
                destino.parent.mkdir(parents=True, exist_ok=True)
                with open(destino, "w", encoding="utf-8", newline="\r\n") as fh:
                    fh.write(normalizar_saltos(contenido))
                self.consola.agregar(f"✓ {destino.name} guardado ({fuente}) en «{destino.parent}».", "ok")
            except OSError as e:
                self.consola.agregar(f"No se pudo guardar «{destino}»: {e}", "error")


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
    "python": {"global": False, "venv": "", "conda": False, "conda_env": ""},
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

    # Conda y el Python global van al Escritorio, con el nombre del entorno («py311», «python314»)
    if cfg.get("conda") and carpeta_venv:
        entorno = nombre_entorno_conda(str(carpeta_venv))
    elif carpeta_venv is None:
        entorno = nombre_python_global(datos.get("version"))
    else:
        entorno = ""
    if cfg["solo_requeridos"]:
        if entorno:     # el que guarda «Info entorno»: requirements_<entorno>.txt en el Escritorio
            defecto = str(Path(cfg["escritorio"]) / nombre_con_entorno("requirements.txt", "requirements.txt", entorno))
        else:
            defecto = str(Path(carpeta_venv) / "requirements.txt") if carpeta_venv else ""
        req = cfg["requirements"] or defecto
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
    contenido = normalizar_saltos("\n".join(partes)).rstrip() + "\n"

    nombre = cfg["nombre_salida"] or "THIRD_PARTY_NOTICES.txt"
    if entorno:         # conda o global: al Escritorio, con el nombre del entorno
        carpeta = cfg["carpeta_salida"] or cfg["escritorio"]
        nombre = nombre_con_entorno(nombre, "THIRD_PARTY_NOTICES.txt", entorno)
    else:
        carpeta = cfg["carpeta_salida"] or str(carpeta_venv)
    salida = Path(carpeta) / nombre
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
            "carpeta", "Predeterminado: la carpeta del venv · el Escritorio si es de conda o el Python global")
        lay.addWidget(self.carpeta_salida)
        lay.addWidget(etiqueta("NOMBRE DEL ARCHIVO"))
        self.nombre_salida = QLineEdit()
        self.nombre_salida.setToolTip("En conda, si lo dejas así se guarda como THIRD_PARTY_NOTICES_<entorno>.txt")
        lay.addWidget(self.nombre_salida)
        self.cuerpo.addWidget(card)

        card, lay = tarjeta("Filtros")
        lay.addWidget(etiqueta("PAQUETES A EXCLUIR (separados por coma)"))
        self.txt_excluir = QLineEdit()
        self.txt_excluir.setPlaceholderText("ej. pip, setuptools, wheel")
        lay.addWidget(self.txt_excluir)
        self.chk_req = QCheckBox("Incluir solo los paquetes de un requirements.txt")
        lay.addWidget(self.chk_req)
        self.req = SelectorRuta("archivo", "Predeterminado: requirements.txt del venv "
                                           "(en conda, requirements_<entorno>.txt del Escritorio)",
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
        conda = self.selector.es_conda()
        cfg = {
            "global": self.selector.usa_global(),
            "venv": self.selector.venv(),
            "conda": conda,
            "escritorio": str(carpeta_escritorio()) if conda or self.selector.usa_global() else "",
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


def script_firma_archivo(ruta: str, internos: list[str] | None = None, firma_msix: str | None = None) -> str:
    """
    Firma digital y SHA256 de un archivo descargado (Get-AuthenticodeSignature y Get-FileHash).
    internos: instaladores sacados de un .zip/.nupkg (el comprimido en sí no lleva firma).
    firma_msix: la firma PKCS#7 de un .msix/.msixbundle, que Get-AuthenticodeSignature no sabe leer:
    se comprueba con SignedCms y la cadena del certificado.
    """
    script = ("$f = " + ps_texto(ruta) + "; "
              "$s = Get-AuthenticodeSignature -LiteralPath $f; "
              "$r = [ordered]@{ Estado = [string]$s.Status; "
              "Firmante = if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { $null }; "
              "Emisor = if ($s.SignerCertificate) { $s.SignerCertificate.Issuer } else { $null }; "
              "SelloDeTiempo = [bool]$s.TimeStamperCertificate; "
              "Sha256 = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash }; ")
    if internos:
        script += ("$r.Internos = @(foreach ($x in @(" + ", ".join(ps_texto(x) for x in internos) + ")) { "
                   "$i = Get-AuthenticodeSignature -LiteralPath $x; [ordered]@{ Estado = [string]$i.Status; "
                   "Firmante = if ($i.SignerCertificate) { $i.SignerCertificate.Subject } else { $null } } }); ")
    if firma_msix:
        # Microsoft firma sus MSIX con certificados de pocos días: si ya venció, la firma vale por su sello
        # de tiempo (como en Authenticode) y la cadena se comprueba en la fecha del sello
        script += ("try { Add-Type -AssemblyName System.Security; "
                   "$cms = New-Object System.Security.Cryptography.Pkcs.SignedCms; "
                   "$cms.Decode([IO.File]::ReadAllBytes(" + ps_texto(firma_msix) + ")); "
                   "$cms.CheckSignature($true); $si = $cms.SignerInfos[0]; $c = $si.Certificate; "
                   "$cadena = { param($cuando) $ch = New-Object System.Security.Cryptography.X509Certificates.X509Chain; "
                   "$ch.ChainPolicy.RevocationMode = 'NoCheck'; $ch.ChainPolicy.ExtraStore.AddRange($cms.Certificates); "
                   "if ($cuando) { $ch.ChainPolicy.VerificationTime = $cuando }; "
                   "@($ch.Build($c), @($ch.ChainStatus | ForEach-Object { [string]$_.Status })) }; "
                   "$ok, $fallas = & $cadena $null; $sello = $null; "
                   "if (-not $ok -and -not ($fallas | Where-Object { $_ -notin 'NotTimeValid', 'NotTimeNested' })) { "
                   "try { $ts = $si.UnsignedAttributes | Where-Object { $_.Oid.Value -eq '1.3.6.1.4.1.311.3.3.1' } "
                   "| Select-Object -First 1; "
                   "if ($ts) { $tok = New-Object System.Security.Cryptography.Pkcs.SignedCms; "
                   "$tok.Decode($ts.Values[0].RawData); $tok.CheckSignature($true); "
                   "$st = $tok.SignerInfos[0].SignedAttributes | Where-Object { $_.Oid.Value -eq '1.2.840.113549.1.9.5' } "
                   "| Select-Object -First 1; if ($st) { $sello = [System.Security.Cryptography.Pkcs.Pkcs9SigningTime]::new("
                   "$st.Values[0].RawData).SigningTime } "
                   # Si el sello no trae «signingTime», su fecha es el genTime (GeneralizedTime) de su TSTInfo
                   "else { $b = $tok.ContentInfo.Content; for ($i = 0; $i -lt $b.Length - 17; $i++) { "
                   "if ($b[$i] -eq 0x18 -and $b[$i + 1] -ge 15 -and $b[$i + 1] -le 23 -and "
                   "$i + 2 + $b[$i + 1] -le $b.Length) { "
                   "$t = [Text.Encoding]::ASCII.GetString($b, $i + 2, $b[$i + 1]); "
                   "if ($t -match '^(\\d{14})(\\.\\d+)?Z$') { $sello = [datetime]::ParseExact($matches[1], 'yyyyMMddHHmmss', "
                   "[Globalization.CultureInfo]::InvariantCulture, 'AssumeUniversal, AdjustToUniversal'); break } } } }; "
                   "if ($sello) { $ok, $fallas = & $cadena $sello } } } "
                   "catch { $fallas = @($fallas) + ('sello de tiempo: ' + $_.Exception.Message) } }; "
                   "$r.Msix = [ordered]@{ Estado = $(if ($ok) { 'Valid' } else { 'NotTrusted' }); "
                   "Firmante = $c.Subject; Emisor = $c.Issuer; Sello = $(if ($sello) { $sello.ToString('yyyy-MM-dd') } "
                   "else { $null }); Fallas = ($fallas -join ', ') } } "
                   "catch { $r.Msix = [ordered]@{ Estado = 'Invalid'; Motivo = $_.Exception.Message } }; ")
    return script + "'" + MARCA_JSON + "' + ($r | ConvertTo-Json -Compress -Depth 4)"


EXT_PAQUETE_MSIX = (".msix", ".msixbundle", ".appx", ".appxbundle")
EXT_COMPRIMIDOS = (".zip", ".nupkg")
EXT_INSTALADORES = (".exe", ".msi", ".msp")


def preparar_revision_interna(archivo: Path, carpeta: Path) -> dict:
    """
    Lo que Get-AuthenticodeSignature no puede revisar directamente (corre en otro hilo):
    · .zip / .nupkg: saca los instaladores de dentro (los 8 más grandes, sin las rutas del comprimido:
      nada sale de la carpeta temporal) → {"internos": [(ruta temporal, nombre dentro del comprimido)]}
    · .msix / .msixbundle: saca su firma (AppxSignature.p7x sin la cabecera «PKCX») → {"msix": ruta}
    """
    import zipfile
    ext = archivo.suffix.lower()
    if ext in EXT_PAQUETE_MSIX:
        with zipfile.ZipFile(archivo) as z:
            datos = z.read("AppxSignature.p7x")
        if datos[:4] != b"PKCX":
            raise ValueError("AppxSignature.p7x no tiene el formato esperado")
        destino = carpeta / "_firma_msix.p7s"
        destino.write_bytes(datos[4:])
        return {"msix": str(destino)}
    if ext not in EXT_COMPRIMIDOS:
        return {}
    internos, total = [], 0
    with zipfile.ZipFile(archivo) as z:
        candidatos = sorted((i for i in z.infolist() if not i.is_dir()
                             and Path(i.filename).suffix.lower() in EXT_INSTALADORES and i.file_size < 2 << 30),
                            key=lambda i: i.file_size, reverse=True)
        salida = carpeta / "_contenido"
        salida.mkdir(exist_ok=True)
        for n, info in enumerate(candidatos[:8]):
            total += info.file_size
            if total > 3 << 30:
                break
            nombre = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(info.filename).name)
            destino = salida / f"{n}_{nombre}"
            with z.open(info) as origen, open(destino, "wb") as fh:
                shutil.copyfileobj(origen, fh, 1 << 20)
            internos.append((str(destino), info.filename))
    return {"internos": internos}


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


# Al reabrir como administrador: la copia nueva va directo a Actualizaciones y vuelve a buscar
ARG_REABIERTO = "--actualizaciones"


def comando_de_la_app() -> tuple[str, list[str]]:
    """(programa, argumentos) para abrir otra copia de esta app, igual que se abrió esta."""
    args = [a for a in sys.argv[1:] if a not in (ARG_REABIERTO, "--autoprueba") and not a.startswith(ARG_ACTUALIZACION)]
    if getattr(sys, "frozen", False):                  # PyInstaller (también onefile)
        return sys.executable, args
    if "__compiled__" in globals():                    # Nuitka: argv[0] es el .exe real, no el extraído
        return str(Path(sys.argv[0]).resolve()), args
    python = Path(sys.executable)
    sin_consola = python.with_name("pythonw.exe")      # desde el código fuente, sin ventana de consola
    if python.name.lower() == "python.exe" and sin_consola.is_file():
        python = sin_consola
    return str(python), [str(Path(__file__).resolve())] + args


def reabrir_como_administrador() -> tuple[bool, str]:
    """
    Abre otra copia de la app con permisos de administrador (Windows muestra su aviso UAC).
    Devuelve (se abrió, motivo si no).
    """
    if not ES_WINDOWS:
        return False, "Solo funciona en Windows."
    import ctypes
    programa, args = comando_de_la_app()
    try:
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", programa, subprocess.list2cmdline(args + [ARG_REABIERTO]),
                                                str(carpeta_app()), 1)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    if r > 32:
        return True, ""
    if r == 5:      # SE_ERR_ACCESSDENIED: se rechazó el aviso de Windows
        return False, "No se dio el permiso de administrador en el aviso de Windows."
    return False, f"Windows no pudo abrirla (código {r})."


def comando_visible(args: list[str]) -> str:
    """Cómo se escribiría en PowerShell (sin comillas si no hacen falta)."""
    return "winget " + " ".join(a if re.fullmatch(r"[\w.:+\-/<>=@]+", a) else ps_texto(a) for a in args)


def codigo_hex(codigo: int) -> str:
    return f"0x{codigo & 0xFFFFFFFF:08X}"


# Códigos de salida de winget (los mismos nombres que muestra «winget error <código>»)
CODIGOS_WINGET = {
    0x8A150006: ("error", "El instalador del programa terminó con error (o no se pudo abrir: aviso de permisos "
                          "de Windows rechazado, o bloqueado por el antivirus)."),
    0x8A150008: ("error", "No se pudo descargar el instalador (revisa tu conexión)."),
    0x8A150010: ("error", "No hay un instalador compatible con este equipo."),
    0x8A150011: ("error", "El SHA256 del instalador NO coincide con el manifiesto: winget lo bloqueó por seguridad."),
    0x8A150014: ("error", "No se encontró el paquete en el origen."),
    0x8A150019: ("error", "Necesita permisos de administrador."),
    0x8A15002B: ("aviso", "No hay una actualización aplicable (puede que ya esté al día o que el instalador cambió)."),
    0x8A15002D: ("error", "El instalador no pasó la comprobación de seguridad del antivirus."),
    0x8A150041: ("error", "No se aceptaron los acuerdos del paquete."),
    0x8A15005E: ("error", "El certificado del servidor no es el que se esperaba: un antivirus o un proxy está "
                          "inspeccionando tus conexiones HTTPS (en la tarjeta «Seguridad» puedes permitirlo)."),
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


RE_SALIDA_INSTALADOR = re.compile(r"(c[oó]digo de salida|exit code)\s*:?\s*(-?\d+)", re.I)


def codigo_salida_instalador(texto: str) -> int | None:
    """El código con el que terminó el instalador, si winget lo escribió (ej. «…con el código de salida: 2»)."""
    m = None
    for m in RE_SALIDA_INSTALADOR.finditer(texto or ""):
        pass
    return int(m.group(2)) if m else None


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
RE_HASH_OK = re.compile(r"hash.*(verif|validat)|(verif|validat).*hash", re.I)    # «verificó» y «verified»
RE_SOLO_GIRO = re.compile(r"^\s*[-\\|/]?\s*$")
RE_TAMANOS = re.compile(r"([\d.,]+\s*[KMG]?B)\s*/\s*([\d.,]+\s*[KMG]?B)")
# Saltos de línea y redibujos (\r suelto, o la secuencia de consola «volver a la columna 1»)
RE_FIN_DE_LINEA = re.compile(r"(\r\n|\n|\r|\x1b\[\d*G)")
RE_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
RE_PORCENTAJE = re.compile(r"(\d{1,3})\s*%")
RE_UN_TAMANO = re.compile(r"([\d.,]+)\s*([KMG]?B)", re.I)
# Fases de «winget upgrade» (español e inglés)
RE_FASE_DESCARGA = re.compile(r"^\s*(descargando|downloading)\b.*?(https?://\S+)", re.I)
RE_FASE_INSTALA = re.compile(r"(inici\w*|start\w*)\b.*(instal|install)", re.I)
RE_FASE_EXTRAE = re.compile(r"\b(extray\w*|extract\w*)\b", re.I)
RE_FASE_LISTO = re.compile(r"(instalad[oa]|install\w*)\s+(correctamente|successfully)|"
                           r"successfully\s+install", re.I)


def bytes_de(texto: str) -> float | None:
    """«12,5 MB» → bytes (winget usa punto o coma según el idioma)."""
    m = RE_UN_TAMANO.search(texto)
    if not m:
        return None
    try:
        numero = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    return numero * {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[m.group(2).upper()]


def leer_barra_winget(texto: str) -> tuple[float, float | None, float | None] | None:
    """
    De un redibujo de la barra de winget: (fracción 0‒1, bytes hechos, bytes totales).
    «█████▒▒▒  12.0 MB / 30.5 MB» o «█████▒▒▒  45%». None si no es una barra.
    """
    texto = RE_ANSI.sub("", texto)
    m = RE_TAMANOS.search(texto)
    if m:
        hecho, total = bytes_de(m.group(1)), bytes_de(m.group(2))
        if hecho is not None and total:
            return min(hecho / total, 1.0), hecho, total
    m = RE_PORCENTAJE.search(texto)
    if m and ("█" in texto or "▒" in texto):
        return min(int(m.group(1)), 100) / 100, None, None
    return None


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
    info = {"sha256": None, "url": None, "editor": None, "version": None, "tipo_instalador": None}
    for linea in lineas:
        m = re.match(r"^\s*(tipo de instalador|installer type)\s*:\s*(.+)$", linea, re.I)
        if m:
            info["tipo_instalador"] = m.group(2).strip().lower()
            break
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


RE_ID_LOCAL = re.compile(r"^(ARP|MSIX)\\", re.I)
RE_ARP = re.compile(r"^ARP\\(Machine|User)\\(X64|X86|Arm64|Arm|Neutral)\\(.+)$", re.I)


def carpeta_valida(ruta: str | None) -> str | None:
    """Una carpeta de programa de verdad (no C:\\, ni Program Files, ni Windows ni el perfil completo)."""
    if not ruta:
        return None
    ruta = ruta.strip().strip('"').rstrip("\\/")
    if not RE_RUTA_WINDOWS.match(ruta + "\\") or not os.path.isdir(ruta):
        return None
    generales = {norm(x) for x in (os.environ.get("SystemRoot") or r"C:\Windows",
                                   os.environ.get("ProgramFiles") or r"C:\Program Files",
                                   os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)",
                                   os.environ.get("ProgramData") or r"C:\ProgramData",
                                   str(Path.home()), str(Path.home() / "AppData" / "Local"),
                                   str(Path.home() / "AppData" / "Local" / "Programs"),
                                   str(Path.home() / "AppData" / "Roaming"))}
    if len(Path(ruta).parts) < 2 or norm(ruta) in generales or esta_dentro(ruta, os.environ.get("SystemRoot") or r"C:\Windows"):
        return None
    return ruta


def carpeta_de_arp(id_local: str | None) -> str | None:
    """
    Carpeta del programa según su entrada de «Programas y características» (ARP), cuando winget no
    trae «Ubicación instalada» (le pasa a OBS): InstallLocation, o la carpeta del icono o del desinstalador.
    """
    m = RE_ARP.match(id_local or "")
    if not m or not ES_WINDOWS:
        return None
    import winreg
    ambito, arquitectura, clave = m.groups()
    if ambito.lower() == "user":
        raiz, ruta, vista = winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0
    else:
        raiz, ruta = winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        vista = winreg.KEY_WOW64_32KEY if arquitectura.lower() == "x86" else winreg.KEY_WOW64_64KEY
    try:
        with winreg.OpenKey(raiz, ruta + "\\" + clave, 0, winreg.KEY_READ | vista) as k:
            valores = {}
            for nombre in ("InstallLocation", "DisplayIcon", "UninstallString"):
                try:
                    valores[nombre] = str(winreg.QueryValueEx(k, nombre)[0])
                except OSError:
                    pass
    except OSError:
        return None
    if carpeta_valida(valores.get("InstallLocation")):
        return carpeta_valida(valores["InstallLocation"])
    carpetas = []
    for nombre in ("UninstallString", "DisplayIcon"):
        texto = valores.get(nombre) or ""
        m = re.match(r'\s*"([^"]+)"', texto) or re.match(r"\s*([A-Za-z]:\\.+?\.(?:exe|ico|dll))\b", texto, re.I)
        if m and carpeta_valida(os.path.dirname(m.group(1).split(",")[0])):
            carpetas.append(carpeta_valida(os.path.dirname(m.group(1).split(",")[0])))
    if len(carpetas) == 2:
        # OBS: icono en …\obs-studio\bin\64bit y desinstalador en …\obs-studio: vale la carpeta común
        try:
            comun = carpeta_valida(os.path.commonpath(carpetas))
        except ValueError:
            comun = None
        if comun:
            return comun
    return carpetas[0] if carpetas else None


def leer_detalles_instalado(texto: str) -> dict:
    """
    De «winget list --id X --exact --details»: carpeta, tipo de instalador, identificador local,
    ámbito (machine/user) y arquitectura.
    """
    d = {"ubicacion": leer_ubicacion_instalada(texto), "categoria": None, "local": None, "ambito": None,
         "arquitectura": None}
    for linea in texto.splitlines():
        etiqueta, sep, valor = linea.partition(": ")
        valor = valor.strip()
        if not sep or not valor:
            continue
        if RE_ID_LOCAL.match(valor):
            d["local"] = valor
        e = etiqueta.strip().lower()
        if ("categor" in e and "instal" in e) or e in ("installer category", "installer type"):
            d["categoria"] = valor.lower()
        elif "mbito" in e or "scope" in e:
            d["ambito"] = valor.lower()
        elif "arquitectura" in e or "architecture" in e:
            d["arquitectura"] = valor.lower()
    d["carpeta"] = carpeta_valida(d["ubicacion"]) or carpeta_de_arp(d["local"])
    return d


# ─── Manifiesto del instalador (winget-pkgs) ────────────────────────────────
# «winget show» no dice cómo actualiza cada instalador. El manifiesto de winget-pkgs sí: con
# «UpgradeBehavior: uninstallPrevious» winget DESINSTALA primero la versión que tienes y luego
# instala la nueva; si la nueva falla, te quedas sin el programa (le pasó a Miniforge).
_CACHE_MANIFIESTOS: dict = {}


def leer_manifiesto_instalador(texto: str) -> dict:
    """
    Lo que importa de un manifiesto de instalador (YAML de winget-pkgs), sin depender de PyYAML:
    {"general": {clave: valor}, "instaladores": [{clave: valor}], "comandos": [...]}.
    """
    general, instaladores, comandos = {}, [], []
    seccion, actual, sangria_item, guion = None, None, 0, None
    for linea in texto.splitlines():
        contenido = linea.strip()
        if not contenido or contenido.startswith("#"):
            continue
        sangria = len(linea) - len(linea.lstrip(" "))
        if contenido.startswith("- "):
            if seccion == "Commands" and sangria <= 2:
                comandos.append(contenido[2:].strip().strip("'\""))
                continue
            if seccion != "Installers":
                continue
            if guion is None:
                guion = sangria                   # la sangría de los «- » de la lista de instaladores
            if sangria != guion:
                continue                          # una lista dentro de un instalador
            actual, sangria_item = {}, guion + 2  # un instalador nuevo
            instaladores.append(actual)
            contenido, sangria = contenido[2:].strip(), sangria_item
        elif sangria == 0:
            seccion = contenido.split(":", 1)[0]
            actual = None
        m = re.match(r"([A-Za-z]+):\s*(.*)$", contenido)
        if not m or not m.group(2):
            continue
        valor = m.group(2).strip().strip("'\"")
        if sangria == 0:
            general[m.group(1)] = valor
        elif actual is not None and sangria == sangria_item:
            actual[m.group(1)] = valor
    return {"general": general, "instaladores": instaladores, "comandos": comandos}


def manifiesto_instalador(id_: str, version: str) -> dict | None:
    """El manifiesto de instalador de esa versión en winget-pkgs (GitHub). Corre en otro hilo."""
    import urllib.error
    import urllib.request
    clave = (id_.lower(), version)
    if clave in _CACHE_MANIFIESTOS:
        return _CACHE_MANIFIESTOS[clave]
    ruta = "/".join(urllib.parse.quote(x) for x in id_.split("."))
    base = (f"https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests/{id_[0].lower()}/"
            f"{ruta}/{urllib.parse.quote(version)}/")
    for archivo in (f"{id_}.installer.yaml", f"{id_}.yaml"):
        try:
            pedido = urllib.request.Request(base + urllib.parse.quote(archivo),
                                            headers={"User-Agent": f"{APP_ID}/{APP_VERSION}"})
            with urllib.request.urlopen(pedido, timeout=15) as r:
                resultado = leer_manifiesto_instalador(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        _CACHE_MANIFIESTOS[clave] = resultado
        return resultado
    _CACHE_MANIFIESTOS[clave] = None
    return None


def instaladores_aplicables(manifiesto: dict, ambito: str | None, arquitectura: str | None) -> list[dict]:
    """
    Los instaladores del manifiesto que winget podría usar para lo que tienes instalado (mismo ámbito
    y arquitectura). Cada uno con las claves generales del manifiesto ya aplicadas.
    """
    todos = [dict(manifiesto["general"], **i) for i in manifiesto["instaladores"]] or [dict(manifiesto["general"])]
    ambito = {"machine": "machine", "user": "user"}.get((ambito or "").lower())
    arquitectura = (arquitectura or "").lower() or None

    def encaja(i: dict, clave: str, valor: str | None) -> bool:
        return not valor or not i.get(clave) or i[clave].lower() in (valor, "neutral")
    elegidos = [i for i in todos if encaja(i, "Scope", ambito) and encaja(i, "Architecture", arquitectura)]
    return elegidos or todos


IDS_CONDA = ("condaforge.", "anaconda.miniconda", "anaconda.anaconda")


def es_distribucion_conda(id_: str) -> bool:
    """Miniforge, Mambaforge, Miniconda, Anaconda: su instalador trae el entorno base de conda."""
    return id_.lower().startswith(IDS_CONDA)


MOTIVO_CONDA = ("Es una distribución de conda: winget la actualiza desinstalando la anterior, y con ella se borran "
                "el entorno «base» y los entornos que estén dentro de su carpeta envs\\. Si el instalador nuevo "
                "falla, te quedas sin conda (le pasó a Miniforge). Actualízala desde conda, que no reinstala nada: "
                "conda update -n base --all")


def script_procesos_en(carpeta: str) -> str:
    """Procesos que tienen abierto un .exe o .dll de esa carpeta (ej. la cámara virtual de OBS en Chrome)."""
    return ("$u = " + ps_texto(carpeta.rstrip("\\") + "\\") + "; $yo = " + str(os.getpid()) + "; "
            "$r = @(Get-Process | Where-Object { $_.Id -ne $yo } | ForEach-Object { $p = $_; try { "
            "$m = @($p.Modules | Where-Object { $_.FileName -and "
            "$_.FileName.StartsWith($u, [StringComparison]::OrdinalIgnoreCase) } | Select-Object -First 1); "
            "if ($m.Count) { [ordered]@{ Nombre = $p.ProcessName; Id = $p.Id; Sesion = $p.SessionId; "
            "Descripcion = $(try { $p.Description } catch { $null }); Titulo = $p.MainWindowTitle; "
            "Archivo = $m[0].ModuleName } } } catch {} }); "
            "'" + MARCA_JSON + "' + (ConvertTo-Json -InputObject $r -Compress)")


def agrupar_procesos(procesos: list) -> list[tuple[str, int, str]]:
    """[(nombre visible, cuántos procesos, archivo que tienen abierto)], el más numeroso primero."""
    grupos: dict[str, list] = {}
    for x in procesos or []:
        if not isinstance(x, dict):
            continue
        nombre = (x.get("Descripcion") or x.get("Nombre") or "?").strip()
        grupos.setdefault(nombre, []).append(x)
    return sorted(((n, len(xs), xs[0].get("Archivo") or "") for n, xs in grupos.items()), key=lambda g: (-g[1], g[0]))


# Nunca se finalizan desde Actualizaciones: Windows los necesita, o los vuelve a abrir al momento (el
# Explorador recarga la extensión de 7-Zip en cuanto lo usas; el instalador la reemplaza al reiniciar)
PROCESOS_PROTEGIDOS = frozenset({
    "system", "idle", "registry", "memory compression", "secure system", "smss", "csrss", "wininit", "winlogon",
    "services", "lsass", "lsaiso", "svchost", "dwm", "fontdrvhost", "explorer", "sihost", "ctfmon", "taskhostw",
    "runtimebroker", "dllhost", "conhost", "audiodg", "spoolsv", "searchhost", "searchindexer",
    "startmenuexperiencehost", "shellexperiencehost", "textinputhost", "lockapp", "userinit", "winget",
    "windowspackagemanagerserver", "appinstallercli", "msiexec", "trustedinstaller", "tiworker",
    "msmpeng", "nissrv", "securityhealthservice", "securityhealthsystray", "mpdefendercoreservice",
})


def separar_finalizables(procesos: list) -> tuple[list[dict], list[dict]]:
    """
    (los que se pueden finalizar, los que no). No se tocan los de Windows (PROCESOS_PROTEGIDOS) ni los
    servicios (sesión 0): el instalador detiene sus propios servicios.
    """
    si, no = [], []
    for x in procesos or []:
        if not isinstance(x, dict) or not x.get("Id"):
            continue
        protegido = (str(x.get("Nombre") or "").lower() in PROCESOS_PROTEGIDOS or x.get("Sesion") == 0
                     or x.get("Id") == os.getpid())
        (no if protegido else si).append(x)
    return si, no


def script_finalizar_procesos(procesos: list[dict], espera: int = 10) -> str:
    """
    Pide a cada proceso que se cierre (como pulsar la X: un navegador guarda sus pestañas) y, si sigue
    abierto pasados `espera` segundos, lo finaliza (Stop-Process -Force). Solo toca el proceso si su Id
    sigue siendo del mismo programa. Devuelve [{Id, Nombre, Resultado: cerrado|finalizado|error, Error}].
    """
    lista = json.dumps([{"Id": int(x["Id"]), "Nombre": str(x.get("Nombre") or "")} for x in procesos])
    # Sin @(): en PowerShell 5.1, ConvertFrom-Json entrega la lista entera como un solo objeto
    return ("$o = ConvertFrom-Json " + ps_texto(lista) + "; "
            "function Vivo($x) { $p = Get-Process -Id $x.Id -ErrorAction SilentlyContinue; "
            "if ($p -and $p.ProcessName -eq $x.Nombre) { $p } else { $null } }; "
            "$pedido = $false; foreach ($x in $o) { $p = Vivo $x; if ($p -and $p.MainWindowHandle -ne 0) { "
            "try { [void]$p.CloseMainWindow(); $pedido = $true } catch {} } }; "
            "$fin = (Get-Date).AddSeconds($(if ($pedido) { " + str(int(espera)) + " } else { 0 })); "
            "while ((Get-Date) -lt $fin -and @($o | Where-Object { Vivo $_ }).Count) { Start-Sleep -Milliseconds 300 }; "
            "$r = @(foreach ($x in $o) { $p = Vivo $x; "
            "if (-not $p) { [ordered]@{ Id = $x.Id; Nombre = $x.Nombre; Resultado = 'cerrado' }; continue }; "
            "try { Stop-Process -Id $x.Id -Force -ErrorAction Stop; "
            "[ordered]@{ Id = $x.Id; Nombre = $x.Nombre; Resultado = 'finalizado' } } "
            "catch { [ordered]@{ Id = $x.Id; Nombre = $x.Nombre; Resultado = 'error'; Error = $_.Exception.Message } } }); "
            "Start-Sleep -Milliseconds 500; "
            "'" + MARCA_JSON + "' + (ConvertTo-Json -InputObject $r -Compress)")


def resumir_finalizados(resultado: list) -> tuple[list[str], list[str]]:
    """(«Chrome (3 procesos)»… que se cerraron, «nombre: motivo»… que no se pudieron finalizar)."""
    cerrados: dict[str, int] = {}
    fallos = []
    for x in resultado or []:
        if not isinstance(x, dict):
            continue
        if x.get("Resultado") in ("cerrado", "finalizado"):
            cerrados[x.get("Nombre") or "?"] = cerrados.get(x.get("Nombre") or "?", 0) + 1
        else:
            motivo = str(x.get("Error") or "no se pudo").strip().rstrip(".")
            fallos.append(f"{x.get('Nombre') or '?'} ({x.get('Id')}): {motivo}")
    return [n + (f" ({c} procesos)" if c > 1 else "") for n, c in cerrados.items()], fallos


# Tipos de instalador: winget no puede pasar un programa de MSIX (Store) a MSI/EXE ni al revés.
# Entre EXE y MSI a veces sí puede (7-Zip figura como EXE y se actualiza con su MSI), así que eso no se avisa.
TIPOS_MSIX = {"msix", "appx"}


def tipo_base(tipo: str | None) -> str:
    """«exe (zip)» → «exe»."""
    return (tipo or "").split("(")[0].strip().lower()


def motivo_no_aplicable(categoria: str | None, tipo: str | None, id_: str, seguro: bool) -> str | None:
    """
    Por qué winget no puede actualizarlo (0x8A15002B), si se ve en los tipos de instalador.
    seguro=False: winget ya dijo «no aplicable» y solo se explica la causa más probable.
    """
    a, b = tipo_base(categoria), tipo_base(tipo)
    if not a or not b or a == b:
        return None
    nombres = {"msix": "MSIX (Microsoft Store)", "appx": "MSIX (Microsoft Store)", "msi": "MSI", "wix": "MSI",
               "exe": "EXE", "inno": "EXE", "nullsoft": "EXE", "burn": "EXE", "portable": "portable"}
    if (a in TIPOS_MSIX) != (b in TIPOS_MSIX):
        texto = f"Está instalado como {nombres.get(a, a)} y winget solo ofrece {nombres.get(b, b)}: winget no puede cambiar de uno a otro."
    elif seguro or nombres.get(a, a) == nombres.get(b, b):
        return None
    else:
        texto = (f"Está instalado como {nombres.get(a, a)} y winget ofrece {nombres.get(b, b)}: probablemente por eso "
                 "no lo reconoce como actualización.")
    if id_.lower() == "microsoft.edge":
        consejo = "Edge se actualiza solo (edge://settings/help): puedes ignorarlo aquí."
    elif a in TIPOS_MSIX:
        consejo = "Actualízalo desde la Microsoft Store, o desinstálalo e instala la versión de winget."
    else:
        consejo = "Actualízalo desde el propio programa o la web del fabricante, o ignóralo aquí."
    return f"{texto} {consejo}"


# ¿Alguien abre las conexiones HTTPS por el camino? (inspección HTTPS de un antivirus o un proxy)
HOSTS_TLS = ("storeedgefd.dsx.mp.microsoft.com", "cdn.winget.microsoft.com")
SCRIPT_TLS = (
    "$r = [ordered]@{}; foreach ($h in @(" + ", ".join(ps_texto(h) for h in HOSTS_TLS) + ")) { "
    "try { $c = New-Object Net.Sockets.TcpClient; $a = $c.BeginConnect($h, 443, $null, $null); "
    "if (-not $a.AsyncWaitHandle.WaitOne(8000)) { throw 'sin respuesta' }; $c.EndConnect($a); "
    "$s = New-Object Net.Security.SslStream($c.GetStream(), $false, ({ $true })); $s.ReadTimeout = 8000; "
    "$s.AuthenticateAsClient($h); "
    "$r[$h] = ([Security.Cryptography.X509Certificates.X509Certificate2]$s.RemoteCertificate).Issuer; "
    "$s.Dispose(); $c.Close() } catch { $r[$h] = 'ERROR: ' + $_.Exception.Message } }; "
    "'" + MARCA_JSON + "' + ($r | ConvertTo-Json -Compress)"
)
INTERCEPTORES_HTTPS = {"avast": "Avast", "avg": "AVG", "kaspersky": "Kaspersky", "eset": "ESET",
                       "bitdefender": "Bitdefender", "norton": "Norton", "mcafee": "McAfee", "sophos": "Sophos",
                       "fortinet": "Fortinet", "fortigate": "Fortinet", "zscaler": "Zscaler", "netskope": "Netskope",
                       "trend micro": "Trend Micro", "webroot": "Webroot", "dr.web": "Dr.Web",
                       "check point": "Check Point", "palo alto": "Palo Alto", "cisco": "Cisco"}


# Opción de administrador de winget: acepta la Store aunque un antivirus o un proxy cambie el certificado
# (sigue comprobando que Windows confíe en él, pero ya no exige el de Microsoft)
AJUSTE_PINNING_STORE = "BypassCertificatePinningForMicrosoftStore"


def interceptor_https(emisor: str | None) -> str | None:
    """Quién firma el certificado que llega en lugar del de Microsoft, o None si es el normal."""
    if not emisor or emisor.startswith("ERROR"):
        return None
    bajo = emisor.lower()
    for clave, nombre in INTERCEPTORES_HTTPS.items():
        if re.search(r"(?<![a-z])" + re.escape(clave) + r"(?![a-z])", bajo):
            return nombre
    if "microsoft" in bajo or "digicert" in bajo:
        return None
    return "un antivirus o un proxy"


# SHA256 que GitHub calcula al subir cada archivo de una release: una segunda fuente, aparte del manifiesto
RE_GITHUB_RELEASE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/([^/?#]+)", re.I)
_CACHE_GITHUB: dict = {}


def digest_de_github(url: str | None) -> dict | None:
    """
    {repo, archivo, digest} con el SHA256 que publica GitHub para ese archivo (None si no es una release
    de GitHub). Sin cuenta, la API de GitHub permite 60 consultas por hora: se guarda lo consultado.
    """
    m = RE_GITHUB_RELEASE.match(url or "")
    if not m:
        return None
    import urllib.request
    dueno, repo, tag, archivo = (urllib.parse.unquote(x) for x in m.groups())
    clave = (dueno.lower(), repo.lower(), tag)
    if clave not in _CACHE_GITHUB:
        pedido = urllib.request.Request(
            f"https://api.github.com/repos/{dueno}/{repo}/releases/tags/{urllib.parse.quote(tag)}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": f"{APP_ID}/{APP_VERSION}"})
        with urllib.request.urlopen(pedido, timeout=15) as r:
            datos = json.load(r)
        _CACHE_GITHUB[clave] = {a.get("name"): a.get("digest") for a in datos.get("assets") or []}
    activos = _CACHE_GITHUB[clave]
    return {"repo": f"{dueno}/{repo}", "archivo": archivo, "existe": archivo in activos,
            "digest": (activos.get(archivo) or "").lower().removeprefix("sha256:") or None}


def evaluar_github(gh, sha_manifiesto: str | None) -> tuple[str, str]:
    """(tipo, texto) de comparar el SHA256 del manifiesto con el que publica GitHub."""
    if isinstance(gh, Exception):
        codigo = getattr(gh, "code", None)
        motivo = ("se pasó el límite de consultas de GitHub; prueba en una hora" if codigo in (403, 429)
                  else "la release ya no existe en GitHub" if codigo == 404 else f"{type(gh).__name__}: {gh}")
        return "info", f"No se pudo comparar con GitHub ({motivo})"
    if not gh["existe"]:
        return "aviso", f"El archivo ya no está en la release de GitHub ({gh['repo']})"
    if not gh["digest"]:
        return "info", f"GitHub no publica el SHA256 de esta release ({gh['repo']})"
    if sha_manifiesto and gh["digest"] == sha_manifiesto.lower():
        return "ok", f"SHA256 igual al que publica GitHub ({gh['repo']})"
    return "error", f"¡El SHA256 del manifiesto NO coincide con el que publica GitHub ({gh['repo']})!"


def componer_verificacion(v: dict):
    """
    Junta lo revisado (manifiesto, GitHub, tipo de instalador, firma) en el tipo y el texto de la
    columna VERIFICACIÓN. Si algo dio error, ese texto va primero.
    """
    partes = [v["manifiesto"]] if v.get("manifiesto") else []
    if v.get("github"):
        partes.append(tuple(v["github"]))
    if v.get("incompatible"):
        partes.append(("aviso", v["incompatible"]))
    partes += [tuple(x) for x in v.get("riesgos") or []]
    if v.get("firma"):
        partes.append(("aviso" if v["firma"]["tipo"] == "sin_firma" else v["firma"]["tipo"], v["firma"]["texto"]))
    v["partes"] = partes
    tipos = {t for t, _ in partes}
    v["tipo"] = "error" if "error" in tipos else "aviso" if "aviso" in tipos else ("ok" if partes else None)
    errores = [x for t, x in partes if t == "error"]
    v["texto"] = errores[0] if errores else " · ".join(x for t, x in partes if t != "info" or len(partes) == 1)


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
    msix = firma.get("Msix")
    if isinstance(msix, dict) and estado != "Valid":
        quien_msix = nombre_del_certificado(msix.get("Firmante"))
        if msix.get("Estado") == "Valid":
            sello = f", con sello de tiempo del {msix['Sello']}" if msix.get("Sello") else ""
            return "ok", f"Firma del paquete MSIX válida: {quien_msix}{sello} (Windows la vuelve a comprobar al instalar)"
        if msix.get("Estado") == "NotTrusted":
            motivo = f": {msix['Fallas']}" if msix.get("Fallas") else ""
            return "aviso", f"El paquete MSIX está firmado por un certificado no confiable ({quien_msix}{motivo})"
        return "error", "¡La firma del paquete MSIX no es válida!"
    internos = [i for i in firma.get("Internos") or [] if isinstance(i, dict)]
    if internos and estado != "Valid":
        # El comprimido no lleva firma: cuenta la del instalador de dentro (el más grande va primero)
        principal = internos[0]
        nombre = principal.get("Nombre") or "el instalador"
        malo = next((i for i in internos if i.get("Estado") == "HashMismatch"), None)
        if malo:
            return "error", f"¡La firma de «{malo.get('Nombre')}» (dentro del comprimido) no corresponde al archivo!"
        if principal.get("Estado") == "Valid":
            return "ok", f"Dentro del comprimido: «{nombre}» firmado por {nombre_del_certificado(principal.get('Firmante'))}"
        if principal.get("Estado") == "NotSigned":
            return "sin_firma", f"Dentro del comprimido, «{nombre}» no tiene firma digital"
        return "aviso", f"Dentro del comprimido, «{nombre}»: firma no confiable ({principal.get('Estado')})"
    if estado == "Valid":
        return "ok", f"Firma válida: {quien}"
    if (firma.get("Archivo") or "").lower().endswith(EXT_COMPRIMIDOS + (".7z",)) and estado in ("NotSigned", "UnknownError"):
        return "sin_firma", "Archivo comprimido sin instaladores firmados dentro"
    if estado == "NotSigned":
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
    seg["sin_pinning_store"] = ajustes.get(AJUSTE_PINNING_STORE) is True
    for clave, texto in (("LocalManifestFiles", "permite instalar desde manifiestos locales"),
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

    # 4. ¿Alguien abre las conexiones HTTPS por el camino?
    tls = datos.get("Tls") if isinstance(datos.get("Tls"), dict) else {}
    quien = next((q for q in (interceptor_https(e) for e in tls.values()) if q), None)
    protegido = ("Lo del repositorio winget sigue protegido: su catálogo va firmado por Microsoft y cada "
                 "instalador se comprueba con su SHA256.")
    if quien:
        emisor = next(e for e in tls.values() if interceptor_https(e))
        seg["https_interceptado"] = quien
        Quien = quien[0].upper() + quien[1:]
        if seg["sin_pinning_store"]:
            c.append(("aviso", f"{Quien} inspecciona tus conexiones HTTPS (pone su certificado, "
                               f"«{nombre_del_certificado(emisor)}»), y la Microsoft Store funciona igual porque "
                               f"activaste «{AJUSTE_PINNING_STORE}»: winget comprueba que Windows confíe en el "
                               "certificado, pero ya no exige el de Microsoft. " + protegido))
        else:
            # Una excepción de sitio web no basta: Avast sigue abriendo la conexión con su propio certificado
            # (solo deja de revisar el contenido), y winget compara el certificado con el de Microsoft
            en_antivirus = ("en Avast, desmarca solo «Análisis HTTPS» del Escudo web (Menú → Configuración → "
                            "Protección → Escudos principales → Escudo web); no hace falta apagar todo el escudo. "
                            "Agregar el sitio a las excepciones de Avast no basta: sigue poniendo su certificado"
                            if quien in ("Avast", "AVG") else
                            f"en {quien}, excluye storeedgefd.dsx.mp.microsoft.com de la inspección HTTPS")
            c.append(("aviso", f"{Quien} inspecciona tus conexiones HTTPS: pone su propio certificado "
                               f"(«{nombre_del_certificado(emisor)}») en lugar del de Microsoft, y winget exige el "
                               "original para la Microsoft Store (error 0x8A15005E): por eso no salen sus "
                               f"actualizaciones. {protegido} Para usar la Store: 1) permítelo en winget con el botón "
                               "«Permitir la Store con la inspección HTTPS» (como administrador), o 2) "
                               f"{en_antivirus}, o 3) actualiza esas apps desde la propia Microsoft Store."))
    elif seg["sin_pinning_store"]:
        c.append(("aviso", f"Opción de administrador «{AJUSTE_PINNING_STORE}» activada: winget no exige el "
                           "certificado de Microsoft para la Store, y ya no hay nada que inspeccione tu HTTPS. "
                           "Puedes volver a exigirlo con el botón «Volver a exigir el certificado de la Store»."))

    # 5. Permisos
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
    if es_distribucion_conda(p["id"]):
        return "manual", MOTIVO_CONDA
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


# ─── Pasos especiales de los flujos de Actualizaciones ──────────────────────

class Pausa:
    """Un flujo la cede para esperar sin trabar la ventana (ej. a que Windows Installer quede libre)."""

    def __init__(self, segundos: float):
        self.segundos = segundos


class EnHilo:
    """Un flujo la cede para correr `funcion` en otro hilo (red, zip…); recibe lo que devuelva o la excepción."""

    def __init__(self, funcion):
        self.funcion = funcion


def windows_installer_ocupado() -> bool:
    """
    True si hay una instalación MSI en curso (de Windows Update, del actualizador de otro programa…):
    Windows Installer tiene creado su mutex «_MSIExecute». Si winget lanza un MSI entonces, falla con
    0x8A150102 (error 1618 de MSI).
    """
    if not ES_WINDOWS:
        return False
    try:
        import ctypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenMutexW.restype = ctypes.c_void_p
        k.OpenMutexW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        h = k.OpenMutexW(0x00100000, False, "Global\\_MSIExecute")      # SYNCHRONIZE
        if h:
            k.CloseHandle(h)
            return True
        return ctypes.get_last_error() == 5     # existe, pero sin permiso para abrirlo: también está ocupado
    except Exception:
        return False


# ─── Descarga por adelantado ────────────────────────────────────────────────
# Antes de descargar, «winget upgrade» busca el instalador en su carpeta temporal,
# %TEMP%\WinGet\<Id>.<Versión>\<sha256>: si está y su SHA256 coincide con el del manifiesto, lo usa
# sin volver a bajarlo (y si no coincide, lo borra y descarga). Ahí se deja lo que bajó «winget download».
ADELANTO_PREPARACION = 3        # cuántos paquetes, como mucho, se preparan por delante del que se instala
RE_NOMBRE_INVALIDO = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def carpeta_temporal_winget() -> Path:
    """%TEMP%\\WinGet, con la misma carpeta temporal que usa winget (GetTempPath)."""
    if ES_WINDOWS:
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetTempPathW(1024, buf):
                return Path(buf.value) / "WinGet"
        except Exception:
            pass
    return Path(tempfile.gettempdir()) / "WinGet"


def guardar_para_winget(archivo: Path, id_: str, version: str) -> dict | None:
    """
    Mueve un instalador bajado con «winget download» a donde «winget upgrade» lo busca.
    {ruta, sha256}, o None si «Id.Versión» no sirve como nombre de carpeta.
    """
    import hashlib
    nombre = f"{id_}.{version}"
    if RE_NOMBRE_INVALIDO.search(nombre) or nombre != nombre.rstrip(". ") or nombre.strip(".") == "":
        return None
    h = hashlib.sha256()
    with open(archivo, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    carpeta = carpeta_temporal_winget() / nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / h.hexdigest()
    if destino.exists():
        destino.unlink()
    shutil.move(str(archivo), str(destino))
    return {"ruta": str(destino), "sha256": h.hexdigest()}


def borrar_guardado_winget(guardado: dict | None):
    """Lo que se dejó para winget y no llegó a usar (se omitió, falló o se canceló)."""
    if not guardado:
        return
    ruta = Path(guardado["ruta"])
    try:
        ruta.unlink(missing_ok=True)
        ruta.parent.rmdir()             # solo si quedó vacía
    except OSError:
        pass


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
    winget dibuja su barra de descarga reescribiendo la misma línea con \r (sin salto de línea):
    cada redibujo sale al momento por «avance», sin esperar a que la línea termine.
    """
    linea = pyqtSignal(str)
    avance = pyqtSignal(str)                    # texto que se va a sobrescribir (barra de progreso)
    terminado = pyqtSignal(object, bool)        # código de salida, si llegó a arrancar
    _linea_hilo = pyqtSignal(int, str)          # (corrida, línea) desde el hilo
    _avance_hilo = pyqtSignal(int, str)         # (corrida, texto) desde el hilo
    _fin_hilo = pyqtSignal(int, object, bool)   # (corrida, código, arrancó) desde el hilo

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineas: list[str] = []
        self._corrida = 0                       # descarta señales atrasadas de una corrida anterior
        self._popen: subprocess.Popen | None = None
        self._hilo: threading.Thread | None = None
        self._matar_al_arrancar = False
        self._linea_hilo.connect(self._recibir_linea)
        self._avance_hilo.connect(self._recibir_avance)
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
        env = entorno_powershell() if programa == POWERSHELL else None
        try:
            proc = subprocess.Popen(linea_de_comando(programa, args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, creationflags=FLAGS_SIN_VENTANA, env=env)
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
            texto = resto + decoder.decode(bloque)
            # Un \r al final puede ser la mitad de un \r\n: se decide con el siguiente bloque
            corte = len(texto) - 1 if texto.endswith("\r") else len(texto)
            resto = self._repartir(corrida, texto[:corte]) + texto[corte:]
            if resto.strip("\r"):
                # Lo \u00faltimo que se dibuj\u00f3 tras un \r (la barra en curso) se ve ya, aunque siga incompleto
                self._avance_hilo.emit(corrida, resto.rstrip("\r"))
        resto += decoder.decode(b"", final=True)
        resto = RE_FIN_DE_LINEA.split(resto.rstrip("\r"))[-1]
        if resto.strip():
            self._linea_hilo.emit(corrida, resto.lstrip("\ufeff"))
        proc.stdout.close()
        self._fin_hilo.emit(corrida, proc.wait() & 0xFFFFFFFF, True)

    def _repartir(self, corrida: int, texto: str) -> str:
        """
        Emite las l\u00edneas completas (lo que qued\u00f3 en pantalla tras el \u00faltimo \r) y los redibujos
        (lo escrito antes de un \r suelto). Devuelve lo que falta por terminar.
        """
        partes = RE_FIN_DE_LINEA.split(texto)
        for segmento, separador in zip(partes[0::2], partes[1::2]):
            if separador in ("\r\n", "\n"):
                self._linea_hilo.emit(corrida, segmento.lstrip("\ufeff"))
            elif segmento.strip():
                self._avance_hilo.emit(corrida, segmento)
        return partes[-1]

    def _recibir_linea(self, corrida: int, linea: str):
        if corrida == self._corrida:
            self.lineas.append(linea)
            self.linea.emit(linea)

    def _recibir_avance(self, corrida: int, texto: str):
        if corrida == self._corrida:
            self.avance.emit(texto)

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
    "sugerir_admin": True,
    "avisar_abiertos": True,
    "finalizar_abiertos": False,
    "preparar_en_paralelo": True,
    "comparar_github": True,
    "tiempo_max": 30,
    "guardar_reporte": True,
    "ignorados": [],
    "sin_firma_aceptados": [],
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
ORDEN_SIN_ESTADO = 9        # celda vacía: siempre después de «En cola» (antes empataban y salían intercaladas)


def orden_de_estado(tipo: str | None) -> int:
    return ORDEN_ESTADOS.get(tipo, 8) if tipo else ORDEN_SIN_ESTADO


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
    """Celda que ordena por su clave (ROL_ORDEN) en vez de por el texto; si empatan, por el nombre de la fila."""

    def __lt__(self, otro):
        a, b = self.data(ROL_ORDEN), otro.data(ROL_ORDEN)
        if a is not None and b is not None:
            try:
                if a != b:
                    return a < b
                return self._nombre_de_fila(self) < self._nombre_de_fila(otro)
            except TypeError:
                pass
        return self.text().lower() < otro.text().lower()

    @staticmethod
    def _nombre_de_fila(it: QTableWidgetItem) -> str:
        t = it.tableWidget()
        primera = t.item(it.row(), 0) if t is not None else None
        return primera.text().lower() if primera is not None else ""


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
    copiables: botones (texto, valor) que copian ese valor, junto a «Copiar».
    """

    def __init__(self, parent, titulo: str, subtitulo: str = "", texto: str = "",
                 nombre_archivo: str | None = None, datos: list | None = None,
                 titulo_texto: str | None = None, ajustar_ancho: bool = False,
                 copiables: list[tuple[str, str]] | None = None):
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
        for i, (nombre, valor) in enumerate(copiables or []):
            b = boton(nombre, "primario" if i == 0 else None, valor)
            b.clicked.connect(lambda _=False, b=b, n=nombre, v=valor: self._copiar(b, n, v))
            fila.addWidget(b)
        nombre_copiar = "Copiar todo" if copiables else "Copiar"
        b = boton(nombre_copiar)
        b.clicked.connect(lambda _=False, b=b, n=nombre_copiar: self._copiar(b, n, self._texto))
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

    @staticmethod
    def _copiar(b: QPushButton, nombre: str, valor: str):
        """Copia y lo confirma en el propio botón un momento."""
        QApplication.clipboard().setText(valor)
        b.setText("✓ Copiado")
        QTimer.singleShot(1500, lambda: b.setText(nombre))

    def _guardar(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar", str(CARPETA_REGISTROS / self._nombre),
                                              "Texto (*.txt);;Todos (*)")
        if ruta:
            try:
                with open(ruta, "w", encoding="utf-8", newline="\r\n") as fh:
                    fh.write(normalizar_saltos(self._texto))
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


def comprobar_fila_reporte(f: dict, actual: dict | None):
    """
    Una fila del reporte frente al análisis de después: qué versión quedó instalada de verdad.
    actual: el paquete tal como sale ahora en «winget upgrade» (None si ya no tiene actualización).
    """
    if actual is None:
        if f["tipo"] in ("ok", "reinicio"):
            f["despues"] = f["objetivo"]
            if f["tipo"] == "ok":
                f["texto"] = "Actualizado y comprobado: ya no tiene actualización pendiente."
        else:
            f["despues"] = "ya no aparece"
        return
    f["despues"] = "desconocida" if actual["desconocida"] else actual["instalada"]
    if f["tipo"] != "ok":
        return
    if actual["instalada"] == f["antes"]:
        f["tipo"] = "aviso"
        f["texto"] = ("winget terminó bien, pero sigue apareciendo con la misma versión"
                      + (" (winget no sabe leer su versión)." if actual["desconocida"] else
                         ": revisa después de reiniciar; si sigue igual, el instalador del fabricante no "
                         "la actualiza en silencio (actualízalo desde el programa o su web)."))
    elif actual["disponible"] == f["objetivo"]:
        # Pasa si el programa estaba abierto: el instalador deja la nueva preparada (le pasó a VS Code)
        f["tipo"] = "aviso"
        f["texto"] = (f"Quedó a medias: ahora tiene {actual['instalada']}, pero {f['objetivo']} sigue "
                      "pendiente. Suele pasar si el programa estaba abierto: termina al cerrarlo (o al "
                      "reiniciar el equipo).")
    else:
        f["texto"] = (f"Actualizado a {actual['instalada']}; mientras tanto salió otra más nueva "
                      f"({actual['disponible']}).")


class CarrilFondo(QObject):
    """
    Un segundo flujo que corre a la par del principal, con su propio proceso: Actualizaciones lo usa
    para ir verificando y descargando los siguientes paquetes mientras se instala otro. Entiende los
    mismos pasos (winget o PowerShell, Pausa, EnHilo), pero no escribe la salida de los programas:
    solo pasa el avance de las descargas a al_avance.
    """
    _resultado_hilo = pyqtSignal(int, object)      # (turno, resultado) de un paso EnHilo

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flujo = None
        self._turno = 0
        self._datos = None
        self._tiempo_agotado = False
        self.abortado = False
        self.al_avance = None                       # función(texto de la barra de winget)
        self._al_terminar = None
        self._proceso = ProcesoExterno(self)
        self._proceso.linea.connect(self._linea)
        self._proceso.avance.connect(self._avance)
        self._proceso.terminado.connect(self._terminado)
        self._resultado_hilo.connect(self._recibir_hilo)
        self._limite = QTimer(self)
        self._limite.setSingleShot(True)
        self._limite.timeout.connect(self._limite_superado)

    def activo(self) -> bool:
        return self._flujo is not None

    def iniciar(self, generador, al_terminar=None):
        self.detener()
        self._flujo, self._al_terminar = generador, al_terminar
        self.abortado = False
        turno = self._turno
        QTimer.singleShot(0, lambda: turno == self._turno and self._avanzar(None))

    def _avanzar(self, valor):
        if self._flujo is None:
            return
        try:
            paso = self._flujo.send(valor)
        except StopIteration:
            self._fin()
            return
        except Exception:
            import traceback
            escribir_fallo(f"[Error en Actualizaciones, segundo plano]\n{traceback.format_exc()}")
            self._fin()
            return
        self._turno += 1
        turno = self._turno
        if isinstance(paso, Pausa):
            QTimer.singleShot(int(paso.segundos * 1000), lambda: turno == self._turno and self._avanzar(None))
            return
        if isinstance(paso, EnHilo):
            def trabajar(funcion=paso.funcion):
                try:
                    resultado = funcion()
                except Exception as e:
                    resultado = e
                self._resultado_hilo.emit(turno, resultado)
            threading.Thread(target=trabajar, daemon=True, name="carril_fondo").start()
            return
        programa, args, _, limite = paso
        self._datos, self._tiempo_agotado = None, False
        if limite:
            self._limite.start(int(limite * 1000))
        self._proceso.iniciar(programa, args)

    def _recibir_hilo(self, turno: int, resultado):
        if turno == self._turno:
            QTimer.singleShot(0, lambda: turno == self._turno and self._avanzar(resultado))

    def _linea(self, linea: str):
        if linea.startswith(MARCA_JSON):
            try:
                self._datos = json.loads(linea[len(MARCA_JSON):])
            except ValueError:
                pass

    def _avance(self, texto: str):
        visible = texto.split("\r")[-1]
        if self.al_avance is not None and ("█" in visible or "▒" in visible):
            self.al_avance(visible)

    def _terminado(self, codigo: int, arranco: bool):
        self._limite.stop()
        if self._flujo is None:
            return
        codigo = 0xFFFFFFFF if not arranco else codigo & 0xFFFFFFFF
        resultado = ResultadoProceso(codigo, list(self._proceso.lineas), self._datos, arranco, self.abortado,
                                     self._tiempo_agotado)
        turno = self._turno
        QTimer.singleShot(0, lambda: turno == self._turno and self._avanzar(resultado))

    def _limite_superado(self):
        self._tiempo_agotado = True
        self._proceso.matar()

    def _fin(self):
        self._flujo = None
        accion, self._al_terminar = self._al_terminar, None
        if accion is not None:
            accion()

    def detener(self):
        """Corta ya: mata el programa en curso y cierra el flujo (sus «finally» limpian lo temporal)."""
        if self._flujo is None:
            return
        self.abortado = True
        self._turno += 1                    # lo que llegue tarde ya no despierta a nadie
        self._limite.stop()
        self._proceso.matar()
        flujo, self._flujo = self._flujo, None
        try:
            flujo.close()
        except Exception:
            pass
        accion, self._al_terminar = self._al_terminar, None
        if accion is not None:
            accion()

    def esperar(self, ms: int = 3000):
        self._proceso.esperar(ms)


class PaginaActualizar(QWidget):
    """
    Busca actualizaciones con winget, las muestra en una tabla (seleccionar, ordenar, filtrar),
    verifica cada paquete y lo actualiza uno por uno, con reporte final.
    """
    _resultado_hilo = pyqtSignal(int, object)      # (turno, resultado) de un paso EnHilo

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
        self.es_admin = es_administrador()
        # Lo que estaba marcado en la copia que se reabrió como administrador (solo vale para esa copia)
        reabierta = self.sec.pop("seleccion_al_reabrir", None)
        self._seleccion_reabierta = ({str(i).lower() for i in reabierta}
                                     if ARG_REABIERTO in sys.argv and isinstance(reabierta, list) else None)

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

        self._turno = 0
        self._resultado_hilo.connect(self._recibir_hilo)
        self._proceso = ProcesoExterno(self)
        self._proceso.linea.connect(self._linea_proceso)
        self._proceso.avance.connect(self._avance_proceso)
        self._proceso.terminado.connect(self._proceso_terminado)
        # Segundo plano: prepara (verifica y descarga) los siguientes mientras se instala uno
        self._carril = CarrilFondo(self)
        self._carril.al_avance = self._avance_fondo
        self._preparados: dict[str, dict] = {}      # clave → {"verifico": bool, "ok": bool}
        self._fondo_en: str | None = None           # el que se está preparando ahora
        self._indice_instalando = -1                # su posición en el lote
        self._siguiendo_fondo = False               # la barra muestra la preparación (se espera a que acabe)
        self._pct_fondo = -1
        self._hubo_descarga = False                 # winget descargó en este paso (no reutilizó nada)
        # Fase del paso en curso (qué hace winget ahora), para la barra y el texto de estado
        self._prefijo = ""                  # «[2/5] Firefox»
        self._fase: str | None = None       # None = el estado lo puso otro texto
        self._texto_fase = ""
        self._inicio_fase = 0.0
        self._paso_instala = False          # el paso actual instala (o solo descarga para revisar la firma)
        self._sitio_descarga = ""
        self._descarga: dict | None = None  # para la velocidad y el tiempo restante
        self._reloj_fase = QTimer(self)     # el tiempo transcurrido avanza aunque winget no diga nada
        self._reloj_fase.setInterval(1000)
        self._reloj_fase.timeout.connect(self._refrescar_fase)
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
        self.chip_admin = QLabel()
        cab.addWidget(self.chip_admin, 0, Qt.AlignmentFlag.AlignVCenter)
        self.chip_seguridad = QLabel("Seguridad: sin revisar")
        self.chip_seguridad.setProperty("class", "chip-info")
        cab.addWidget(self.chip_seguridad, 0, Qt.AlignmentFlag.AlignVCenter)
        cab.addSpacing(SPACING_SM)
        self.btn_admin = boton("Reabrir como administrador", tooltip=(
            "Cierra la app y la vuelve a abrir con permisos de administrador (Windows lo pide con su aviso). "
            "Vuelve a esta pestaña, busca de nuevo y conserva lo que tengas marcado."))
        self.btn_admin.clicked.connect(self._reabrir_admin)
        cab.addWidget(self.btn_admin, 0, Qt.AlignmentFlag.AlignVCenter)
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
        self.tabla.customContextMenuRequested.connect(lambda pos: self._menu_tabla(self.tabla, pos))
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
        self.tabla_manual.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabla_manual.customContextMenuRequested.connect(lambda pos: self._menu_tabla(self.tabla_manual, pos))
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
        self.btn_store = boton("Permitir la Store con la inspección HTTPS…", "fantasma")
        self.btn_store.clicked.connect(self._cambiar_pinning_store)
        self.btn_store.setVisible(False)
        cab_s.addWidget(self.btn_store)
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
            "• Si se descarga de una release de GitHub, su SHA256 se compara además con el que GitHub calculó "
            "cuando el autor subió el archivo (segunda fuente, aparte del manifiesto).\n"
            "• «Revisar la firma digital» (en Opciones) descarga el instalador aparte y comprueba con PowerShell "
            "quién lo firmó (Get-AuthenticodeSignature). Si viene en .zip/.nupkg revisa los instaladores de dentro; "
            "si es MSIX, la firma del paquete.\n"
            "• Antes de instalar revisa si el programa está abierto y espera si Windows Installer está ocupado con "
            "otra instalación.\n"
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
        fila_estado = QHBoxLayout()
        fila_estado.setSpacing(SPACING_SM)
        self.lbl_estado = QLabel("Listo.")
        self.lbl_estado.setProperty("class", "suave")
        self.lbl_estado.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        fila_estado.addWidget(self.lbl_estado, 1)
        self.lbl_porcentaje = QLabel()           # % real de la descarga (de la barra de winget)
        self.lbl_porcentaje.setProperty("class", "dato")
        self.lbl_porcentaje.setVisible(False)
        fila_estado.addWidget(self.lbl_porcentaje)
        progreso.addLayout(fila_estado)
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
        self.chk_sugerir_admin.setChecked(bool(self.sec["sugerir_admin"]))
        self.chk_abiertos.setChecked(bool(self.sec["avisar_abiertos"]))
        self.chk_finalizar.setChecked(bool(self.sec["finalizar_abiertos"]))
        self.chk_paralelo.setChecked(bool(self.sec["preparar_en_paralelo"]))
        self.chk_github.setChecked(bool(self.sec["comparar_github"]))
        self.sp_limite.setValue(int(self.sec["tiempo_max"]))
        self.chk_reporte.setChecked(bool(self.sec["guardar_reporte"]))
        self.lista_ignorados.establecer(self.sec.get("ignorados") or [])
        self.lista_sin_firma.establecer(self.sec.get("sin_firma_aceptados") or [])
        for sig in (self.chk_origenes.toggled, self.chk_desconocidas.toggled, self.chk_ancladas.toggled,
                    self.chk_ignorados.toggled, self.combo_modo.currentIndexChanged, self.chk_verificar.toggled,
                    self.chk_firma.toggled, self.chk_sin_firma.toggled, self.chk_reanalizar.toggled,
                    self.chk_detener.toggled, self.chk_sugerir_admin.toggled, self.chk_abiertos.toggled,
                    self.chk_finalizar.toggled, self.chk_paralelo.toggled,
                    self.chk_github.toggled, self.sp_limite.valueChanged, self.chk_reporte.toggled):
            sig.connect(self._opciones_cambiadas)
        self.lista_ignorados.cambiado.connect(self._ignorados_cambiados)
        self.lista_sin_firma.cambiado.connect(self._sin_firma_cambiados)
        self._opciones_cambiadas()
        self._ajustar_alto(self.tabla)
        self._ajustar_alto(self.tabla_manual)
        self._mostrar_vacio()
        self._mostrar_admin()
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
            self._carril.detener()
            self._proceso.matar()

    def esperar(self, ms: int = 3000):
        self._proceso.esperar(ms)
        self._carril.esperar(ms)

    def estado(self, texto: str):
        self._fase = None
        self.lbl_estado.setText(texto)
        self.lbl_porcentaje.setVisible(False)

    # ─── progreso real de cada paso ───
    def _empezar_paso(self, prefijo: str, texto: str, instala: bool = False):
        """Paso nuevo de un paquete: la barra gira hasta que winget diga cuánto lleva."""
        self._prefijo, self._paso_instala = prefijo, instala
        self._descarga, self._sitio_descarga = None, ""
        self._poner_fase("espera", texto, None)

    def _poner_fase(self, fase: str, texto: str, fraccion: float | None):
        """fraccion None = no se sabe cuánto falta (la barra gira); 0‒1 = avance real."""
        if fase != self._fase:
            self._inicio_fase = time.monotonic()
        self._fase, self._texto_fase = fase, texto
        if fraccion is None:
            self.barra.setRange(0, 0)
            self.lbl_porcentaje.setVisible(False)
        else:
            self.barra.setRange(0, 1000)
            self.barra.setValue(int(fraccion * 1000))
            self.lbl_porcentaje.setText(f"{fraccion * 100:.0f} %")
            self.lbl_porcentaje.setVisible(True)
        self._refrescar_fase()

    def _refrescar_fase(self):
        if self._fase is None or self._flujo is None:
            return
        texto = self._texto_fase
        segundos = time.monotonic() - self._inicio_fase
        if self._fase != "descarga" and segundos >= 3:      # que se note que sigue trabajando
            texto += f" · {formatear_duracion(segundos)}"
        self.lbl_estado.setText(f"{self._prefijo} · {texto}" if self._prefijo else texto)

    def _avance_proceso(self, texto: str):
        """Redibujo de la barra de winget: % real, tamaño, velocidad y tiempo restante."""
        if self._mostrar_salida:
            self._mostrar_avance(texto)

    def _avance_fondo(self, texto: str):
        """La descarga que va en segundo plano: en su fila y, si se está esperando a que acabe, en la barra."""
        if self._siguiendo_fondo:
            self._mostrar_avance(texto)
        lectura = leer_barra_winget(texto)
        p = self._paquetes.get(self._fondo_en or "")
        if lectura is None or p is None:
            return
        pct = int(lectura[0] * 100)
        if pct // 5 != self._pct_fondo // 5:            # sin redibujar la tabla en cada redibujo de winget
            self._pct_fondo = pct
            self._poner_estado(p, "info", f"Preparando: descargando {pct} %")

    def _mostrar_avance(self, texto: str):
        lectura = leer_barra_winget(texto)
        if lectura is None:
            return
        fraccion, hecho, total = lectura
        verbo = f"Descargando de {self._sitio_descarga}" if self._sitio_descarga else "Descargando"
        if hecho is None:
            self._poner_fase("descarga", verbo + "…", fraccion)
            return
        ahora = time.monotonic()
        d = self._descarga
        if d is None or d["total"] != total or hecho < d["hecho"]:          # descarga nueva
            d = self._descarga = {"total": total, "inicio": ahora, "base": hecho, "hecho": hecho}
        d["hecho"] = hecho
        partes = [f"{verbo} · {formatear_bytes(hecho)} de {formatear_bytes(total)}"]
        transcurrido = ahora - d["inicio"]
        if transcurrido >= 1 and hecho > d["base"]:
            velocidad = (hecho - d["base"]) / transcurrido
            partes.append(f"{formatear_bytes(velocidad)}/s")
            if hecho < total:
                partes.append(f"quedan {formatear_duracion((total - hecho) / velocidad)}")
        self._poner_fase("descarga", " · ".join(partes), fraccion)

    def _fase_por_linea(self, visible: str):
        """Lo que winget va diciendo (descargando, hash comprobado, instalando…) pasa a la barra y al estado."""
        m = RE_FASE_DESCARGA.search(visible)
        if m:
            self._hubo_descarga = True
            self._descarga, self._sitio_descarga = None, dominio(m.group(2))
            self._poner_fase("descarga", f"Descargando de {self._sitio_descarga}…", 0.0)
        elif RE_HASH_OK.search(visible):
            if self._paso_instala:
                self._poner_fase("instala", "SHA256 comprobado · iniciando la instalación…", None)
            else:
                self._poner_fase("descargado", "Descargado y SHA256 comprobado", 1.0)
        elif RE_FASE_EXTRAE.search(visible):
            self._poner_fase("instala", "Extrayendo…", None)
        elif RE_FASE_INSTALA.search(visible):
            self._poner_fase("instala", "Instalando (el instalador no informa su avance)…", None)
        elif RE_FASE_LISTO.search(visible):
            self._poner_fase("listo", "Instalado", 1.0)

    def error(self, texto: str):
        if not self.sin_dialogos:
            QMessageBox.warning(self, APP_NOMBRE, texto)
        else:
            self.consola.agregar(texto, "aviso")

    # ─── permisos de administrador ───
    def _mostrar_admin(self):
        if self.es_admin:
            self.chip_admin.setText("✓ Administrador")
            self.chip_admin.setProperty("class", "chip-ok")
            self.chip_admin.setToolTip("La app corre como administrador: los instaladores no pedirán permiso.\n"
                                       "Mientras tanto, Windows no deja arrastrar archivos desde el Explorador "
                                       "a esta ventana.")
        else:
            self.chip_admin.setText("⚠ Sin administrador")
            self.chip_admin.setProperty("class", "chip-aviso")
            self.chip_admin.setToolTip("Sin permisos de administrador: varios instaladores pedirán permiso (UAC) a "
                                       "mitad de la actualización y, en modo silencioso, algunos fallan "
                                       "(«Necesita permisos de administrador») o se quedan esperando.")
        refrescar_estilo(self.chip_admin)
        self.chip_admin.setVisible(ES_WINDOWS)
        self.btn_admin.setVisible(ES_WINDOWS and not self.es_admin)

    def _reabrir_admin(self):
        if self._flujo is not None:
            return
        # La copia nueva vuelve a buscar y marca lo mismo que tenías marcado aquí
        if self._analizado:
            self.sec["seleccion_al_reabrir"] = [self._paquetes[c]["id"] for c in self._claves_marcadas()]
        self.config.guardar()
        if not self.ventana.reabrir_como_admin():
            self.sec.pop("seleccion_al_reabrir", None)
            self.config.guardar()

    def tras_reabrir(self):
        """Esta copia se abrió con «Reabrir como administrador»: busca de nuevo sin que tengas que pulsar nada."""
        if self.es_admin:
            self.consola.agregar("App reabierta como administrador: se vuelve a buscar"
                                 + (" y se marca lo que tenías marcado." if self._seleccion_reabierta is not None
                                    else "."), "ok")
        if ES_WINDOWS:
            QTimer.singleShot(300, lambda: self.analizar())

    def _aviso_finalizar(self, opciones: dict) -> str | None:
        """Con «Finalizarlos sin preguntar» activo, la advertencia que se acepta antes de empezar."""
        if not (opciones["avisar_abiertos"] and opciones["finalizar_abiertos"]):
            return None
        return ("⚠ Está activado «Finalizar sin preguntar los programas abiertos»: si alguno de estos programas "
                "(o algo que use sus archivos, como un navegador con la cámara virtual de OBS) está abierto, se le "
                "pide cerrarse y, si sigue abierto a los 10 s, se finaliza. Perderás lo que no hayas guardado en "
                "él: guarda tu trabajo antes de aceptar. Los procesos de Windows nunca se tocan.")

    def _confirmar_inicio(self, texto: str, aviso: str | None = None) -> bool:
        """
        Pregunta antes de instalar. Sin permisos de administrador (y con la opción activa) ofrece
        reabrir la app así antes de empezar. aviso: advertencia que va primero (ej. finalizar programas).
        True = empezar ya.
        """
        if self.sin_dialogos:
            return True
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Icon.Warning if aviso else QMessageBox.Icon.Question)
        caja.setWindowTitle(APP_NOMBRE)
        if aviso:
            texto = f"{aviso}\n\n{texto}"
        if self.es_admin or not ES_WINDOWS or not self.chk_sugerir_admin.isChecked():
            if not self.es_admin:
                texto += "\n\nAlgunos instaladores pueden pedir permiso de administrador."
            caja.setText(texto + "\n\n¿Continuar?")
            si = caja.addButton(QMessageBox.StandardButton.Yes)
            caja.addButton(QMessageBox.StandardButton.No)
            caja.exec()
            return caja.clickedButton() is si
        caja.setText(texto + "\n\n⚠ La app NO tiene permisos de administrador: varios instaladores pedirán "
                             "permiso (UAC) a mitad de la actualización y, en modo silencioso, algunos fallan "
                             "o se quedan esperando.\n\nRecomendado: reabrirla como administrador. Vuelve a esta "
                             "pestaña y conserva lo que marcaste.")
        b_admin = caja.addButton("Reabrir como administrador", QMessageBox.ButtonRole.AcceptRole)
        b_seguir = caja.addButton("Seguir sin permisos", QMessageBox.ButtonRole.ActionRole)
        caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        caja.setDefaultButton(b_admin)
        no_sugerir = QCheckBox("No volver a sugerirlo (se cambia en «Opciones»)")
        caja.setCheckBox(no_sugerir)
        caja.exec()
        if no_sugerir.isChecked():
            self.chk_sugerir_admin.setChecked(False)
        if caja.clickedButton() is b_admin:
            self._reabrir_admin()
            return False
        return caja.clickedButton() is b_seguir

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
                                     "Si el instalador no está firmado, se omite (salvo los de «Sin firma, pero confío»)")
        self.chk_github = casilla("Comparar el SHA256 con el que publica GitHub",
                                  "Si el instalador se descarga de una release de github.com, se compara el SHA256 del "
                                  "manifiesto con el que GitHub calculó cuando el autor subió el archivo")
        self.chk_abiertos = casilla("Antes de cada programa, revisar si está abierto",
                                    "Busca qué programas tienen abiertos archivos de su carpeta (ej. la cámara virtual "
                                    "de OBS en Chrome o Claude) y te dice cuáles cerrar; desde ese aviso también "
                                    "puedes finalizarlos")
        self.chk_finalizar = casilla("Finalizarlos sin preguntar (⚠ pierdes lo que no hayas guardado en ellos)",
                                     "Si un programa a actualizar está abierto, se le pide cerrarse y, si sigue "
                                     "abierto a los 10 s, se finaliza a la fuerza. Nunca se tocan los procesos de "
                                     "Windows (Explorador, servicios…). Al pulsar «Actualizar» se avisa antes.")
        self.chk_paralelo = casilla("Ir descargando y verificando los siguientes mientras se instala otro",
                                    "Mientras se instala uno, se preparan los siguientes (hasta "
                                    f"{ADELANTO_PREPARACION} por delante): manifiesto, SHA256, firma y descarga. "
                                    "winget reutiliza esa descarga (vuelve a comprobar su SHA256). "
                                    "Las instalaciones siguen siendo de una en una.")
        self.chk_detener = casilla("Detener todo si una actualización falla",
                                   "Los que falten quedan como «omitidos» en el reporte")
        self.chk_sugerir_admin = casilla("Sugerir reabrir como administrador antes de actualizar",
                                         "Si la app no tiene permisos de administrador, al pulsar «Actualizar» "
                                         "ofrece reabrirla así: los instaladores no pedirán permiso a mitad del lote")
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
        self.lista_sin_firma = ListaEditable(
            "SIN FIRMA, PERO CONFÍO (Id)", "Su autor no firma los instaladores (ej. 7zip.7zip): no salen como aviso "
            "ni se omiten por no tener firma. El SHA256 se sigue comprobando. También: clic derecho → Aceptar sin firma.",
            "Agregar Id, ej. 7zip.7zip")
        self.lista_sin_firma.lista.setMaximumHeight(120)

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
        lay.addWidget(self.chk_github)
        lay.addWidget(self.chk_paralelo)
        lay.addWidget(self.chk_abiertos)
        sangria = QHBoxLayout()
        sangria.addSpacing(SPACING_LG + SPACING_XS)
        sangria.addWidget(self.chk_finalizar, 1)
        lay.addLayout(sangria)
        lay.addWidget(self.chk_detener)
        lay.addWidget(self.chk_sugerir_admin)
        lay.addSpacing(SPACING_XS)
        fila = QHBoxLayout()
        fila.addWidget(etiqueta("TIEMPO MÁXIMO POR PAQUETE"), 1)
        fila.addWidget(self.sp_limite)
        lay.addLayout(fila)
        lay.addStretch(1)
        rejilla.addWidget(card, 1, 0)
        card, lay = tarjeta()
        lay.addWidget(self.lista_ignorados)
        lay.addSpacing(SPACING_SM)
        lay.addWidget(self.lista_sin_firma)
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
        self.chk_sugerir_admin.setChecked(o["sugerir_admin"])
        self.chk_abiertos.setChecked(o["avisar_abiertos"])
        self.chk_finalizar.setChecked(o["finalizar_abiertos"])
        self.chk_paralelo.setChecked(o["preparar_en_paralelo"])
        self.chk_github.setChecked(o["comparar_github"])
        self.sp_limite.setValue(o["tiempo_max"])
        self.chk_reporte.setChecked(o["guardar_reporte"])

    def _resumen_opciones(self) -> str:
        """Cómo se van a ejecutar (va debajo de «Comandos»)."""
        o = self.opciones()
        modo = {"silencioso": "modo silencioso", "normal": "con la ventana del instalador",
                "interactivo": "modo interactivo"}.get(o["modo"], o["modo"])
        partes = ["Uno por uno, en el orden de la tabla", modo]
        if o["preparar_en_paralelo"]:
            partes.append("prepara los siguientes mientras instala")
        if o["verificar_antes"]:
            partes.append("verifica el manifiesto antes")
        if o["comprobar_firma"]:
            partes.append("revisa la firma digital" + (" (omite los que no tengan)" if o["omitir_sin_firma"] else ""))
        if o["avisar_abiertos"] and o["finalizar_abiertos"]:
            partes.append("⚠ finaliza sin preguntar los programas abiertos")
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
            "sugerir_admin": self.chk_sugerir_admin.isChecked(),
            "avisar_abiertos": self.chk_abiertos.isChecked(),
            "finalizar_abiertos": self.chk_finalizar.isChecked(),
            "preparar_en_paralelo": self.chk_paralelo.isChecked(),
            "comparar_github": self.chk_github.isChecked(),
            "tiempo_max": self.sp_limite.value(),
            "guardar_reporte": self.chk_reporte.isChecked(),
        }

    def _opciones_cambiadas(self, *_):
        self.chk_sin_firma.setEnabled(self.chk_firma.isChecked())
        self.chk_finalizar.setEnabled(self.chk_abiertos.isChecked())
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

    def _sin_firma_aceptados(self) -> set[str]:
        return {x.lower() for x in self.lista_sin_firma.activos()}

    def _sin_firma_cambiados(self):
        self.sec["sin_firma_aceptados"] = self.lista_sin_firma.valores()
        self.config.guardar()

    def _aceptar_sin_firma(self, id_: str):
        valores = [v for v in self.lista_sin_firma.valores() if v[0].lower() != id_.lower()] + [[id_, True]]
        self.lista_sin_firma.establecer(valores)
        self._sin_firma_cambiados()
        p = next((x for x in self._paquetes.values() if x["id"].lower() == id_.lower()), None)
        firma = (p or {}).get("verif", {}).get("firma")
        if p and firma and firma["tipo"] == "sin_firma":
            self._aplicar_sin_firma_aceptado(p)
            self._refrescar_fila(p)
        self.consola.agregar(f"«{id_}» queda en «Sin firma, pero confío».", "ok")

    def _aplicar_sin_firma_aceptado(self, p: dict):
        """El autor no firma (ej. 7-Zip) y lo aceptaste: cuenta como bien, con su SHA256 comprobado."""
        firma = p["verif"]["firma"]
        firma["tipo"], firma["aceptado"] = "ok", True
        firma["texto"] = "Sin firma (el autor no firma; aceptado por ti)"
        componer_verificacion(p["verif"])

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
        self._prefijo = ""
        self._set_ocupado(True)
        self.estado(texto_estado)
        self._reloj_fase.start()
        QTimer.singleShot(0, lambda: self._avanzar(None))

    def _avanzar(self, valor):
        if self._flujo is None:
            return
        try:
            paso = self._flujo.send(valor)
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
        # El turno evita que un temporizador o un hilo atrasado despierte a otro paso (u otro flujo)
        self._turno += 1
        turno = self._turno
        if isinstance(paso, Pausa):
            QTimer.singleShot(int(paso.segundos * 1000), lambda: turno == self._turno and self._avanzar(None))
            return
        if isinstance(paso, EnHilo):
            def trabajar(funcion=paso.funcion):
                try:
                    resultado = funcion()
                except Exception as e:
                    resultado = e
                self._resultado_hilo.emit(turno, resultado)
            threading.Thread(target=trabajar, daemon=True, name="flujo_actualizaciones").start()
            return
        programa, args, mostrar, limite = paso
        self._mostrar_salida, self._programa = mostrar, programa
        self._datos_ps, self._tiempo_agotado = None, False
        if limite:
            self._limite.start(int(limite * 1000))
        self._proceso.iniciar(programa, args)

    def _recibir_hilo(self, turno: int, resultado):
        if turno == self._turno:
            QTimer.singleShot(0, lambda: self._avanzar(resultado))

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
        self._parar_preparacion()
        self._reloj_fase.stop()
        self._fase, self._prefijo = None, ""
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
        self.lbl_porcentaje.setVisible(False)
        self._actualizar_botones()

    def detener_tras_actual(self):
        if self._flujo is not None:
            self._detener = True
            self.btn_detener.setEnabled(False)
            if self._carril.activo():
                self._carril.detener()          # ya no hace falta preparar los siguientes
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
        self._carril.detener()
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
        if "█" in visible or "▒" in visible:       # barra de progreso: a la barra, no al registro
            self._avance_proceso(visible)
            return
        self.consola.alimentar(visible + "\n")
        self._fase_por_linea(visible)
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
        # Quién firma el certificado HTTPS que llega (Microsoft, o un antivirus que inspecciona el tráfico)
        r = yield self._powershell(SCRIPT_TLS, 60)
        if r.abortado:
            return
        datos["Tls"] = r.datos
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
            self._empezar_paso(f"[{i}/{len(claves)}] {p['nombre']}", "Leyendo el manifiesto (winget show)…")
            yield from self._pasos_verificar(p, con_firma, estricto=p["grupo"] == "lote")
        self.estado("Verificación terminada.")

    def _pasos_verificar(self, p: dict, con_firma: bool, estricto: bool, guardar: bool = False,
                         fondo: bool = False):
        """
        Devuelve True si el paquete se puede instalar (con estricto=False, solo informa).
        guardar: lo que se descargue se deja para que «winget upgrade» no lo vuelva a bajar.
        fondo: corre en segundo plano (CarrilFondo): no toca la barra ni el estado, y descarga por
        adelantado aunque no haya que revisar la firma.
        """
        w = self._seguridad["winget"]
        fase = (lambda *_: None) if fondo else self._poner_fase
        args = self._args_show(p)
        self.consola.agregar(f"🔍 {p['nombre']}: " + comando_visible(args), "suave")
        r = yield self._winget(w, args, False, 180)
        if r.abortado:
            return False
        info = parsear_show(r.texto, p["id"])
        v = p["verif"]
        for clave in ("github", "incompatible", "firma", "riesgos", "como"):
            v.pop(clave, None)
        v.update(info)
        v["show"] = r.texto
        v["manifiesto"] = evaluar_manifiesto(info, r.codigo, estricto)
        componer_verificacion(v)
        tipo_m, texto_m = v["manifiesto"]
        self.consola.agregar(f"{ICONOS_TIPO[tipo_m]} {p['nombre']}: {texto_m}"
                             + (f" · editor: {info['editor']}" if info.get("editor") else "")
                             + (f"\n   SHA256 {info['sha256']}\n   {info['url']}" if info.get("sha256") else ""),
                             tipo_m)
        self._refrescar_fila(p)
        if v["tipo"] == "error":
            return False

        # Segunda fuente del SHA256: el que GitHub calculó cuando el autor subió el archivo a la release
        if self.chk_github.isChecked() and info.get("sha256") and RE_GITHUB_RELEASE.match(info.get("url") or ""):
            fase("github", "Comparando el SHA256 con el que publica GitHub…", None)
            gh = yield EnHilo(lambda: digest_de_github(info["url"]))
            if self._abortado:
                return False
            v["github"] = evaluar_github(gh, info["sha256"])
            self.consola.agregar(f"{ICONOS_TIPO[v['github'][0]]} {p['nombre']}: {v['github'][1]}",
                                 v["github"][0] if v["github"][0] != "info" else "suave")
            componer_verificacion(v)
            self._refrescar_fila(p)
            if v["tipo"] == "error":
                return False

        # ¿winget puede pasar de lo instalado a lo que ofrece? (de MSIX a MSI/EXE, o al revés, no puede)
        fase("detalles", "Leyendo cómo está instalado (winget list --details)…", None)
        detalles = yield from self._detalles_instalado(w, p)
        if self._abortado:
            return False
        motivo = motivo_no_aplicable(detalles.get("categoria"), info.get("tipo_instalador"), p["id"], seguro=True)
        if motivo:
            v["incompatible"] = motivo
            self.consola.agregar(f"⚠ {p['nombre']}: {motivo}", "aviso")
            componer_verificacion(v)
            self._refrescar_fila(p)

        # ¿Cómo actualiza? (manifiesto de winget-pkgs): desinstalar antes, permisos de administrador, conda
        fase("detalles", "Leyendo cómo actualiza su instalador (manifiesto de winget-pkgs)…", None)
        como = yield from self._como_actualiza(w, p)
        if self._abortado:
            return False
        riesgos = []
        if como.get("conda") and not es_distribucion_conda(p["id"]):
            riesgos.append(("error" if estricto else "aviso", MOTIVO_CONDA))
        elif como.get("desinstala_antes"):
            riesgos.append(("aviso", "Al actualizar, winget DESINSTALA primero la versión que tienes: si la nueva "
                                     "falla, te quedas sin el programa (se pregunta antes de hacerlo)"))
        if como.get("eleva") and not self.es_admin:
            riesgos.append(("aviso", "Su instalador necesita permisos de administrador: abre la app como administrador"))
        if riesgos:
            v["riesgos"] = riesgos
            for tipo, texto in riesgos:
                self.consola.agregar(f"{ICONOS_TIPO[tipo]} {p['nombre']}: {texto}", tipo)
            componer_verificacion(v)
            self._refrescar_fila(p)
            if v["tipo"] == "error":
                return False

        if p["origen"] in ORIGENES_EN_LOTE and (con_firma or (fondo and self._vale_descargar(p))):
            ok = yield from self._descargar_y_revisar(p, con_firma, guardar, fondo)
            if not ok:
                return False
        return True

    def _vale_descargar(self, p: dict) -> bool:
        """¿Sirve bajarlo por adelantado? (winget no usa la descarga de un MSIX ni se actualiza conda así)."""
        v = p["verif"]
        if p["origen"] not in ORIGENES_EN_LOTE or es_distribucion_conda(p["id"]) or (v.get("como") or {}).get("conda"):
            return False
        if tipo_base(v.get("tipo_instalador")) in TIPOS_MSIX:
            return False
        guardado = p.get("descargado")
        return not (guardado and os.path.isfile(guardado["ruta"]))

    def _descargar_y_revisar(self, p: dict, con_firma: bool, guardar: bool, fondo: bool = False):
        """
        «winget download» a una carpeta temporal (winget comprueba el SHA256 al descargar).
        con_firma: PowerShell revisa la firma y recalcula el SHA256; devuelve False si no pasa.
        guardar: deja el instalador donde «winget upgrade» lo reutiliza (p["descargado"]).
        La carpeta temporal se borra siempre, aunque se cancele.
        """
        w = self._seguridad["winget"]
        v = p["verif"]
        fase = (lambda *_: None) if fondo else self._poner_fase
        carpeta = Path(tempfile.mkdtemp(prefix="utilidades_winget_"))
        firma = None
        codigo = None
        try:
            # El mismo ámbito y arquitectura que lo instalado: así se baja el instalador que usará «upgrade»
            detalles = p.get("instalado") or {}
            ambito = {"machine": "machine", "user": "user"}.get((detalles.get("ambito") or "").lower())
            arquitectura = (detalles.get("arquitectura") or "").lower()
            filtros = (["--scope", ambito] if ambito else []) + (
                ["--architecture", arquitectura] if arquitectura in ("x86", "x64", "arm", "arm64") else [])
            for intento in (filtros, []):
                args = (["download", "--id", p["id"], "--exact", "--source", p["origen"], "--version", p["disponible"]]
                        + intento + ["--download-directory", str(carpeta), "--accept-package-agreements",
                                     "--accept-source-agreements", "--disable-interactivity"])
                self.consola.agregar(f"⬇ {p['nombre']}: " + comando_visible(args), "suave")
                if not fondo:
                    self._empezar_paso(self._prefijo or p["nombre"], "Descargando el instalador para revisar su firma…"
                                       if con_firma else "Descargando el instalador…")
                r = yield self._winget(w, args, True, 1800)
                if r.abortado or r.tiempo_agotado:
                    return False
                if r.codigo != 0x8A150010 or not intento:      # 0x8A150010: ningún instalador con esos filtros
                    break
            codigo = r.codigo
            if r.codigo == 0:
                archivos = [f for f in carpeta.rglob("*")
                            if f.is_file() and f.suffix.lower() not in (".yaml", ".yml")]
                archivo = max(archivos, key=lambda f: f.stat().st_size, default=None)
                if archivo is not None and con_firma:
                    # Lo que Get-AuthenticodeSignature no sabe leer: lo de dentro de un zip/nupkg, o un MSIX
                    interno = {}
                    if archivo.suffix.lower() in EXT_COMPRIMIDOS + EXT_PAQUETE_MSIX:
                        fase("firma", f"Abriendo «{archivo.name}» para revisar lo de dentro…", None)
                        interno = yield EnHilo(lambda: preparar_revision_interna(archivo, carpeta))
                        if self._abortado:
                            return False
                        if isinstance(interno, Exception):
                            self.consola.agregar(f"No se pudo abrir «{archivo.name}» para revisar lo de dentro: "
                                                 f"{interno}", "aviso")
                            interno = {}
                    internos = interno.get("internos") or []
                    extra = (f" y de los {len(internos)} instalador(es) de dentro" if internos
                             else " y la firma del paquete MSIX" if interno.get("msix") else "")
                    self.consola.agregar(f"🔏 {p['nombre']}: Get-AuthenticodeSignature y Get-FileHash "
                                         f"de «{archivo.name}»{extra}", "suave")
                    fase("firma", "Revisando la firma digital (PowerShell)…", None)
                    r2 = yield self._powershell(script_firma_archivo(str(archivo), [x[0] for x in internos],
                                                                     interno.get("msix")), 300)
                    if r2.abortado:
                        return False
                    firma = dict(r2.datos or {"Estado": "SinRespuesta"}, Archivo=archivo.name,
                                 Bytes=archivo.stat().st_size)
                    datos_internos = firma.get("Internos")
                    if isinstance(datos_internos, dict):         # PowerShell 5.1 devuelve uno solo sin lista
                        firma["Internos"] = datos_internos = [datos_internos]
                    for dato, (_, nombre) in zip(datos_internos or [], internos):
                        if isinstance(dato, dict):
                            dato["Nombre"] = nombre
                if archivo is not None and guardar:
                    guardado = yield EnHilo(lambda: guardar_para_winget(archivo, p["id"], p["disponible"]))
                    if self._abortado:
                        return False
                    if isinstance(guardado, dict):
                        previo = p.get("descargado")
                        if previo and previo["ruta"] != guardado["ruta"]:
                            borrar_guardado_winget(previo)
                        p["descargado"] = guardado
                    elif isinstance(guardado, Exception):
                        self.consola.agregar(f"No se pudo dejar la descarga de {p['nombre']} lista para winget "
                                             f"({guardado}): la bajará otra vez al instalar.", "suave")
            elif not con_firma:
                self.consola.agregar(f"No se pudo descargar {p['nombre']} por adelantado ({codigo_hex(r.codigo)}): "
                                     "winget lo descargará al instalar.", "suave")
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)
        if not con_firma:
            return True
        tipo, texto = evaluar_firma(firma, v.get("sha256"), codigo)
        v["firma"] = {"tipo": tipo, "texto": texto, "datos": firma}
        if tipo == "sin_firma" and p["id"].lower() in self._sin_firma_aceptados():
            self._aplicar_sin_firma_aceptado(p)
        else:
            componer_verificacion(v)
        tipo, texto = v["firma"]["tipo"], v["firma"]["texto"]
        self.consola.agregar(f"{ICONOS_TIPO[tipo]} {p['nombre']}: {texto}"
                             + (f" (emitido por {nombre_del_certificado((firma or {}).get('Emisor'))})"
                                if tipo == "ok" and (firma or {}).get("Estado") == "Valid" else ""),
                             tipo if tipo != "sin_firma" else "aviso")
        self._refrescar_fila(p)
        return not (tipo == "error" or (tipo == "sin_firma" and self.chk_sin_firma.isChecked()))

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
        lineas = [f"• {self._paquetes[c]['nombre']}: {self._paquetes[c]['instalada']} → "
                  f"{self._paquetes[c]['disponible']}" for c in claves[:12]]
        if len(claves) > 12:
            lineas.append(f"… y {len(claves) - 12} más")
        aviso = self._aviso_finalizar(opciones)
        if not self._confirmar_inicio(f"Se van a actualizar {len(claves)} programa(s), uno por uno:\n\n"
                                      + "\n".join(lineas)
                                      + ("" if aviso else "\n\nCierra esos programas antes de empezar."), aviso):
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
        # Mientras se instala uno, otro carril va verificando y descargando los siguientes
        self._preparados, self._fondo_en, self._indice_instalando = {}, None, -1
        if opciones["preparar_en_paralelo"] and total > 1:
            self._carril.iniciar(self._flujo_preparar(claves, opciones))
        for i, clave in enumerate(claves, 1):
            p = self._paquetes[clave]
            fila = reporte["filas"][clave]
            self._indice_instalando = i - 1
            if self._abortado:
                break
            if self._detener:
                fila["tipo"], fila["texto"] = "omitido", "Detenido antes de empezar."
                self._poner_estado(p, "omitido", "Omitido (detenido)")
                continue
            prefijo = f"[{i}/{total}] {p['nombre']}"

            # 0. Si se está preparando en segundo plano, se espera a que acabe (la barra muestra su descarga)
            if self._fondo_en == clave:
                self._empezar_paso(prefijo, "Terminando de prepararlo (verificar y descargar)…")
                self._siguiendo_fondo = True
                while self._fondo_en == clave and not self._abortado:
                    yield Pausa(0.5)
                self._siguiendo_fondo = False
                if self._abortado:
                    break

            # 1. Verificación previa (si ya se hizo en segundo plano, se usa su resultado)
            v = p["verif"]
            preparado = self._preparados.get(clave) or {}
            if preparado.get("verifico") or self._necesita_verificar(p, opciones):
                if preparado.get("verifico"):
                    ok = preparado["ok"]
                else:
                    self._poner_estado(p, "info", "Verificando…")
                    self._empezar_paso(prefijo, "Leyendo el manifiesto (winget show)…")
                    ok = yield from self._pasos_verificar(p, opciones["comprobar_firma"],
                                                          estricto=p["grupo"] == "lote", guardar=True)
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

            # 2. ¿Está abierto? (el instalador fallaría o dejaría la actualización a medias)
            p.pop("abierto_por", None)
            p.pop("finalizados", None)
            if opciones["avisar_abiertos"]:
                respuesta = yield from self._revisar_abiertos(w, p, prefijo, opciones["finalizar_abiertos"])
                if self._abortado:
                    break
                if respuesta == "omitir":
                    fila["tipo"], fila["texto"] = "omitido", f"Omitido: estaba en uso por {p.get('abierto_por')}."
                    self._poner_estado(p, "omitido", "Omitido: estaba abierto")
                    continue
            # 3. ¿winget lo desinstalará antes de instalar la nueva? Si falla, te quedarías sin el programa
            self._empezar_paso(prefijo, "Leyendo cómo actualiza su instalador…")
            como = yield from self._como_actualiza(w, p)
            if self._abortado:
                break
            if como.get("conda") or es_distribucion_conda(p["id"]):
                fila["tipo"], fila["texto"] = "omitido", f"Omitido: {MOTIVO_CONDA}"
                self._poner_estado(p, "omitido", "Omitido: distribución de conda")
                self.consola.agregar(f"↷ {p['nombre']}: {MOTIVO_CONDA}", "aviso")
                continue
            if como.get("desinstala_antes"):
                self.consola.agregar(f"⚠ {p['nombre']}: winget desinstala primero la versión que tienes "
                                     "(UpgradeBehavior: uninstallPrevious).", "aviso")
                if not self._confirmar_desinstala_antes(p, como):
                    fila["tipo"], fila["texto"] = "omitido", ("Omitido: winget lo desinstalaría antes de instalar la "
                                                              "nueva y, si fallaba, te quedabas sin el programa.")
                    self._poner_estado(p, "omitido", "Omitido: se desinstalaría antes")
                    continue
            # 4. Si Windows Installer está ocupado con otra instalación, se espera (si no, falla con 1618)
            yield from self._esperar_windows_installer(prefijo)
            if self._abortado:
                break

            # 5. Actualización
            args = self._args_actualizar(p, opciones)
            self.consola.agregar(f"▶ [{i}/{total}] {p['nombre']}: {p['instalada']} → {p['disponible']}", "titulo")
            self.consola.agregar(comando_visible(args), "suave")
            guardado = p.get("descargado")
            if guardado and os.path.isfile(guardado["ruta"]):
                self.consola.agregar("⚡ Su instalador ya está descargado: winget lo usa sin volver a bajarlo si es el "
                                     "que elige (antes comprueba otra vez su SHA256).", "suave")
            self._poner_estado(p, "info", "Actualizando…")
            self._empezar_paso(prefijo, f"Preparando {version_visible(p['instalada'])} → {p['disponible']}…",
                               instala=True)
            p["hash_winget"] = False
            self._hubo_descarga = False
            self._en_curso = p
            limite = opciones["tiempo_max"] * 60 if opciones["tiempo_max"] else None
            r = yield self._winget(w, args, True, limite)
            self._en_curso = None
            if guardado and p["hash_winget"] and not self._hubo_descarga:
                fila["descarga_previa"] = True
                self.consola.agregar("⚡ winget usó la descarga hecha por adelantado.", "ok")
            if r.codigo == 0x8A15005F and not (r.abortado or r.tiempo_agotado):
                # Algunos instaladores (ej. Battle.net) piden la carpeta: se usa en la que ya está instalado
                ubicacion = yield from self._ubicacion_instalada(w, p)
                if ubicacion and not self._abortado:
                    self.consola.agregar(f"winget pide la carpeta de instalación: se reintenta con la que ya "
                                         f"tiene ({ubicacion}).", "aviso")
                    args = self._args_actualizar(p, opciones, ubicacion)
                    self.consola.agregar(comando_visible(args), "suave")
                    fila["ubicacion"] = ubicacion
                    self._empezar_paso(prefijo, "Reintentando en la carpeta donde ya está instalado…", instala=True)
                    self._en_curso = p
                    r = yield self._winget(w, args, True, limite)
                    self._en_curso = None
            # Chocó con otra instalación MSI que empezó justo entonces: se espera a que acabe y se reintenta
            for intento in (1, 2):
                if r.codigo != 0x8A150102 or r.abortado or r.tiempo_agotado or self._abortado:
                    break
                self.consola.agregar(f"Chocó con otra instalación de Windows Installer: se reintenta ({intento}/2) "
                                     "cuando termine.", "aviso")
                yield from self._esperar_windows_installer(prefijo)
                self._empezar_paso(prefijo, f"Esperando unos segundos antes de reintentar ({intento}/2)…")
                yield Pausa(8)
                if self._abortado:
                    break
                self._empezar_paso(prefijo, f"Reintentando ({intento}/2)…", instala=True)
                self._en_curso = p
                r = yield self._winget(w, args, True, limite)
                self._en_curso = None
                fila["reintentos"] = intento
            motivo = None
            if r.codigo == 0x8A15002B and not (r.abortado or r.tiempo_agotado or self._abortado):
                detalles = yield from self._detalles_instalado(w, p)
                motivo = v.get("incompatible") or motivo_no_aplicable(
                    detalles.get("categoria"), v.get("tipo_instalador"), p["id"], seguro=False)
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
                if motivo:
                    texto = f"No hay una actualización aplicable. {motivo}"
                if p.get("abierto_por") and r.codigo in CODIGOS_PROGRAMA_ABIERTO:
                    texto += f" Estaba en uso por: {p['abierto_por']}."
                if p.get("finalizados"):
                    texto += f" (Antes se cerraron: {', '.join(p['finalizados'])}.)"
                    fila["finalizados"] = list(p["finalizados"])
                if fila.get("reintentos") and tipo in ("ok", "reinicio"):
                    texto += f" (a la {fila['reintentos'] + 1}.ª: antes chocó con otra instalación)"
                salida_instalador = codigo_salida_instalador(r.texto) if tipo == "error" else None
                if salida_instalador is not None:
                    texto += f" Código de salida del instalador: {salida_instalador}."
                    fila["salida_instalador"] = salida_instalador
                carpeta = (p.get("instalado") or {}).get("carpeta")
                if tipo == "error" and como.get("desinstala_antes") and carpeta and not os.path.isdir(carpeta):
                    # winget desinstaló la anterior y la nueva no se instaló: dilo claro y cómo reinstalarlo
                    reinstalar = comando_visible(["install", "--id", p["id"], "--exact", "--source", p["origen"]]
                                                 + (["--scope", "machine"] if como.get("ambito") == "machine" else []))
                    texto = (f"Se DESINSTALÓ la versión anterior y la nueva no se instaló: «{p['nombre']}» ya no está "
                             f"instalado ({carpeta} ya no existe). {texto} Para reinstalarlo: {reinstalar}")
                    fila["desinstalado"] = True
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
        self._parar_preparacion()
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

    @staticmethod
    def _necesita_verificar(p: dict, opciones: dict) -> bool:
        v = p["verif"]
        falta_firma = opciones["comprobar_firma"] and not v.get("firma") and p["origen"] in ORIGENES_EN_LOTE
        return bool((opciones["verificar_antes"] and v.get("tipo") is None) or falta_firma)

    def _siguiente_a_preparar(self, claves: list[str], opciones: dict) -> str | None:
        """El primero sin preparar de los que vienen (como mucho ADELANTO_PREPARACION por delante)."""
        inicio = self._indice_instalando + 1
        for clave in claves[inicio:inicio + ADELANTO_PREPARACION]:
            if clave in self._preparados:
                continue
            p = self._paquetes.get(clave)
            if p is None or p.get("id_cortado") or (p["verif"].get("tipo") == "error" and p["grupo"] == "lote") \
                    or not (self._necesita_verificar(p, opciones) or self._vale_descargar(p)):
                self._preparados[clave] = {"verifico": False, "ok": None}      # no hay nada que adelantar
                continue
            return clave
        return None

    def _flujo_preparar(self, claves: list[str], opciones: dict):
        """
        Segundo plano del lote: verifica y descarga los que vienen mientras se instala otro. No instala
        ni pregunta nada (las preguntas y la instalación van en el flujo principal, de una en una).
        """
        w = self._seguridad["winget"]
        while not (self._abortado or self._detener):
            clave = self._siguiente_a_preparar(claves, opciones)
            if clave is None:
                if all(c in self._preparados for c in claves[self._indice_instalando + 1:]):
                    return
                yield Pausa(1)          # ya hay bastantes preparados: espera a que se instale el actual
                continue
            p = self._paquetes[clave]
            verificar = self._necesita_verificar(p, opciones)
            self._fondo_en, self._pct_fondo = clave, -1
            terminado = False
            try:
                self._poner_estado(p, "info", "Preparando en segundo plano…")
                self.consola.agregar(f"⇣ {p['nombre']}: se prepara en segundo plano ("
                                     + ("verificar y descargar" if verificar else "descargar") + ").", "suave")
                if verificar:
                    ok = yield from self._pasos_verificar(p, opciones["comprobar_firma"], estricto=p["grupo"] == "lote",
                                                          guardar=True, fondo=True)
                else:
                    yield from self._detalles_instalado(w, p)
                    ok = yield from self._descargar_y_revisar(p, False, True, fondo=True)
                terminado = not (self._abortado or self._carril.abortado)
            finally:
                self._fondo_en = None
                if terminado:
                    self._preparados[clave] = {"verifico": verificar, "ok": ok}
                else:
                    # Se cortó a medias: el flujo principal lo verificará entero
                    self._preparados[clave] = {"verifico": False, "ok": None}
                    if verificar:
                        p["verif"].pop("tipo", None)
                    if self._reporte and self._reporte["filas"].get(clave, {}).get("tipo") == "pendiente":
                        self._poner_estado(p, "pendiente", "En cola")
            listo = (["verificado"] if verificar else []) + (["descargado"] if p.get("descargado") else [])
            if ok:
                self._poner_estado(p, "pendiente", "En cola · " + " y ".join(listo) if listo else "En cola")
            else:
                self._poner_estado(p, "aviso", "En cola · no pasó la verificación (se omitirá)")

    def _parar_preparacion(self):
        """Corta el segundo plano y borra lo descargado por adelantado que winget no llegó a usar."""
        self._carril.detener()
        self._fondo_en, self._siguiendo_fondo = None, False
        for p in self._paquetes.values():
            borrar_guardado_winget(p.pop("descargado", None))

    def _ubicacion_instalada(self, w: str, p: dict):
        detalles = yield from self._detalles_instalado(w, p)
        return detalles.get("ubicacion") or detalles.get("carpeta")

    def _detalles_instalado(self, w: str, p: dict):
        """«winget list --id X --details» (una vez por análisis): carpeta, tipo de instalador, identificador local."""
        if p.get("instalado") is None:
            args = ["list", "--id", p["id"], "--exact", "--details", "--accept-source-agreements",
                    "--disable-interactivity"]
            self.consola.agregar(comando_visible(args), "suave")
            r = yield self._winget(w, args, False, 120)
            if r.abortado:
                return {}
            p["instalado"] = leer_detalles_instalado(r.texto) if r.codigo == 0 else {}
        return p["instalado"]

    def _como_actualiza(self, w: str, p: dict):
        """
        Del manifiesto en winget-pkgs, para el ámbito y la arquitectura que tienes instalados: si winget
        desinstalará la versión anterior antes de instalar, si el instalador pide administrador y si
        trae conda. {} si no se pudo saber. Se guarda en la verificación del paquete.
        """
        v = p["verif"]
        if v.get("como") is not None:
            return v["como"]
        detalles = yield from self._detalles_instalado(w, p)
        version = p["disponible"]
        manifiesto = yield EnHilo(lambda: manifiesto_instalador(p["id"], version))
        if isinstance(manifiesto, Exception) or manifiesto is None:
            if isinstance(manifiesto, Exception):
                self.consola.agregar(f"No se pudo leer el manifiesto de {p['nombre']} en winget-pkgs ({manifiesto}).",
                                     "suave")
            v["como"] = {}
            return v["como"]
        aplicables = instaladores_aplicables(manifiesto, detalles.get("ambito"), detalles.get("arquitectura"))
        comportamientos = {(i.get("UpgradeBehavior") or "install") for i in aplicables}
        v["como"] = {"desinstala_antes": "uninstallPrevious" in comportamientos,
                     "eleva": any(i.get("ElevationRequirement") == "elevationRequired" for i in aplicables),
                     "conda": "conda" in [c.lower() for c in manifiesto["comandos"]],
                     "ambito": detalles.get("ambito")}
        return v["como"]

    def _confirmar_desinstala_antes(self, p: dict, como: dict) -> bool:
        """winget va a desinstalar la versión actual antes de instalar la nueva: ¿seguir? (no, por defecto)."""
        if self.sin_dialogos:
            return False
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Icon.Warning)
        caja.setWindowTitle(APP_NOMBRE)
        caja.setText(f"Para actualizar «{p['nombre']}», winget primero DESINSTALA la versión que tienes "
                     f"({version_visible(p['instalada'])}) y después instala la {p['disponible']}.\n\n"
                     "Si el instalador nuevo falla, el programa se queda desinstalado.")
        caja.setInformativeText("Su instalador necesita permisos de administrador: si no abriste la app como "
                                "administrador, es más probable que falle." if como.get("eleva") and not self.es_admin
                                else "Si prefieres no arriesgarte, actualízalo desde el propio programa o su web.")
        caja.addButton("Saltar este programa", QMessageBox.ButtonRole.RejectRole)
        b_seguir = caja.addButton("Desinstalar y actualizar", QMessageBox.ButtonRole.DestructiveRole)
        caja.setDefaultButton(caja.buttons()[0])
        caja.exec()
        return caja.clickedButton() is b_seguir

    def _esperar_windows_installer(self, prefijo: str, maximo: float = 900):
        """Si otra instalación MSI está en curso (Windows Update, el actualizador de otro programa…), espera."""
        if not windows_installer_ocupado():
            return
        self.consola.agregar("Windows Installer está ocupado con otra instalación (de Windows o de otro programa): "
                             "se espera a que termine para no chocar con ella.", "aviso")
        self._empezar_paso(prefijo, "Esperando a que termine otra instalación (Windows Installer)…")
        inicio = time.monotonic()
        while windows_installer_ocupado():
            if self._abortado:
                return
            if time.monotonic() - inicio > maximo:
                self.consola.agregar(f"Windows Installer siguió ocupado {formatear_duracion(maximo)}: se intenta de "
                                     "todos modos.", "aviso")
                return
            yield Pausa(2)
        self.consola.agregar("Windows Installer quedó libre: se sigue.", "suave")

    def _revisar_abiertos(self, w: str, p: dict, prefijo: str, auto: bool = False):
        """
        Antes de instalar: qué programas tienen abiertos archivos de su carpeta. Devuelve «seguir» u «omitir».
        auto: los finaliza sin preguntar (una sola vez: si queda alguno, de Windows o sin permiso, se sigue igual).
        """
        detalles = yield from self._detalles_instalado(w, p)
        carpeta = detalles.get("carpeta")
        if not carpeta or self._abortado:
            return "seguir"
        finalizo = False
        while True:
            self._empezar_paso(prefijo, "Revisando si el programa está abierto…")
            r = yield self._powershell(script_procesos_en(carpeta), 90)
            if r.abortado:
                return "omitir"
            datos = r.datos if isinstance(r.datos, list) else [r.datos] if isinstance(r.datos, dict) else None
            if datos is None:
                self.consola.agregar(f"No se pudo revisar si {p['nombre']} está abierto (PowerShell no respondió).", "suave")
                return "seguir"
            grupos = agrupar_procesos(datos)
            if not grupos:
                if finalizo:
                    self.consola.agregar(f"✓ {p['nombre']} ya no está en uso: se sigue.", "ok")
                p.pop("abierto_por", None)
                return "seguir"
            p["abierto_por"] = ", ".join(n + (f" ({c} procesos)" if c > 1 else "") for n, c, _ in grupos)
            archivos = sorted({a for _, _, a in grupos if a})
            self.consola.agregar(f"⚠ {p['nombre']} está en uso por: {p['abierto_por']}"
                                 + (f" (tienen abierto {', '.join(archivos[:3])})" if archivos else "") + ".", "aviso")
            finalizables, intocables = separar_finalizables(datos)
            if auto and finalizables and not finalizo:
                respuesta = "finalizar"
            elif auto or self.sin_dialogos:
                if intocables:
                    self.consola.agregar("No se finalizan (son de Windows o servicios; el instalador se encarga): "
                                         + ", ".join(n for n, _, _ in agrupar_procesos(intocables)) + ".", "suave")
                return "seguir"
            else:
                respuesta = self._preguntar_abiertos(p, carpeta, finalizables, intocables)
            if respuesta == "finalizar":
                yield from self._finalizar_procesos(p, finalizables, prefijo)
                if self._abortado:
                    return "omitir"
                finalizo = True
                continue
            if respuesta != "revisar":
                return respuesta

    def _finalizar_procesos(self, p: dict, procesos: list, prefijo: str):
        """Cierra (o finaliza) los procesos que tienen abierto el programa y dice cuáles no se pudo."""
        nombres = ", ".join(n for n, _, _ in agrupar_procesos(procesos))
        self.consola.agregar(f"⏹ {p['nombre']}: se cierran {nombres} (si no se cierran solos en 10 s, se "
                             "finalizan)…", "aviso")
        self._empezar_paso(prefijo, "Cerrando los programas que lo tienen abierto…")
        r = yield self._powershell(script_finalizar_procesos(procesos), 120)
        if r.abortado:
            return
        datos = r.datos if isinstance(r.datos, list) else [r.datos] if isinstance(r.datos, dict) else None
        if datos is None:
            self.consola.agregar("No se pudieron cerrar (PowerShell no respondió).", "aviso")
            return
        cerrados, fallos = resumir_finalizados(datos)
        if cerrados:
            self.consola.agregar("✓ Se cerraron: " + ", ".join(cerrados) + ".", "ok")
            p.setdefault("finalizados", []).extend(cerrados)
        if fallos:
            self.consola.agregar("No se pudieron finalizar: " + "; ".join(fallos[:6])
                                 + ("" if self.es_admin else ". Sin permisos de administrador no se pueden finalizar "
                                                             "los que corren como administrador") + ".", "aviso")

    def _preguntar_abiertos(self, p: dict, carpeta: str, finalizables: list, intocables: list) -> str:
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Icon.Warning)
        caja.setWindowTitle(APP_NOMBRE)

        def lineas(procesos: list, nota: str = "") -> list[str]:
            return [f"• {n}" + (f" ({c} procesos)" if c > 1 else "") + (f" — usa {a}" if a else "") + nota
                    for n, c, a in agrupar_procesos(procesos)]
        lista = (lineas(finalizables) + lineas(intocables, " (de Windows: no se cierra)"))[:12]
        caja.setText(f"«{p['nombre']}» está en uso ahora mismo por:\n\n" + "\n".join(lista) + "\n\nSi siguen "
                     "abiertos, el instalador puede fallar («otra aplicación lo está usando») o dejar la actualización "
                     "a medias.\n\nCiérralos tú (guarda antes lo que tengas abierto) y pulsa «Ya los cerré», o deja "
                     "que la app los cierre.")
        caja.setInformativeText(
            ("«Finalizarlos y seguir»: se les pide cerrarse y, si siguen abiertos a los 10 s, se finalizan: "
             "pierdes lo que no hayas guardado en ellos.\n" if finalizables else "")
            + f"Carpeta revisada: {carpeta}"
            + ("" if self.es_admin else "\nSin permisos de administrador no se ven ni se pueden finalizar los "
                                        "programas que corren como administrador."))
        b_revisar = caja.addButton("Ya los cerré: revisar otra vez", QMessageBox.ButtonRole.AcceptRole)
        b_finalizar = (caja.addButton("Finalizarlos y seguir", QMessageBox.ButtonRole.DestructiveRole)
                       if finalizables else None)
        b_seguir = caja.addButton("Actualizar de todos modos", QMessageBox.ButtonRole.ActionRole)
        caja.addButton("Saltar este programa", QMessageBox.ButtonRole.RejectRole)
        caja.setDefaultButton(b_revisar)
        caja.exec()
        if caja.clickedButton() is b_revisar:
            return "revisar"
        if b_finalizar is not None and caja.clickedButton() is b_finalizar:
            return "finalizar"
        return "seguir" if caja.clickedButton() is b_seguir else "omitir"

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
        if es_distribucion_conda(p["id"]):
            # Nunca con winget: desinstala la anterior (con el entorno base) y, si falla, te quedas sin conda
            if not self.sin_dialogos:
                caja = QMessageBox(self)
                caja.setIcon(QMessageBox.Icon.Information)
                caja.setWindowTitle(APP_NOMBRE)
                caja.setText(f"«{p['nombre']}» no se actualiza desde aquí.\n\n{MOTIVO_CONDA}")
                caja.setInformativeText("Abre «Miniforge Prompt» (o «Anaconda Prompt») y escribe el comando.")
                b_copiar = caja.addButton("Copiar el comando de conda", QMessageBox.ButtonRole.AcceptRole)
                caja.addButton("Cerrar", QMessageBox.ButtonRole.RejectRole)
                caja.exec()
                if caja.clickedButton() is b_copiar:
                    self._copiar("conda update -n base --all", "Comando de conda copiado")
            return
        comando = comando_visible(self._args_actualizar(p))
        opciones = self.opciones()
        if not self._confirmar_inicio(
                f"«{p['nombre']}» ({p['id']})\nOrigen: {p['origen']} · {p['instalada']} → {p['disponible']}\n\n"
                f"Motivo de la revisión manual:\n{p['motivo']}\n\nSe ejecutará:\n{comando}\n\n"
                "Actualízalo solo si confías en este paquete.", self._aviso_finalizar(opciones)):
            return
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
        copiables = [("Copiar enlace de descarga", v["url"])] if v.get("url") else []
        copiables += [("Copiar comando", comando_visible(self._args_actualizar(p))), ("Copiar Id", p["id"])]
        return DialogoTexto(self, p["nombre"], "Datos del manifiesto oficial que winget va a usar.", v["show"],
                            datos=datos, titulo_texto="SALIDA COMPLETA DE WINGET SHOW", copiables=copiables)

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
        if self._seleccion_reabierta is not None:
            # Recién reabierta como administrador: lo mismo que estaba marcado en la otra copia
            self._seleccion = {c for c, p in nuevos.items()
                               if p["id"].lower() in self._seleccion_reabierta and p["grupo"] == "lote"}
            self._seleccion_reabierta = None
        elif not self._analizado:
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
            partes = [f"{ICONOS_TIPO.get(t, '•')} {x}" for t, x in v.get("partes") or [(v["tipo"], v["texto"])]]
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
        it.setData(ROL_ORDEN, orden_de_estado(v.get("tipo")))
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
        estado.setData(ROL_ORDEN, orden_de_estado(tipo))
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

    def _menu_tabla(self, t: QTableWidget, pos):
        it = t.itemAt(pos)
        if it is None:
            return
        clave = self._clave_de_fila(t, it.row())
        p = self._paquetes.get(clave)
        if p is None:
            return
        t.selectRow(it.row())
        v = p["verif"]
        menu = QMenu(self)
        if v.get("url"):
            a = menu.addAction(f"Copiar enlace de descarga ({dominio(v['url'])})",
                               lambda: self._copiar(v["url"], "Enlace de descarga copiado"))
            a.setToolTip(v["url"])
        elif v.get("show"):
            menu.addAction("Sin enlace de descarga (el manifiesto no lo trae)").setEnabled(False)
        else:
            a = menu.addAction("Copiar enlace de descarga (lee el manifiesto)", lambda: self._copiar_enlace(clave))
            a.setEnabled(self._flujo is None and bool(self._seguridad))
        menu.addAction("Copiar comando", lambda: self._copiar(comando_visible(self._args_actualizar(p)),
                                                               "Comando copiado"))
        menu.addAction("Copiar Id", lambda: self._copiar(p["id"], "Id copiado"))
        menu.addSeparator()
        menu.addAction("Ver detalles (winget show)", lambda: self._detalles(clave))
        if (v.get("firma") or {}).get("tipo") == "sin_firma":
            menu.addAction("Aceptar sin firma (el autor no firma)", lambda: self._aceptar_sin_firma(p["id"]))
        if t is self.tabla:
            menu.addSeparator()
            if p["id"].lower() in self._ignorados():
                menu.addAction("Dejar de ignorar", lambda: self._ignorar(p["id"], False))
            else:
                menu.addAction("Ignorar este paquete", lambda: self._ignorar(p["id"], True))
        menu.setToolTipsVisible(True)
        menu.exec(t.viewport().mapToGlobal(pos))

    def _copiar(self, texto: str, aviso: str):
        QApplication.clipboard().setText(texto)
        self.estado(f"✓ {aviso}: {texto}")

    def _copiar_enlace(self, clave: str):
        """Si el manifiesto aún no se leyó, lo lee (winget show) y luego copia el enlace del instalador."""
        p = self._paquetes.get(clave)
        if p is None or self._flujo is not None or not self._seguridad:
            return

        def copiar():
            url = p["verif"].get("url")
            if url:
                self._copiar(url, "Enlace de descarga copiado")
                self.consola.agregar(f"Enlace de descarga de {p['nombre']} copiado: {url}", "ok")
            else:
                self.estado(f"El manifiesto de {p['nombre']} no trae un enlace de descarga.")

        def flujo():
            yield from self._pasos_verificar(p, False, estricto=False)
        self._iniciar_flujo(flujo(), "detalles", f"Leyendo el manifiesto de {p['nombre']}…", al_terminar=copiar)

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
        self.btn_admin.setEnabled(libre)
        self.btn_store.setEnabled(libre)
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

    def _cambiar_pinning_store(self):
        """Activa o quita BypassCertificatePinningForMicrosoftStore (opción de administrador de winget)."""
        seg = self._seguridad or {}
        if self._flujo is not None or not seg.get("winget"):
            return
        activar = not seg.get("sin_pinning_store")
        args = ["settings", "--enable" if activar else "--disable", AJUSTE_PINNING_STORE]
        if not self.sin_dialogos:
            caja = QMessageBox(self)
            caja.setWindowTitle(APP_NOMBRE)
            if not self.es_admin:
                caja.setIcon(QMessageBox.Icon.Information)
                caja.setText("Es una opción de administrador de winget: abre la app como administrador y vuelve a "
                             "pulsar el botón.\n\nO, en una terminal como administrador:\nwinget " + " ".join(args))
                b_admin = caja.addButton("Reabrir como administrador", QMessageBox.ButtonRole.AcceptRole)
                caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
                caja.exec()
                if caja.clickedButton() is b_admin:
                    self._reabrir_admin()
                return
            quien = seg.get("https_interceptado") or "tu antivirus"
            if activar:
                caja.setIcon(QMessageBox.Icon.Warning)
                caja.setText(f"winget dejará de exigir el certificado propio de Microsoft para la Microsoft Store "
                             f"(«{AJUSTE_PINNING_STORE}»). Seguirá comprobando que Windows confíe en el certificado, "
                             f"que ahora es el de {quien}.\n\nAsí vuelven a salir y a actualizarse las apps de la "
                             "Store, pero si alguien suplantara la Store con un certificado que tu equipo acepte, "
                             "winget ya no lo notaría. El repositorio winget no cambia: su catálogo va firmado y "
                             "cada instalador se comprueba con su SHA256.")
                caja.setInformativeText("Se puede revertir con el mismo botón. Es lo mismo que ejecutar, como "
                                        "administrador: winget " + " ".join(args))
                b_si = caja.addButton("Permitirlo", QMessageBox.ButtonRole.AcceptRole)
            else:
                caja.setIcon(QMessageBox.Icon.Question)
                caja.setText("winget volverá a exigir el certificado de Microsoft para la Store "
                             f"(«{AJUSTE_PINNING_STORE}» desactivado)."
                             + (f"\n\nComo {quien} sigue inspeccionando tu HTTPS, la Store volverá a dar el error "
                                "0x8A15005E." if seg.get("https_interceptado") else ""))
                b_si = caja.addButton("Volver a exigirlo", QMessageBox.ButtonRole.AcceptRole)
            caja.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            caja.exec()
            if caja.clickedButton() is not b_si:
                return
        elif not self.es_admin:
            return

        def flujo():
            self.consola.agregar("▶ " + comando_visible(args), "titulo")
            r = yield self._winget(seg["winget"], args, True, 60)
            if r.abortado:
                return
            if r.codigo == 0:
                self.consola.agregar(f"✓ «{AJUSTE_PINNING_STORE}» " + ("activado" if activar else "desactivado")
                                     + ": se vuelve a buscar para leerlo y ver la Store.", "ok")
            else:
                self.salio_bien = False
                self.consola.agregar(f"winget no pudo cambiar el ajuste ({codigo_hex(r.codigo)}).", "error")
        self._iniciar_flujo(flujo(), "ajuste", "Cambiando el ajuste de winget…",
                            al_terminar=lambda: self.salio_bien and self.analizar(False))

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
        sin_pinning = bool(seg and seg.get("sin_pinning_store"))
        self.btn_store.setVisible(bool(seg and seg.get("winget") and (seg.get("https_interceptado") or sin_pinning)))
        self.btn_store.setText("Volver a exigir el certificado de la Store…" if sin_pinning
                               else "Permitir la Store con la inspección HTTPS…")
        self.btn_store.setToolTip(f"winget settings --{'disable' if sin_pinning else 'enable'} {AJUSTE_PINNING_STORE}"
                                  " (necesita administrador)")
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
            comprobar_fila_reporte(f, actual)
            if actual is None:
                continue
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

# ═════════════════════════════════════════════════════════════════════════════
# ACTUALIZAR LA APP (releases de GitHub)
# ═════════════════════════════════════════════════════════════════════════════

DEFAULT_ACTUALIZAR_APP = {
    "buscar_al_abrir": True,
    "ultima_revision": 0.0,     # time.time() de la última vez que GitHub respondió
    "etag": "",                 # con él, GitHub responde 304 si nada cambió (y no gasta de su límite)
    "release": None,            # lo último que se leyó de GitHub (ver leer_release)
    "omitida": "",              # versión de la que pediste no volver a avisar
}
INTERVALO_REVISION_APP = 24 * 3600
ESPERA_REVISION_AL_ABRIR = 4000         # ms: que la ventana ya esté lista antes de consultar
RE_VERSION_RELEASE = re.compile(r"\d[\w.+-]*")
RE_INSTALADOR_APP = re.compile(rf"^{APP_ID}_Setup_v?(\d[\w.]*)\.exe$", re.I)
HOSTS_DESCARGA_APP = ("github.com", "githubusercontent.com")
CARPETA_DESCARGA_APP = CARPETA_DATOS / "actualizacion"
ARG_ACTUALIZACION = "--actualizacion="  # «--actualizacion=1.4.0:0»: el ayudante la volvió a abrir tras instalar
VARIABLE_RELEASE_PRUEBA = "UTILIDADES_RELEASE_URL"     # pruebas: un JSON local en vez de la API de GitHub

# Cómo terminó el instalador: códigos de salida de Inno Setup y los del ayudante («hash», «falta», «inicio»)
CODIGOS_INSTALADOR = {
    "1": "el instalador no pudo arrancar (o no se dio el permiso de administrador)",
    "2": "se canceló antes de instalar",
    "3": "el instalador falló al prepararse",
    "4": "el instalador falló a mitad de la instalación",
    "5": "se canceló a mitad de la instalación",
    "7": "el instalador no pudo seguir (algún programa tenía sus archivos en uso)",
    "8": "Windows necesita reiniciarse antes de instalar",
    "hash": "el instalador cambió después de descargarlo (su SHA256 ya no coincidía) y no se abrió",
    "falta": "el instalador descargado ya no estaba (¿lo puso en cuarentena el antivirus?)",
    "inicio": "Windows o el antivirus no dejaron abrir el instalador",
}


def repo_de_github() -> str:
    """«dueño/repositorio» de APP_REPO."""
    return APP_REPO.rstrip("/").split("github.com/", 1)[-1]


def url_ultima_release() -> str:
    return os.environ.get(VARIABLE_RELEASE_PRUEBA) or f"https://api.github.com/repos/{repo_de_github()}/releases/latest"


def comparar_versiones(a: str | None, b: str | None) -> int | None:
    """-1, 0 o 1 según «a» sea menor, igual o mayor que «b» (1.3 = 1.3.0). None si alguna no se entiende."""
    x, y = numeros_de_version(a), numeros_de_version(b)
    if x is None or y is None:
        return None
    n = max(len(x), len(y))
    x, y = x + [0] * (n - len(x)), y + [0] * (n - len(y))
    return (x > y) - (x < y)


def fecha_legible(marca: float) -> str:
    """«hoy 21:55», «ayer 09:10» o «2026-10-28 09:10»."""
    import datetime
    d = datetime.datetime.fromtimestamp(marca)
    dia = {0: "hoy", 1: "ayer"}.get((datetime.date.today() - d.date()).days, f"{d:%Y-%m-%d}")
    return f"{dia} {d:%H:%M}"


def leer_release(datos: dict) -> dict | None:
    """
    Lo que la app usa de una release de GitHub: versión, notas, página y el instalador con su tamaño y el
    SHA256 que publica GitHub. None si es borrador, prerelease o su etiqueta no es una versión.
    """
    if not isinstance(datos, dict) or datos.get("draft") or datos.get("prerelease"):
        return None
    version = str(datos.get("tag_name") or "").strip().lstrip("vV")
    if not RE_VERSION_RELEASE.fullmatch(version):
        return None
    instalador = None
    for a in datos.get("assets") or []:
        m = RE_INSTALADOR_APP.match(str(a.get("name") or ""))
        if not m or not a.get("browser_download_url"):
            continue
        sha = str(a.get("digest") or "").lower().removeprefix("sha256:")
        candidato = {"nombre": a["name"], "url": str(a["browser_download_url"]), "tamano": int(a.get("size") or 0),
                     "sha256": sha if re.fullmatch(r"[0-9a-f]{64}", sha) else None}
        if instalador is None or comparar_versiones(m.group(1), version) == 0:
            instalador = candidato
    return {"version": version, "titulo": str(datos.get("name") or f"v{version}"),
            "notas": str(datos.get("body") or ""), "fecha": str(datos.get("published_at") or "")[:10],
            "pagina": str(datos.get("html_url") or f"{APP_REPO}/releases"), "instalador": instalador}


def consultar_ultima_release(etag: str = "") -> dict:
    """
    La última release publicada (corre en otro hilo): {"codigo", "release", "etag"}. Código 304 = nada
    cambió desde la consulta de ese etag; 404 = el repositorio aún no tiene releases.
    """
    import urllib.error
    import urllib.request
    cabeceras = {"Accept": "application/vnd.github+json", "User-Agent": f"{APP_ID}/{APP_VERSION}"}
    if etag:
        cabeceras["If-None-Match"] = etag
    try:
        with urllib.request.urlopen(urllib.request.Request(url_ultima_release(), headers=cabeceras), timeout=10) as r:
            datos = json.loads(r.read().decode("utf-8"))
            return {"codigo": 200, "release": leer_release(datos), "etag": r.headers.get("ETag") or ""}
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return {"codigo": 304, "release": None, "etag": etag}
        if e.code == 404:
            return {"codigo": 404, "release": None, "etag": ""}
        if e.code in (403, 429):
            raise RuntimeError("GitHub limitó las consultas desde tu conexión; se reintenta más tarde") from None
        raise


def describir_error_red(e: Exception) -> str:
    import socket
    import ssl
    import urllib.error
    motivo = e.reason if isinstance(e, urllib.error.URLError) and not isinstance(e, urllib.error.HTTPError) else e
    if isinstance(motivo, TimeoutError):
        return "GitHub tardó demasiado en responder"
    if isinstance(motivo, ssl.SSLError):
        return f"falló la conexión segura con GitHub (¿un antivirus revisa HTTPS?): {motivo}"
    if isinstance(motivo, (socket.gaierror, ConnectionError)):
        return "sin conexión a internet (o GitHub no responde)"
    if isinstance(e, urllib.error.HTTPError):
        return f"GitHub respondió {e.code} {e.reason}"
    return str(e) if isinstance(e, (RuntimeError, ValueError)) else f"{type(e).__name__}: {e}"


def host_permitido(url: str) -> bool:
    """El instalador solo se baja de GitHub (github.com y sus servidores de descargas, siempre por HTTPS)."""
    p = urllib.parse.urlparse(url)
    if p.scheme == "file":
        return bool(os.environ.get(VARIABLE_RELEASE_PRUEBA))        # solo en las pruebas
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host == h or host.endswith("." + h) for h in HOSTS_DESCARGA_APP)


def instalada_con_instalador() -> bool:
    """La app corre desde donde la dejó su instalador de Inno Setup (que pone ahí unins000.exe)."""
    return forma_de_ejecucion() == "PyInstaller" and (carpeta_app() / "unins000.exe").is_file()


def control_inteligente_activo() -> bool:
    """El Control inteligente de aplicaciones de Windows 11, activado: bloquea programas sin firma reconocida."""
    if not ES_WINDOWS:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            return winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")[0] == 1
    except OSError:
        return False


def script_firmas(rutas: list[str]) -> str:
    """Estado, firmante y huella del certificado de cada archivo (Get-AuthenticodeSignature)."""
    return ("$r = @(foreach ($f in @(" + ", ".join(ps_texto(x) for x in rutas) + ")) { "
            "$s = Get-AuthenticodeSignature -LiteralPath $f; [ordered]@{ Estado = [string]$s.Status; "
            "Firmante = if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { $null }; "
            "Huella = if ($s.SignerCertificate) { $s.SignerCertificate.Thumbprint } else { $null } } }); "
            "'" + MARCA_JSON + "' + (ConvertTo-Json -InputObject $r -Compress)")


def descargar_instalador_app(t: Tarea, instalador: dict, carpeta: Path) -> dict:
    """
    Descarga el instalador de la versión nueva (en otro hilo) y lo comprueba: que venga de GitHub, su tamaño,
    el SHA256 que publica GitHub y su firma digital (junto con la de esta versión, para compararlas). Se baja
    a un .part que solo se renombra si todo coincide. Devuelve {"ruta", "sha256", "firmas"}.
    """
    import hashlib
    import urllib.request
    sha_esperado = str(instalador.get("sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha_esperado):
        raise ValueError("GitHub no publicó el SHA256 de este instalador: sin él no se puede comprobar")
    if not host_permitido(instalador.get("url") or ""):
        raise ValueError(f"El enlace del instalador no es de GitHub: {instalador.get('url')}")
    carpeta.mkdir(parents=True, exist_ok=True)
    for viejo in carpeta.iterdir():             # lo de otras veces: descargas a medias o versiones viejas
        if viejo.is_file():
            try:
                viejo.unlink()
            except OSError:
                pass
    destino = carpeta / instalador["nombre"]
    parcial = destino.with_name(destino.name + ".part")
    esperado = int(instalador.get("tamano") or 0)
    h, hecho = hashlib.sha256(), 0
    try:
        pedido = urllib.request.Request(instalador["url"], headers={"User-Agent": f"{APP_ID}/{APP_VERSION}"})
        with urllib.request.urlopen(pedido, timeout=30) as r, open(parcial, "wb") as fh:
            if not host_permitido(r.geturl()):
                raise ValueError(f"La descarga se desvió a un sitio que no es de GitHub ({dominio(r.geturl())})")
            total = esperado or int(r.headers.get("Content-Length") or 0)
            while True:
                t.revisar()
                bloque = r.read(1 << 17)
                if not bloque:
                    break
                fh.write(bloque)
                h.update(bloque)
                hecho += len(bloque)
                t.progreso(hecho, total, f"Descargando… {formatear_bytes(hecho)}"
                                         + (f" de {formatear_bytes(total)}" if total else ""))
        if esperado and hecho != esperado:
            raise ValueError(f"Se descargaron {hecho:,} bytes y GitHub dice {esperado:,}: la descarga quedó incompleta")
        if h.hexdigest() != sha_esperado:
            raise ValueError("El SHA256 de lo descargado no coincide con el que publica GitHub (se borró)")
        os.replace(parcial, destino)
    finally:
        if parcial.exists():
            try:
                parcial.unlink()
            except OSError:
                pass
    t.progreso(0, 0, "Revisando la firma digital…")
    rutas = [str(destino)] + ([sys.executable] if forma_de_ejecucion() == "PyInstaller" else [])
    firmas = None
    try:
        programa, args = comando_powershell(script_firmas(rutas))
        salida = ejecutar_cancelable(t, [programa] + args, timeout=90, env=entorno_powershell()).stdout
        linea = next((x for x in salida.splitlines() if x.startswith(MARCA_JSON)), None)
        firmas = json.loads(linea[len(MARCA_JSON):]) if linea else None
    except Cancelado:
        raise
    except Exception:
        pass
    return {"ruta": str(destino), "sha256": sha_esperado, "firmas": firmas if isinstance(firmas, list) else None}


def evaluar_firma_instalador(firmas: list | None) -> tuple[str, str]:
    """
    (tipo, texto) de la firma del instalador, comparada con la de esta versión (si está compilada).
    «error» = no se instala: lo alteraron después de firmarlo, o tu versión está firmada y él no lo está
    con el mismo certificado.
    """
    if not firmas:
        return "aviso", "No se pudo revisar la firma digital (PowerShell no respondió); el SHA256 sí coincide."
    inst = firmas[0] or {}
    actual = (firmas[1] or {}) if len(firmas) > 1 else None
    nombre = nombre_del_certificado(inst.get("Firmante"))
    if inst.get("Estado") == "HashMismatch":
        return "error", "La firma digital del instalador no corresponde a su contenido: lo modificaron después de firmarlo."
    if actual and actual.get("Huella"):
        if inst.get("Huella") == actual["Huella"]:
            return "ok", f"Firmado con el mismo certificado que tu versión ({nombre})."
        return "error", (f"Tu versión está firmada por {nombre_del_certificado(actual.get('Firmante'))} y el "
                         "instalador " + (f"por otro certificado ({nombre})." if inst.get("Huella") else "no tiene firma."))
    if inst.get("Estado") == "Valid":
        return "ok", f"Firma digital válida: {nombre}."
    if inst.get("Huella"):
        return "info", f"Firmado por {nombre}, con un certificado que Windows no reconoce ({inst.get('Estado')})."
    return "info", "Sin firma digital" + (", igual que tu versión actual." if actual is not None else ".")


def argumentos_instalador(silencioso: bool, registro: Path) -> str:
    """
    Parámetros de Inno Setup. /SILENT: sin preguntas, solo la ventana de progreso, en la misma carpeta y con
    las opciones de la instalación anterior. /CLOSEAPPLICATIONS por si la app aún no terminó de cerrarse, y
    /NORESTARTAPPLICATIONS porque la vuelve a abrir el ayudante (si no, se abriría dos veces).
    """
    args = (["/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS"] if silencioso else [])
    return " ".join(args + ["/SP-", "/NORESTART", f'/LOG="{registro}"'])


def script_ayudante_actualizar(instalador: str, sha256: str, argumentos: str, pid: int, app: str,
                               version: str, silencioso: bool) -> str:
    """
    El PowerShell aparte (sin ventana) que sigue vivo cuando la app se cierra: espera a que se cierre,
    vuelve a comprobar el SHA256 justo antes de abrir el instalador (Inno Setup pide el permiso de
    administrador) y al terminar vuelve a abrir la app con tus permisos normales, diciéndole cómo fue
    («--actualizacion=versión:código»). Con el asistente, si terminó bien, la abre el propio instalador.
    """
    return (f"try {{ Wait-Process -Id {int(pid)} -Timeout 60 -ErrorAction Stop }} catch {{ }}; "
            f"$f = {ps_texto(instalador)}; $codigo = 'inicio'; "
            f"try {{ if (-not (Test-Path -LiteralPath $f)) {{ $codigo = 'falta' }} "
            f"elseif ((Get-FileHash -LiteralPath $f -Algorithm SHA256 -ErrorAction Stop).Hash -ne "
            f"{ps_texto(sha256.upper())}) {{ $codigo = 'hash' }} "
            f"else {{ $p = Start-Process -FilePath $f -ArgumentList {ps_texto(argumentos)} -PassThru -Wait; "
            f"$codigo = [string]$p.ExitCode }} }} catch {{ }}; "
            f"if ({'$true' if silencioso else '$false'} -or $codigo -ne '0') {{ Start-Process -FilePath {ps_texto(app)} "
            f"-ArgumentList ({ps_texto(f'{ARG_ACTUALIZACION}{version}:')} + $codigo) }}")


def lanzar_ayudante_actualizar(script: str) -> str | None:
    """Arranca el ayudante sin ventana y separado de la app (sigue vivo al cerrarla). None = arrancó."""
    programa, args = comando_powershell(script)
    flags = FLAGS_SIN_VENTANA | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    error: OSError | None = None
    # Fuera del «job» de la app si se puede (si la abrió otro programa que cierra todo lo suyo al salir)
    for separar in (getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0), 0):
        try:
            CARPETA_DESCARGA_APP.mkdir(parents=True, exist_ok=True)     # el ayudante no se queda en la de la app
            subprocess.Popen([programa] + args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=flags | separar, env=entorno_powershell(),
                             cwd=str(CARPETA_DESCARGA_APP))
            return None
        except OSError as e:
            error = e
    return f"{type(error).__name__}: {error}"


def resultado_de_actualizacion(argv: list[str]) -> tuple[str, str] | None:
    """(versión que se instalaba, código) si el ayudante volvió a abrir la app tras el instalador."""
    for a in argv:
        if a.startswith(ARG_ACTUALIZACION):
            version, _, codigo = a[len(ARG_ACTUALIZACION):].partition(":")
            return version, codigo
    return None


class ActualizadorApp(QObject):
    """
    ¿Hay una versión nueva de la app en GitHub? Se consulta al abrir (si está activado y pasó un día desde
    la última vez) o con «Buscar ahora»: una sola consulta pequeña, en otro hilo y con ETag (si nada cambió,
    GitHub responde 304 y no gasta de su límite de 60 por hora). Sin internet no dice nada al abrir.
    """
    cambio = pyqtSignal()
    _respuesta = pyqtSignal(object)

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.cfg = config.seccion("actualizar_app")
        for clave, valor in DEFAULT_ACTUALIZAR_APP.items():
            self.cfg.setdefault(clave, copy.deepcopy(valor))
        self.buscando = False
        self.error = ""
        self.pospuesta = False          # «Más tarde»: no vuelve a avisar en esta sesión
        self._respuesta.connect(self._recibir)

    def release(self) -> dict | None:
        """La última release que se leyó de GitHub (aunque no sea más nueva)."""
        r = self.cfg.get("release")
        return r if isinstance(r, dict) and numeros_de_version(r.get("version")) else None

    def nueva(self) -> dict | None:
        """La release de GitHub, si es más nueva que esta versión."""
        r = self.release()
        return r if r and comparar_versiones(r["version"], APP_VERSION) == 1 else None

    def debe_avisar(self) -> bool:
        r = self.nueva()
        return r is not None and not self.pospuesta and r["version"] != self.cfg.get("omitida")

    def al_abrir(self):
        """Avisa con lo que ya se sabía y, si toca, consulta GitHub unos segundos después (sin trabar nada)."""
        self.cambio.emit()
        transcurrido = time.time() - float(self.cfg.get("ultima_revision") or 0)
        if self.cfg.get("buscar_al_abrir") and not 0 <= transcurrido < INTERVALO_REVISION_APP:
            QTimer.singleShot(ESPERA_REVISION_AL_ABRIR, self.buscar)

    def buscar(self):
        if self.buscando:
            return
        self.buscando, self.error = True, ""
        self.cambio.emit()
        etag = str(self.cfg.get("etag") or "")

        def trabajar():
            try:
                r = consultar_ultima_release(etag)
            except Exception as e:
                r = {"error": describir_error_red(e)}
            try:
                self._respuesta.emit(r)
            except RuntimeError:            # la app ya se cerró
                pass
        threading.Thread(target=trabajar, daemon=True, name="buscar_version_app").start()

    def _recibir(self, r: dict):
        self.buscando = False
        if "error" in r:
            self.error = r["error"]
        else:
            self.cfg["ultima_revision"] = time.time()
            if r["codigo"] != 304:
                self.cfg["release"], self.cfg["etag"] = r["release"], r["etag"]
            self.config.guardar()
        self.cambio.emit()

    def cambiar_buscar_al_abrir(self, activo: bool):
        self.cfg["buscar_al_abrir"] = bool(activo)
        self.config.guardar()

    def posponer(self):
        self.pospuesta = True
        self.cambio.emit()

    def omitir(self):
        r = self.nueva()
        if r is not None:
            self.cfg["omitida"] = r["version"]
            self.config.guardar()
        self.cambio.emit()

    def texto_estado(self) -> tuple[str, str]:
        """(texto, clase del QLabel) para «Acerca de»."""
        if self.buscando:
            return "Buscando en GitHub…", "suave"
        cuando = float(self.cfg.get("ultima_revision") or 0)
        revisado = f" Revisado: {fecha_legible(cuando)}." if cuando else ""
        if self.error:
            return f"No se pudo revisar: {self.error}.{revisado}", "aviso"
        r = self.nueva()
        if r is not None:
            omitida = " (pediste no avisar de esta)" if r["version"] == self.cfg.get("omitida") else ""
            return f"Hay una versión nueva: {r['version']}{omitida}. Tienes la {APP_VERSION}.{revisado}", "ok"
        if not cuando:
            return "Aún no se ha revisado.", "suave"
        ultima = self.release()
        if ultima is None:
            return f"Aún no hay versiones publicadas en GitHub.{revisado}", "suave"
        if comparar_versiones(APP_VERSION, ultima["version"]) == 1:
            return (f"Tienes la {APP_VERSION}, más nueva que la última publicada en GitHub "
                    f"({ultima['version']}).{revisado}"), "suave"
        return f"Tienes la versión más reciente ({APP_VERSION}).{revisado}", "suave"


class AvisoApp(QFrame):
    """Franja bajo la barra superior: hay una versión nueva, o cómo terminó la actualización."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("avisoApp")
        h = QHBoxLayout(self)
        h.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)
        h.setSpacing(SPACING_SM)
        self.lbl = QLabel()
        self.lbl.setWordWrap(True)
        self.lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        h.addWidget(self.lbl, 1)
        self._botones = QHBoxLayout()
        self._botones.setSpacing(SPACING_SM)
        h.addLayout(self._botones)
        self.tipo = ""
        self.hide()

    def mostrar(self, texto: str, tipo: str, botones: list[tuple]):
        """tipo: «info» (versión nueva), «ok» o «aviso». botones: [(texto, clase, al pulsar)]."""
        self.tipo = tipo
        self.setProperty("tipo", tipo)
        refrescar_estilo(self)
        refrescar_estilo(self.lbl)
        self.lbl.setText(texto)
        while self._botones.count():
            w = self._botones.takeAt(0).widget()
            if w is not None:
                w.hide()            # deleteLater no lo quita hasta volver al bucle de eventos
                w.deleteLater()
        for nombre, clase, accion in botones:
            b = boton(nombre, clase)
            b.clicked.connect(accion)
            self._botones.addWidget(b)
        self.show()

    def ocultar(self):
        self.tipo = ""
        self.hide()


def navegador_notas(release: dict) -> QTextBrowser:
    """Las notas de una release (Markdown de GitHub) con sus enlaces."""
    notas = QTextBrowser()
    notas.setObjectName("notasRelease")
    notas.setOpenExternalLinks(True)
    notas.setMarkdown(release.get("notas") or "_Esta versión no trae notas._")
    return notas


def ver_novedades(parent: QWidget, release: dict):
    d = QDialog(parent)
    d.setWindowTitle(f"Novedades de la versión {release['version']}")
    v = QVBoxLayout(d)
    v.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
    v.setSpacing(SPACING_MD)
    t = QLabel(f"{APP_NOMBRE} {release['version']}")
    t.setProperty("class", "titulo-pagina")
    v.addWidget(t)
    v.addWidget(navegador_notas(release), 1)
    fila = QHBoxLayout()
    fila.addStretch(1)
    b = boton("Cerrar", "primario")
    b.clicked.connect(d.accept)
    fila.addWidget(b)
    v.addLayout(fila)
    d.resize(720, 560)
    d.exec()


class DialogoActualizarApp(QDialog):
    """
    Novedades de la versión nueva y cómo instalarla: descarga el instalador de GitHub, lo comprueba
    (tamaño, SHA256 y firma) y deja un ayudante instalándolo mientras la app se cierra.
    """

    def __init__(self, ventana, release: dict):
        super().__init__(ventana)
        self.ventana, self.release = ventana, release
        self.tarea: Tarea | None = None
        self.setWindowTitle(f"Actualizar a la versión {release['version']}")
        v = QVBoxLayout(self)
        v.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        v.setSpacing(SPACING_MD)
        t = QLabel(f"{APP_NOMBRE} {release['version']}")
        t.setProperty("class", "titulo-pagina")
        v.addWidget(t)
        inst = release.get("instalador") or {}
        datos = [f"Tienes la {APP_VERSION}"]
        if release.get("fecha"):
            datos.append(f"publicada el {release['fecha']}")
        if inst.get("tamano"):
            datos.append(f"instalador de {formatear_bytes(inst['tamano'])}")
        v.addWidget(etiqueta(" · ".join(datos), "suave"))
        v.addWidget(etiqueta("NOVEDADES"))
        v.addWidget(navegador_notas(release), 1)

        # Cómo se instala: sola solo si esta copia la dejó su instalador y GitHub publica el SHA256
        self.instalable = False
        self.rb_sola = self.rb_asistente = self.btn_instalar = None
        if not instalada_con_instalador():
            motivo = ("corre desde el código fuente" if forma_de_ejecucion() == "Código fuente"
                      else "no se instaló con su instalador (es un .exe suelto)")
            v.addWidget(etiqueta(f"Esta copia {motivo}: descarga la versión nueva desde su página de GitHub.", "aviso"))
        elif not inst:
            v.addWidget(etiqueta("Esta versión no trae el instalador en GitHub: revísala en su página.", "aviso"))
        elif not inst.get("sha256"):
            v.addWidget(etiqueta("GitHub no publicó el SHA256 de este instalador y sin él no se instala sola: "
                                 "descárgalo desde su página.", "aviso"))
        else:
            self.instalable = True
            self.rb_sola = QRadioButton("Instalar sola (recomendado)")
            self.rb_asistente = QRadioButton("Con el asistente del instalador")
            grupo = QButtonGroup(self)
            for rb in (self.rb_sola, self.rb_asistente):
                grupo.addButton(rb)
            self.rb_sola.setChecked(True)
            explicaciones = (
                (self.rb_sola, "La app se cierra, Windows pide permiso de administrador una vez (se instala en Archivos "
                               "de programa) y se instala sin preguntas, en la misma carpeta y con tus mismas opciones. "
                               "Al terminar, la app se vuelve a abrir sola. Instalar implica aceptar el contrato de "
                               "licencia (EULA) de la versión nueva, que queda en la carpeta de la app."),
                (self.rb_asistente, "Ves cada paso: contrato, carpeta y accesos directos. Al final, el instalador "
                                    "ofrece abrir la app."))
            for rb, texto in explicaciones:
                v.addWidget(rb)
                lbl = etiqueta(texto, "suave")
                lbl.setContentsMargins(SPACING_LG, 0, 0, 0)
                v.addWidget(lbl)
            if control_inteligente_activo():
                v.addWidget(etiqueta("El Control inteligente de aplicaciones de Windows está activado: bloquea los "
                                     "instaladores que no tienen una firma reconocida.", "aviso"))

        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.hide()
        v.addWidget(self.barra)
        self.lbl_estado = etiqueta("", "suave")
        self.lbl_estado.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_estado.hide()
        v.addWidget(self.lbl_estado)

        fila = QHBoxLayout()
        fila.setSpacing(SPACING_SM)
        pagina = release.get("pagina") or f"{APP_REPO}/releases"
        b = boton("Ver en GitHub", None if self.instalable else "primario", pagina)
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(pagina)))
        fila.addWidget(b)
        fila.addStretch(1)
        self.btn_cerrar = boton("Cerrar")
        self.btn_cerrar.clicked.connect(self.reject)
        fila.addWidget(self.btn_cerrar)
        if self.instalable:
            self.btn_instalar = boton("Descargar e instalar", "primario")
            self.btn_instalar.clicked.connect(self._descargar)
            fila.addWidget(self.btn_instalar)
        v.addLayout(fila)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._drenar)
        pantalla = (ventana.screen() or QApplication.primaryScreen()).availableGeometry()
        self.resize(min(760, int(pantalla.width() * 0.95)), min(700, int(pantalla.height() * 0.9)))

    def _estado(self, texto: str, clase: str):
        self.lbl_estado.setText(texto)
        self.lbl_estado.setProperty("class", clase)
        refrescar_estilo(self.lbl_estado)
        self.lbl_estado.show()

    def _activar(self, activo: bool):
        for w in (self.rb_sola, self.rb_asistente, self.btn_instalar):
            w.setEnabled(activo)
        self.btn_cerrar.setText("Cerrar" if activo else "Cancelar")

    def _descargar(self):
        ocupadas = self.ventana.tareas_en_curso()
        if ocupadas:
            QMessageBox.information(self, APP_NOMBRE, "Para instalar, la app se cierra: espera a que termine lo que "
                                                      f"está en curso ({', '.join(ocupadas)}).")
            return
        self._activar(False)
        self.barra.setRange(0, 0)
        self.barra.show()
        self._estado("Conectando con GitHub…", "suave")
        self.tarea = Tarea(descargar_instalador_app, self.release["instalador"], CARPETA_DESCARGA_APP, parent=self)
        self.tarea.listo.connect(self._descargado)
        self.tarea.fallo.connect(lambda m: self._detenido(f"✗ No se descargó: {m}", "error-texto"))
        self.tarea.cancelado.connect(lambda: self._detenido("Descarga cancelada.", "suave"))
        self.tarea.start()
        self._timer.start()

    def _drenar(self):
        if self.tarea is None:
            return
        _, avance = self.tarea.tomar()
        if avance:
            actual, total, texto = avance
            if total:
                self.barra.setRange(0, 1000)
                self.barra.setValue(int(actual * 1000 / total))
            else:
                self.barra.setRange(0, 0)
            if texto:
                self._estado(texto, "suave")

    def _fin_tarea(self):
        self._timer.stop()
        if self.tarea is not None:
            self.tarea.wait()
            self.tarea = None
        self.barra.hide()

    def _detenido(self, texto: str, clase: str):
        self._fin_tarea()
        self._estado(texto, clase)
        self._activar(True)
        self.btn_instalar.setText("Reintentar")

    def _descargado(self, r: dict):
        self._fin_tarea()
        tipo, texto_firma = evaluar_firma_instalador(r["firmas"])
        marca = {"ok": "✓", "info": "•", "aviso": "⚠", "error": "✗"}[tipo]
        lineas = "✓ Tamaño y SHA256 iguales a los que publica GitHub.\n" + f"{marca} {texto_firma}"
        if tipo == "error":
            try:
                Path(r["ruta"]).unlink()
            except OSError:
                pass
            self._detenido(lineas + "\nNo se instala.", "error-texto")
            self.btn_instalar.setEnabled(False)
            return
        firma_valida = bool(r["firmas"]) and (r["firmas"][0] or {}).get("Estado") == "Valid"
        if control_inteligente_activo() and not firma_valida and QMessageBox.question(
                self, APP_NOMBRE, "El Control inteligente de aplicaciones de Windows está activado y el instalador "
                                  "no tiene una firma que Windows reconozca: lo más probable es que lo bloquee.\n\n"
                                  "¿Intentarlo de todos modos?") != QMessageBox.StandardButton.Yes:
            self._detenido(lineas + "\nNo se instaló: descárgalo desde su página de GitHub.", "aviso")
            return
        self._estado(lineas + "\nCerrando la app para instalar…", "ok")
        self._instalar(r)

    def _instalar(self, r: dict):
        silencioso = self.rb_sola.isChecked()
        version = self.release["version"]
        try:
            CARPETA_REGISTROS.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        script = script_ayudante_actualizar(
            r["ruta"], r["sha256"], argumentos_instalador(silencioso, CARPETA_REGISTROS / f"instalacion_v{version}.log"),
            os.getpid(), comando_de_la_app()[0], version, silencioso)
        motivo = lanzar_ayudante_actualizar(script)
        if motivo:
            self._detenido(f"✗ No se pudo abrir el instalador: {motivo}", "error-texto")
            return
        self.accept()
        QTimer.singleShot(0, self.ventana.cerrar_para_actualizar)

    def reject(self):
        if self.tarea is not None:          # primero se cancela la descarga; el diálogo sigue abierto
            self.tarea.cancelar()
            return
        super().reject()


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

        # ─── Versión nueva en GitHub ───
        act = ventana.actualizador
        card, lay = tarjeta("Actualizaciones de la app")
        self.lbl_version_app = etiqueta("", "suave")
        self.lbl_version_app.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl_version_app)
        self.chk_buscar_al_abrir = QCheckBox("Buscar versiones nuevas al abrir la app (una consulta a GitHub, "
                                             "como mucho una vez al día)")
        self.chk_buscar_al_abrir.setChecked(bool(act.cfg.get("buscar_al_abrir")))
        self.chk_buscar_al_abrir.toggled.connect(act.cambiar_buscar_al_abrir)
        lay.addWidget(self.chk_buscar_al_abrir)
        botones = QHBoxLayout()
        botones.setSpacing(SPACING_SM)
        self.btn_buscar_version = boton("Buscar ahora", tooltip="Consulta la última versión publicada en GitHub")
        self.btn_buscar_version.clicked.connect(act.buscar)
        botones.addWidget(self.btn_buscar_version)
        self.btn_ver_version = boton("Ver y actualizar", "primario")
        self.btn_ver_version.clicked.connect(ventana.abrir_actualizacion)
        botones.addWidget(self.btn_ver_version)
        b = boton("Versiones en GitHub", "fantasma", f"{APP_REPO}/releases")
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"{APP_REPO}/releases")))
        botones.addWidget(b)
        botones.addStretch(1)
        lay.addLayout(botones)
        v.addWidget(card)
        act.cambio.connect(self._refrescar_version)
        self._refrescar_version()

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

    def _refrescar_version(self):
        act = self.ventana.actualizador
        texto, clase = act.texto_estado()
        self.lbl_version_app.setText(texto)
        self.lbl_version_app.setProperty("class", clase)
        refrescar_estilo(self.lbl_version_app)
        self.btn_buscar_version.setEnabled(not act.buscando)
        nueva = act.nueva()
        self.btn_ver_version.setVisible(nueva is not None)
        if nueva is not None:
            self.btn_ver_version.setText(f"Ver y actualizar a la {nueva['version']}")

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
        self.actualizador = ActualizadorApp(config, self)
        # Como cmd: «Administrador:» delante del título si tiene esos permisos
        self.setWindowTitle(("Administrador: " if es_administrador() else "") + f"{APP_NOMBRE} {APP_VERSION}")
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
        self.aviso_app = AvisoApp()
        v.addWidget(self.aviso_app)
        self.actualizador.cambio.connect(self._refrescar_aviso_app)

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

    def tareas_en_curso(self) -> list[str]:
        return [n for n, p in self.paginas if p.ocupada()]

    def closeEvent(self, e):
        ocupadas = self.tareas_en_curso()
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
        self._guardar_ventana()
        e.accept()

    def _guardar_ventana(self):
        self.config.datos["pestana"] = self.tabs.currentIndex()
        self.config.datos["ventana"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.config.guardar()

    def reabrir_como_admin(self) -> bool:
        """Abre otra copia con permisos de administrador y cierra esta. False si no se pudo (o se rechazó)."""
        ocupadas = self.tareas_en_curso()
        if ocupadas:
            QMessageBox.information(self, APP_NOMBRE, f"Espera a que termine lo que está en curso "
                                                      f"({', '.join(ocupadas)}) para reabrir la app.")
            return False
        self._guardar_ventana()     # antes de abrir la otra: que arranque con el mismo tamaño y pestaña
        ok, motivo = reabrir_como_administrador()
        if not ok:
            QMessageBox.warning(self, APP_NOMBRE, f"No se reabrió como administrador.\n\n{motivo}")
            return False
        self.close()
        return True

    def tras_reabrir(self):
        pagina = dict(self.paginas)["Actualizaciones"]
        self.tabs.setCurrentWidget(pagina)
        pagina.tras_reabrir()

    # ─── Versión nueva de la app ───
    def _refrescar_aviso_app(self):
        if self.aviso_app.tipo in ("ok", "aviso"):      # cómo terminó la actualización: se queda hasta cerrarlo
            return
        nueva = self.actualizador.nueva()
        if nueva is None or not self.actualizador.debe_avisar():
            self.aviso_app.ocultar()
            return
        self.aviso_app.mostrar(
            f"⬆  Hay una versión nueva: {nueva['version']} (tienes la {APP_VERSION}).", "info",
            [("Ver y actualizar", "primario", self.abrir_actualizacion),
             ("Más tarde", None, self.actualizador.posponer),
             ("Omitir esta versión", None, self.actualizador.omitir)])

    def abrir_actualizacion(self):
        nueva = self.actualizador.nueva()
        if nueva is not None:
            DialogoActualizarApp(self, nueva).exec()

    def cerrar_para_actualizar(self):
        """El ayudante ya espera a que la app se cierre para abrir el instalador."""
        self.close()

    def tras_actualizar(self, version: str, codigo: str):
        """Al volver a abrirse tras el instalador: si quedó la versión nueva o qué pasó."""
        if (comparar_versiones(APP_VERSION, version) or 0) >= 0 and numeros_de_version(version):
            shutil.rmtree(CARPETA_DESCARGA_APP, ignore_errors=True)
            release = self.actualizador.release()
            botones = []
            if release is not None and comparar_versiones(release["version"], APP_VERSION) == 0:
                botones.append(("Novedades", None, lambda: ver_novedades(self, release)))
            self.aviso_app.mostrar(f"✓  Se actualizó a la versión {APP_VERSION}.", "ok",
                                   botones + [("Cerrar", None, self.aviso_app.ocultar)])
            return
        motivo = CODIGOS_INSTALADOR.get(codigo) or (f"el instalador terminó con el código {codigo}" if codigo
                                                    else "no se supo cómo terminó el instalador")
        registro = CARPETA_REGISTROS / f"instalacion_v{version}.log"
        botones = []
        if registro.is_file():
            botones.append(("Ver registro", None, lambda: abrir_en_sistema(registro)))
        if self.actualizador.nueva() is not None:
            botones.append(("Reintentar", "primario", self.abrir_actualizacion))
        self.aviso_app.mostrar(f"⚠  No se actualizó a la {version}: {motivo}. Sigues con la {APP_VERSION}.", "aviso",
                               botones + [("Cerrar", None, self.aviso_app.ocultar)])


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

        # 0. Sesiones: «sin guardar» solo si de verdad cambió algo respecto a la sesión elegida
        def sesiones():
            for _ in range(100):            # que termine la detección de discos de Copiar
                app.processEvents()
                time.sleep(0.01)
            detalle = {}
            for nombre in ("Copiar", "Listar rutas", "Licencias"):
                if nombre not in pag:
                    continue
                b = pag[nombre].sesiones
                al_abrir = b.modificado()
                b._sesiones()["autoprueba"] = b.obtener_estado()
                b._rellenar("autoprueba")
                b._aplicar("autoprueba")
                cargada = b.modificado()
                campo = pag[nombre].nombre_salida if hasattr(pag[nombre], "nombre_salida") else pag[nombre].txt_extra
                antes = campo.text()
                campo.setText(antes + "_x")
                cambiada = b.modificado()
                campo.setText(antes)
                deshecha = b.modificado()
                campo.setText(antes + "_y")
                b.guardar()
                guardada = b.modificado()
                campo.setText(antes)
                b._sesiones().pop("autoprueba", None)
                b._rellenar(PREDETERMINADA)
                b._aplicar(PREDETERMINADA)
                detalle[nombre] = [al_abrir, cargada, cambiada, deshecha, guardada]
            p = pag["Copiar"]
            p.chk_mt.setChecked(True)
            p.chk_auto.setChecked(True)
            p.sesiones._tomar_referencia()
            p.sp_hilos.setValue(p.sp_hilos.value() % 16 + 1)     # lo que hace la detección del disco
            detalle["hilos_auto"] = p.sesiones.modificado()
            p.sesiones._aplicar(PREDETERMINADA)
            esperado = [False, False, True, False, False]
            registrar("sesiones", all(v == esperado for k, v in detalle.items() if k != "hilos_auto")
                      and detalle["hilos_auto"] is False,
                      orden="al abrir, cargada, cambiada, deshecha, guardada", **detalle)
        probar("sesiones", sesiones)

        # 0b. La tabla final de robocopy en palabras (sin /BYTES: «29.371 g»)
        def tabla_robocopy():
            t = leer_tabla_robocopy(
                "               Total   Copiado   OmitidoNo coincidencia     ERROR    Extras\n"
                "Director.:      1866      1817       271         0         0       845\n"
                " Archivos:     12675      9713      2962         0         0      5766\n"
                "    Bytes:  29.371 g  26.965 g   2.406 g         0         0  14.887 g\n"
                "   Tiempo:   0:00:03   0:00:00                       0:00:00   0:00:03\n")
            filas = {}
            if t:
                for linea in resumen_robocopy(t, True, None)[0]:
                    celdas = [x.strip() for x in "".join(texto for texto, _ in linea).split("│")[1:-1]]
                    if celdas:
                        filas[celdas[0]] = celdas[1:]
            tiempos = leer_tiempos_robocopy("   Tiempo:   0:01:03   0:00:40                       0:00:00   0:00:03\n"
                                            "   Finalizado: viernes, 30 de octubre de 2026 04:55:30 p. m.\n")
            registrar("robocopy_tabla", bool(t) and filas.get("se copiaría (nuevo o cambiado)") == ["1,595", "9,713", "27.0 GB"]
                      and filas.get("Solo en el destino: se queda") == ["845", "5,766", "14.9 GB"]
                      and filas.get("CÓMO QUEDARÍA EL DESTINO") == ["2,711", "18,441", "44.3 GB"]
                      and bool(tiempos) and tiempos["total"] == 63 and tiempos["copiando"] == 40
                      and "2026" in (tiempos["fin"] or ""), filas=filas, tiempos=tiempos)
        probar("robocopy_tabla", tabla_robocopy)

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

        # 1b. Copiar con /MIR: borra del destino lo que no está en el origen (menos lo omitido
        # con /XD) y el registro dice cuánto borró
        def copiar_mir():
            p = pag["Copiar"]
            destino = tmp / "destino_mir"
            (destino / "carpeta_sobra").mkdir(parents=True)
            (destino / "carpeta_sobra" / "sobra.txt").write_bytes(b"s" * 10)
            (destino / "__pycache__").mkdir()                    # omitida con /XD: no se borra
            (destino / "__pycache__" / "cache.pyc").write_bytes(b"c")
            p.sin_dialogos = True
            p.origen.establecer(str(origen))
            p.destino.establecer(str(destino))
            p.chk_carpeta.setChecked(False)
            p.chk_simular.setChecked(False)
            p.txt_extra.setText("/MIR")
            p.consola.limpiar()
            p.iniciar()
            terminado = esperar(p, 120)
            p.consola._vaciar()
            texto = p.consola.toPlainText()
            p.txt_extra.setText("")
            fila_borrado = next((linea for linea in texto.splitlines() if "se BORRÓ (/MIR)" in linea), "")
            registrar("copiar_mir", terminado and not (destino / "carpeta_sobra").exists()
                      and (destino / "__pycache__" / "cache.pyc").exists()
                      and re.search(r"│\s+1 │\s+1 │\s+10 B │", fila_borrado) is not None
                      and "CÓMO QUEDÓ EL DESTINO" in texto and "no se tocaron" not in texto
                      and "Se BORRÓ del destino" in texto,
                      archivos_copiados=sum(1 for _ in destino.rglob("*.txt")), fila_borrado=fila_borrado.strip())
        if ES_WINDOWS:
            probar("copiar_mir", copiar_mir)

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
                # Del Python global: requirements_python3XX.txt, una fila por paquete y sin filas vacías entre medio
                guardado = next(iter(tmp.glob("requirements_python*.txt")), None)
                crudo = guardado.read_bytes() if guardado else b""
                p.carpeta_salida.establecer("")             # sin carpeta elegida: el global va al Escritorio
                por_defecto = p._ruta_salida()
                registrar("info_entorno", bool(p._datos and p._datos["paquetes"]) and guardado is not None
                          and b"\r\r\n" not in crudo and b"\r\n\r\n" not in crudo.strip()
                          and norm(por_defecto.parent) == norm(carpeta_escritorio()),
                          python=str(python_global), paquetes=len((p._datos or {}).get("paquetes", [])),
                          archivo=guardado.name if guardado else None, por_defecto=str(por_defecto))
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
                doc = next(iter(tmp.glob("THIRD_PARTY_NOTICES*.txt")), tmp / "THIRD_PARTY_NOTICES.txt")
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

        # 6b. Diagnósticos de Actualizaciones, sin red: tipo de instalador, inspección HTTPS, firma de lo que
        # va dentro de un zip, reporte «a medias» y Windows Installer
        def ayudas_winget():
            import zipfile
            fallos = []
            if not motivo_no_aplicable("msix", "wix", "Microsoft.PowerShell", seguro=True):
                fallos.append("msix→msi no avisado")
            if motivo_no_aplicable("exe", "wix", "7zip.7zip", seguro=True):
                fallos.append("exe→msi avisado (7-Zip sí se actualiza así)")
            if interceptor_https("CN=Avast Web/Mail Shield Root, O=Avast Web/Mail Shield") != "Avast":
                fallos.append("Avast no detectado")
            if interceptor_https("CN=Microsoft Azure RSA TLS Issuing CA 07, O=Microsoft Corporation, C=US"):
                fallos.append("certificado de Microsoft tomado por interceptado")
            # Avast inspeccionando: con y sin BypassCertificatePinningForMicrosoftStore
            datos = {"Winget": "winget", "Usado": "winget",
                     "Tls": {HOSTS_TLS[0]: "CN=Avast Web/Mail Shield Root, O=Avast Web/Mail Shield"},
                     "Ajustes": json.dumps({"adminSettings": {"InstallerHashOverride": False, AJUSTE_PINNING_STORE: True}})}
            seg = evaluar_seguridad(datos)
            if not (seg["sin_pinning_store"] and seg.get("https_interceptado") == "Avast"
                    and any("funciona igual" in t for _, t in seg["comprobaciones"])):
                fallos.append("Store permitida con Avast")
            datos["Ajustes"] = json.dumps({"adminSettings": {"InstallerHashOverride": False}})
            seg = evaluar_seguridad(datos)
            if seg["sin_pinning_store"] or not any("Permitir la Store" in t for _, t in seg["comprobaciones"]):
                fallos.append("Store bloqueada por Avast")
            comprimido = tmp / "paquete.zip"
            with zipfile.ZipFile(comprimido, "w") as z:
                z.writestr("carpeta/setup.exe", b"MZ" + b"0" * 4096)
                z.writestr("leeme.txt", b"hola")
                z.writestr("../fuera.exe", b"MZ")
            carpeta = tmp / "revision"
            carpeta.mkdir()
            internos = preparar_revision_interna(comprimido, carpeta)["internos"]
            if [n for _, n in internos] != ["carpeta/setup.exe", "../fuera.exe"] or \
                    not all(esta_dentro(r, carpeta) for r, _ in internos):
                fallos.append(f"zip: {internos}")
            firma = {"Estado": "UnknownError", "Archivo": "paquete.zip", "Sha256": "AB" * 32,
                     "Internos": [{"Estado": "Valid", "Firmante": "CN=GIGABYTE, O=GIGABYTE", "Nombre": "setup.exe"}]}
            if evaluar_firma(firma, "ab" * 32, 0)[0] != "ok":
                fallos.append(f"firma interna: {evaluar_firma(firma, 'ab' * 32, 0)}")
            if evaluar_firma(dict(firma, Internos=[], Msix={"Estado": "Valid", "Firmante": "CN=Microsoft Corporation"}),
                             "ab" * 32, 0)[0] != "ok":
                fallos.append("msix")
            detalles = leer_detalles_instalado("Versión: 7.6.7.0\nIdentificador local: MSIX\\Microsoft.PowerShell_x\n"
                                               "Categoría del instalador: msix\n")
            if detalles["categoria"] != "msix" or not detalles["local"].startswith("MSIX"):
                fallos.append(f"detalles: {detalles}")
            if evaluar_github({"repo": "a/b", "archivo": "x", "existe": True, "digest": "ab" * 32}, "AB" * 32)[0] != "ok":
                fallos.append("github")
            p = pag["Actualizaciones"]
            v = {"manifiesto": ("ok", "SHA256 · github.com"), "firma": {"tipo": "sin_firma", "texto": "sin firma"}}
            componer_verificacion(v)
            if v["tipo"] != "aviso":
                fallos.append("componer")
            fila = {"tipo": "ok", "texto": "", "antes": "1.0", "objetivo": "1.2", "despues": ""}
            comprobar_fila_reporte(fila, {"instalada": "1.1", "disponible": "1.2", "desconocida": False})
            if fila["tipo"] != "aviso" or "a medias" not in fila["texto"]:
                fallos.append(f"caso a medias: {fila}")
            # Manifiesto como el de Miniforge: en «machine» desinstala antes; en «user» winget no lo actualiza
            manifiesto = leer_manifiesto_instalador(
                "PackageIdentifier: CondaForge.Miniforge3\nInstallerType: nullsoft\nCommands:\n- conda\n- mamba\n"
                "Installers:\n- Architecture: x64\n  Scope: user\n  InstallerSwitches:\n    Custom: /InstallationType=JustMe\n"
                "  UpgradeBehavior: deny\n- Architecture: x64\n  Scope: machine\n  UpgradeBehavior: uninstallPrevious\n"
                "  ElevationRequirement: elevationRequired\nManifestType: installer\n")
            maquina = instaladores_aplicables(manifiesto, "machine", "x64")
            if [i.get("UpgradeBehavior") for i in maquina] != ["uninstallPrevious"] or manifiesto["comandos"] != ["conda", "mamba"] \
                    or [i.get("UpgradeBehavior") for i in instaladores_aplicables(manifiesto, "user", "x64")] != ["deny"]:
                fallos.append(f"manifiesto: {manifiesto}")
            if codigo_salida_instalador("Instalador con errores con el código de salida: 2") != 2:
                fallos.append("código de salida del instalador")
            if not es_distribucion_conda("CondaForge.Miniforge3") or es_distribucion_conda("Anaconda.Navigator"):
                fallos.append("distribución de conda")
            ocupado = windows_installer_ocupado()       # solo que no truene
            registrar("actualizaciones_ayudas", not fallos, fallos=fallos, windows_installer_ocupado=ocupado)
        probar("actualizaciones_ayudas", ayudas_winget)

        # 6c. Finalizar sin preguntar lo que tiene abierto un programa: con una copia de ping.exe propia,
        # lanzada desde una carpeta temporal (nunca se toca otro proceso)
        def finalizar_abiertos():
            pa = pag["Actualizaciones"]
            carpeta = tmp / "programa abierto"
            carpeta.mkdir()
            exe = carpeta / "programa_prueba.exe"
            shutil.copy(Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "PING.EXE", exe)
            proc = subprocess.Popen([str(exe), "-n", "120", "127.0.0.1"], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=FLAGS_SIN_VENTANA)
            falso = {"nombre": "Programa de prueba", "instalado": {"carpeta": str(carpeta)}}
            resultado = {}

            def flujo():
                resultado["respuesta"] = yield from pa._revisar_abiertos("", falso, "[prueba]", auto=True)
            try:
                time.sleep(0.5)
                pa._iniciar_flujo(flujo(), "prueba", "Probando…")
                esperar(pa, 120)
                for _ in range(30):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                vivo = proc.poll() is None
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
            registrar("actualizaciones_finalizar",
                      resultado.get("respuesta") == "seguir" and not vivo and falso.get("finalizados") == [exe.stem],
                      respuesta=resultado.get("respuesta"), finalizados=falso.get("finalizados"), sigue_abierto=vivo)
        if ES_WINDOWS:
            probar("actualizaciones_finalizar", finalizar_abiertos)

        # 6d. Preparación en paralelo: el segundo carril (hilo, pausa y PowerShell) y dejar una descarga
        # donde winget la reutiliza (una carpeta propia en %TEMP%\WinGet, que se borra al final)
        def preparacion_paralela():
            import hashlib
            pa = pag["Actualizaciones"]
            fallos = []
            resultado = {}

            def flujo():
                resultado["hilo"] = yield EnHilo(lambda: 6 * 7)
                yield Pausa(0.1)
                r = yield pa._powershell(f"'{MARCA_JSON}' + (ConvertTo-Json -InputObject @(1, 2) -Compress)", 60)
                resultado["ps"] = r.datos
                yield Pausa(30)                 # aquí se corta: detener() no debe esperar
                resultado["no_debia"] = True
            pa._carril.iniciar(flujo())
            limite = time.monotonic() + 60
            while "ps" not in resultado and time.monotonic() < limite:
                app.processEvents()
                time.sleep(0.01)
            pa._carril.detener()
            if resultado.get("hilo") != 42 or resultado.get("ps") != [1, 2] or "no_debia" in resultado \
                    or pa._carril.activo():
                fallos.append(f"carril: {resultado}")
            archivo = tmp / "instalador_prueba.exe"
            archivo.write_bytes(b"MZ prueba" * 100)
            sha = hashlib.sha256(archivo.read_bytes()).hexdigest()
            guardado = guardar_para_winget(archivo, "UtilidadesArchivos.Autoprueba", f"0.0.{os.getpid()}")
            ruta = Path(guardado["ruta"]) if guardado else None
            if ruta is None or ruta.name != sha or ruta.parent.parent != carpeta_temporal_winget() or archivo.exists():
                fallos.append(f"guardar: {guardado}")
            borrar_guardado_winget(guardado)
            if ruta is not None and (ruta.exists() or ruta.parent.exists()):
                fallos.append("no se borró lo guardado")
            if guardar_para_winget(archivo, "Mal:Id", "1.0") is not None:
                fallos.append("Id con «:» aceptado")
            registrar("actualizaciones_paralelo", not fallos, fallos=fallos)
        probar("actualizaciones_paralelo", preparacion_paralela)

        # 6e. Actualizar la app desde GitHub, sin internet: una release y un instalador falsos (file://).
        # No se lanza el ayudante ni se instala nada
        def actualizar_app():
            import hashlib
            fallos = []
            falso = tmp / "UtilidadesArchivos_Setup_v99.0.0.exe"
            falso.write_bytes(b"MZ instalador de prueba" * 4000)
            sha = hashlib.sha256(falso.read_bytes()).hexdigest()
            datos = {"tag_name": "v99.0.0", "name": "Prueba", "body": "## Novedades\n- algo", "draft": False,
                     "prerelease": False, "published_at": "2026-11-01T10:00:00Z", "html_url": f"{APP_REPO}/releases",
                     "assets": [{"name": "otra_cosa.zip", "size": 1, "browser_download_url": f"{APP_REPO}/x.zip"},
                                {"name": falso.name, "size": falso.stat().st_size, "digest": f"sha256:{sha}",
                                 "browser_download_url": falso.as_uri()}]}
            (tmp / "release.json").write_text(json.dumps(datos), encoding="utf-8")
            antes = os.environ.get(VARIABLE_RELEASE_PRUEBA)
            os.environ[VARIABLE_RELEASE_PRUEBA] = (tmp / "release.json").as_uri()
            act = ventana.actualizador
            try:
                for a, b, esperado in (("1.10.0", "1.9.9", 1), ("1.3", "1.3.0", 0), ("v1.2.0", "1.3.0", -1)):
                    if comparar_versiones(a, b) != esperado:
                        fallos.append(f"comparar {a} {b}")
                if leer_release(dict(datos, prerelease=True)) is not None:
                    fallos.append("prerelease aceptada")
                # La consulta, como la de al abrir: aviso arriba y botón en «Acerca de»
                act.buscar()
                limite = time.monotonic() + 20
                while act.buscando and time.monotonic() < limite:
                    app.processEvents()
                    time.sleep(0.01)
                app.processEvents()
                nueva = act.nueva() or {}
                if nueva.get("version") != "99.0.0" or (nueva.get("instalador") or {}).get("sha256") != sha:
                    fallos.append(f"consulta: {act.error or nueva}")
                if ventana.aviso_app.tipo != "info" or ventana.pagina_acerca.btn_ver_version.isHidden():
                    fallos.append("sin aviso de la versión nueva")
                # Descarga comprobada; con otro SHA256 se rechaza y no queda nada
                for sha_pedido, debe_fallar in ((sha, False), ("0" * 64, True)):
                    resultado = {}
                    t = Tarea(descargar_instalador_app, dict(nueva["instalador"], sha256=sha_pedido), tmp / "descarga")
                    t.listo.connect(lambda r, d=resultado: d.update(r))
                    t.fallo.connect(lambda m, d=resultado: d.update(error=m))
                    t.start()
                    limite = time.monotonic() + 120
                    while "error" not in resultado and "ruta" not in resultado and time.monotonic() < limite:
                        app.processEvents()
                        time.sleep(0.01)
                    t.wait()
                    quedan = [x.name for x in (tmp / "descarga").iterdir()]
                    if debe_fallar and ("SHA256" not in resultado.get("error", "") or quedan):
                        fallos.append(f"SHA256 distinto: {resultado}, quedan {quedan}")
                    if not debe_fallar and (resultado.get("sha256") != sha or quedan != [falso.name]):
                        fallos.append(f"descarga: {resultado}")
                if host_permitido("https://example.com/x.exe") or not host_permitido(
                        "https://release-assets.githubusercontent.com/x"):
                    fallos.append("host_permitido")
                propia = {"Estado": "Valid", "Huella": "AA", "Firmante": "CN=Prueba"}
                if evaluar_firma_instalador([{"Estado": "NotSigned"}, propia])[0] != "error" \
                        or evaluar_firma_instalador([propia, propia])[0] != "ok" \
                        or evaluar_firma_instalador([{"Estado": "HashMismatch"}])[0] != "error":
                    fallos.append("evaluar_firma_instalador")
                args = argumentos_instalador(True, Path(r"C:\con espacios\x.log"))
                script = script_ayudante_actualizar(str(falso), sha, args, 1234, "app.exe", "99.0.0", True)
                if '/LOG="C:\\con espacios\\x.log"' not in args or "/SILENT" not in args or any(
                        x not in script for x in ("Wait-Process -Id 1234", "Get-FileHash", sha.upper(), "99.0.0:")):
                    fallos.append("argumentos o ayudante")
                if resultado_de_actualizacion(["x", f"{ARG_ACTUALIZACION}99.0.0:0"]) != ("99.0.0", "0"):
                    fallos.append("resultado_de_actualizacion")
                ventana.tras_actualizar("99.0.0", "1")
                if ventana.aviso_app.tipo != "aviso":
                    fallos.append("aviso de actualización fallida")
                ventana.tras_actualizar(APP_VERSION, "0")
                if ventana.aviso_app.tipo != "ok":
                    fallos.append("aviso de actualización correcta")
            finally:
                if antes is None:
                    os.environ.pop(VARIABLE_RELEASE_PRUEBA, None)
                else:
                    os.environ[VARIABLE_RELEASE_PRUEBA] = antes
                act.cfg.update(copy.deepcopy(DEFAULT_ACTUALIZAR_APP))
                ventana.aviso_app.ocultar()
            registrar("actualizar_app", not fallos, fallos=fallos)
        probar("actualizar_app", actualizar_app)

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
    """Ruta 8.3 de Windows (C:\\Users\\USUARI~1\\...); si no se puede, la original."""
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
    # Antes de abrir fallo_grave.log y la configuración: si no, quedarían abiertos en la carpeta vieja
    mudanza = mover_datos_a_carpeta_nueva()
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
    if mudanza:
        ventana.paginas[0][1].consola.agregar(mudanza[1], mudanza[0])
    autoprueba_activa = "--autoprueba" in sys.argv
    # En la autoprueba no se muestran mensajes (esperarían un clic): solo se registran
    instalar_manejador_de_errores(ventana, mostrar=not autoprueba_activa)
    if autoprueba_activa:
        sys.exit(autoprueba(app, ventana))
    ventana.show()
    if ARG_REABIERTO in sys.argv:
        ventana.tras_reabrir()
    actualizacion = resultado_de_actualizacion(sys.argv)
    if actualizacion:
        ventana.tras_actualizar(*actualizacion)
    ventana.actualizador.al_abrir()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
