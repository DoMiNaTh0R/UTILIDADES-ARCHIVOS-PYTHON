# Utilidades de archivos · Copyright (C) 2026  Kevin González (DoMiNaTh0R)
# SPDX-License-Identifier: GPL-3.0-or-later  (ver LICENSE)
"""
Compila Utilidades de archivos con PyInstaller o con Nuitka.

Uso (con el venv del proyecto, build_env; lo crea build_env.bat):
    python compilar.py pyinstaller              carpeta (recomendado: arranca más rápido)
    python compilar.py pyinstaller --onefile    un solo .exe
    python compilar.py nuitka                   carpeta, compilado a código C nativo
    python compilar.py nuitka --onefile         un solo .exe
    python compilar.py todo                     PyInstaller y Nuitka (carpeta)

Opciones:
    --consola       con ventana de consola (para diagnosticar errores)
    --sin-prueba    no ejecuta la autoprueba al terminar

Resultado:
    dist\\pyinstaller\\UtilidadesArchivos\\UtilidadesArchivos.exe   (--onefile: dist\\pyinstaller\\UtilidadesArchivos.exe)
    dist\\nuitka\\UtilidadesArchivos\\UtilidadesArchivos.exe        (--onefile: dist\\nuitka\\UtilidadesArchivos.exe)

La configuración (utilidades_config.json) se crea junto al .exe la primera vez que se abre.
Nuitka necesita un compilador de C: usa Visual Studio Build Tools si está instalado; si no,
descarga uno automáticamente (una sola vez).

Junto al .exe (y dentro de él) van LICENSE (GNU GPL v3) y THIRD_PARTY_NOTICES.txt, que se
genera aquí con el mismo formato que la pestaña «Licencias»: la licencia completa de cada paquete de build_env.

Al terminar ejecuta el .exe con --autoprueba (sin mostrar la ventana): prueba recursos,
complementos de Qt y cada pestaña (incluido el JSON extra de Licencias) y muestra el resultado.
"""
import ast
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
FUENTE = RAIZ / "utilidades_archivos.py"
RECURSOS = RAIZ / "recursos"
ICONO = RECURSOS / "app.ico"
LOGO = RECURSOS / "logo_app.png"
LICENCIA = RAIZ / "LICENSE"
LICENCIA_IMAGENES = RECURSOS / "LICENCIA_LOGO_Y_AVATAR.txt"     # el logo y el avatar no están bajo la GPL
TRABAJO = RAIZ / "build"
AVISOS = TRABAJO / "THIRD_PARTY_NOTICES.txt"
DIST = RAIZ / "dist"

ONEFILE = "--onefile" in sys.argv
CONSOLA = "--consola" in sys.argv

# Módulos que la app no usa (menos tamaño y menos tiempo de análisis)
EXCLUIR = ["tkinter", "numpy", "PIL", "PyQt5", "PySide2", "PySide6"]
# Archivos grandes de Qt que no hacen falta (la interfaz no usa OpenGL)
SOBRANTES = ["opengl32sw.dll"]
# Paquetes de Python que van dentro del .exe (lo demás es la biblioteca estándar de Python)
PAQUETES_INCLUIDOS = ["PyQt6", "PyQt6-Qt6", "PyQt6-sip"]


def datos_app() -> dict:
    """APP_NOMBRE, APP_VERSION... (y el lector y formato de licencias) leídos del código fuente sin importarlo."""
    datos = {}
    for nodo in ast.parse(FUENTE.read_text(encoding="utf-8")).body:
        if isinstance(nodo, ast.Assign) and isinstance(nodo.value, ast.Constant):
            for destino in nodo.targets:
                if isinstance(destino, ast.Name) and (destino.id.startswith("APP_") or destino.id in (
                        "HELPER_ENTORNO", "ENCABEZADO_LICENCIAS", "ANCHO_DOC")):
                    datos[destino.id] = nodo.value.value
    return datos


APP = datos_app()
NOMBRE_EXE = APP["APP_ID"]
# En las propiedades del .exe va solo el nombre real; dentro de la app se ve también DoMiNaTh0R
AUTOR_EXE = APP["APP_AUTOR_NOMBRE"]
COPYRIGHT = f"© {APP['APP_ANIO']} {AUTOR_EXE}. Licencia {APP['APP_LICENCIA']}."


def version_windows() -> tuple[str, ...]:
    return tuple((APP["APP_VERSION"].split(".") + ["0", "0", "0", "0"])[:4])


def _quitar_solo_lectura(funcion, ruta, _error):
    os.chmod(ruta, stat.S_IWRITE)
    funcion(ruta)


def borrar(ruta: Path):
    if ruta.is_dir():
        if sys.version_info >= (3, 12):
            shutil.rmtree(ruta, onexc=_quitar_solo_lectura)
        else:
            shutil.rmtree(ruta, onerror=_quitar_solo_lectura)
    elif ruta.exists():
        os.chmod(ruta, stat.S_IWRITE)
        ruta.unlink()


def preparar_icono():
    """Regenera recursos\\app.ico si cambiaste logo_app.png (hace falta Pillow)."""
    if not LOGO.exists():
        # El logo y el avatar no van en el repositorio: sin ellos se compila igual, sin icono propio
        if not ICONO.exists():
            print("Aviso: no está recursos\\logo_app.png: el .exe se compila sin icono propio ni imágenes.")
        return
    if ICONO.exists() and ICONO.stat().st_mtime >= LOGO.stat().st_mtime:
        return
    try:
        from PIL import Image
    except ImportError:
        if not ICONO.exists():
            sys.exit("Falta recursos\\app.ico y Pillow para crearlo:  ejecuta build_env.bat")
        print("Aviso: logo_app.png es más nuevo que app.ico, pero sin Pillow no se puede regenerar.")
        return
    imagen = Image.open(LOGO).convert("RGBA")
    lado = max(imagen.size)
    lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))     # el .ico tiene que ser cuadrado
    lienzo.paste(imagen, ((lado - imagen.width) // 2, (lado - imagen.height) // 2))
    lienzo.save(ICONO, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f"Icono regenerado desde {LOGO.name}")


def tamano_mb(ruta: Path) -> float:
    if ruta.is_file():
        return ruta.stat().st_size / 1e6
    return sum(f.stat().st_size for f in ruta.rglob("*") if f.is_file()) / 1e6


def escribir_avisos_de_terceros() -> Path:
    """
    THIRD_PARTY_NOTICES.txt: el encabezado de la app y, debajo, el mismo documento que genera la
    pestaña «Licencias» con todos los paquetes del venv de compilación (build_env). Usa el mismo
    lector de licencias que la app, ejecutado con el Python del venv.
    """
    TRABAJO.mkdir(parents=True, exist_ok=True)
    lector, datos = TRABAJO / "leer_licencias.py", TRABAJO / "licencias_venv.json"
    lector.write_text(APP["HELPER_ENTORNO"], encoding="utf-8")
    r = subprocess.run([sys.executable, str(lector), "licencias", str(datos)], capture_output=True, text=True)
    if r.returncode != 0 or not datos.exists():
        sys.exit(f"No se pudieron leer las licencias del venv:\n{r.stderr}")

    def normalizar(nombre: str) -> str:          # PEP 503: PyQt6_sip == pyqt6-sip
        return re.sub(r"[-_.]+", "-", nombre).lower()

    paquetes = json.loads(datos.read_text(encoding="utf-8"))["paquetes"]
    instalados = {normalizar(p["nombre"]) for p in paquetes}
    for nombre in PAQUETES_INCLUIDOS:
        if normalizar(nombre) not in instalados:
            sys.exit(f"Falta {nombre} en el venv: ejecuta build_env.bat")
    filas = sorted(((p["nombre"], p["version"], p["tipo"], p["texto"]) for p in paquetes),
                   key=lambda x: x[0].lower())

    ancho = APP["ANCHO_DOC"]

    def titulo_doc(texto: str) -> str:            # igual que en la pestaña «Licencias»
        return "=" * ancho + "\n" + texto.center(ancho) + "\n" + "=" * ancho

    linea = "=" * 72
    partes = [linea, "AVISOS DE TERCEROS / THIRD-PARTY NOTICES".center(72), linea, "",
              f"{APP['APP_NOMBRE']} {APP['APP_VERSION']} · {COPYRIGHT}",
              f"Código fuente: {APP['APP_REPO']}", "",
              "Este programa incluye los componentes de terceros de abajo, cada uno con su licencia.",
              "Qt se distribuye bajo la LGPL v3: sus bibliotecas van como archivos DLL separados (Qt6*.dll)",
              "que se pueden reemplazar por otra versión compatible; su código fuente está en https://download.qt.io/.",
              "Robocopy, PowerShell y winget son programas de Windows que la app solo ejecuta: no van incluidos.",
              ""]
    # Desde aquí, exactamente el documento de la pestaña «Licencias»
    partes += [titulo_doc("LICENSE INFORMATION DOCUMENT"), ""]
    partes.append(APP["ENCABEZADO_LICENCIAS"].format(app="esta aplicación").strip())
    partes += ["", "", titulo_doc("SUMMARY OF INCLUDED PACKAGES"), ""]
    partes += [f"{nombre}=={version}" for nombre, version, _, _ in filas]
    partes += ["", "", titulo_doc("DETAILED LICENSE TEXTS"), ""]
    for nombre, version, tipo, texto in filas:
        partes += [f"--- {nombre} ({version}) ---", f"License Type: {tipo}", "", texto, "", "-" * ancho, ""]
    with open(AVISOS, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(partes).rstrip() + "\n")
    print(f"Avisos de terceros: {len(filas)} paquetes del venv ({AVISOS.stat().st_size // 1024} KB)")
    return AVISOS


def copiar_documentos_legales(carpeta: Path):
    """LICENSE, THIRD_PARTY_NOTICES.txt y el aviso del logo y avatar junto al .exe, a la vista de quien lo reciba."""
    for archivo in (LICENCIA, AVISOS, LICENCIA_IMAGENES):
        if archivo.exists():
            shutil.copy2(archivo, carpeta / archivo.name)


def quitar_sobrantes(carpeta: Path):
    for nombre in SOBRANTES:
        for archivo in carpeta.rglob(nombre):
            archivo.unlink()
            print(f"  quitado {archivo.relative_to(carpeta)}")


# ─── PyInstaller ────────────────────────────────────────────────────────────

def escribir_version_info() -> Path:
    v = ", ".join(version_windows())
    ruta = TRABAJO / "version_info.txt"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}), prodvers=({v}), mask=0x3f, flags=0x0, OS=0x4, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040a04B0', [
        StringStruct('CompanyName', '{AUTOR_EXE}'),
        StringStruct('FileDescription', '{APP['APP_NOMBRE']}'),
        StringStruct('FileVersion', '{APP['APP_VERSION']}'),
        StringStruct('InternalName', '{NOMBRE_EXE}'),
        StringStruct('LegalCopyright', '{COPYRIGHT}'),
        StringStruct('OriginalFilename', '{NOMBRE_EXE}.exe'),
        StringStruct('ProductName', '{APP['APP_NOMBRE']}'),
        StringStruct('ProductVersion', '{APP['APP_VERSION']}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1034, 1200])])
  ]
)
""", encoding="utf-8")
    return ruta


def compilar_pyinstaller() -> Path:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        sys.exit("PyInstaller no está instalado:  ejecuta build_env.bat")
    destino = DIST / "pyinstaller"
    exe = destino / f"{NOMBRE_EXE}.exe" if ONEFILE else destino / NOMBRE_EXE / f"{NOMBRE_EXE}.exe"
    borrar(exe if ONEFILE else exe.parent)
    cmd = [sys.executable, "-m", "PyInstaller", str(FUENTE),
           "--name", NOMBRE_EXE, "--noconfirm", "--clean",
           "--distpath", str(destino),
           "--workpath", str(TRABAJO / "pyinstaller"), "--specpath", str(TRABAJO / "pyinstaller"),
           "--version-file", str(escribir_version_info()),
           "--add-data", f"{LICENCIA}{os.pathsep}.",
           "--add-data", f"{AVISOS}{os.pathsep}.",
           "--onefile" if ONEFILE else "--onedir",
           "--console" if CONSOLA else "--windowed"]
    if ICONO.exists():
        cmd += ["--icon", str(ICONO)]
    if RECURSOS.is_dir():
        cmd += ["--add-data", f"{RECURSOS}{os.pathsep}recursos"]
    for modulo in EXCLUIR:
        cmd += ["--exclude-module", modulo]
    print(f"\n=== PyInstaller ({'un solo .exe' if ONEFILE else 'carpeta'}) ===")
    if subprocess.run(cmd, cwd=RAIZ).returncode != 0:
        sys.exit("PyInstaller falló.")
    if not ONEFILE:
        quitar_sobrantes(exe.parent)
    copiar_documentos_legales(exe.parent)
    print(f"Listo: {exe}  ({tamano_mb(exe if ONEFILE else exe.parent):.0f} MB)")
    return exe


# ─── Nuitka ─────────────────────────────────────────────────────────────────

def traduccion_qt() -> Path | None:
    """qtbase_es.qm: los menús propios de Qt (Copiar, Pegar…) en español."""
    import importlib.util
    spec = importlib.util.find_spec("PyQt6")
    if spec is None or not spec.submodule_search_locations:
        return None
    ruta = Path(list(spec.submodule_search_locations)[0]) / "Qt6" / "translations" / "qtbase_es.qm"
    return ruta if ruta.is_file() else None


def compilar_nuitka() -> Path:
    try:
        import nuitka  # noqa: F401
    except ImportError:
        sys.exit("Nuitka no está instalado:  ejecuta build_env.bat")
    salida = TRABAJO / "nuitka"
    destino = DIST / "nuitka"
    version = ".".join(version_windows())
    cmd = [sys.executable, "-m", "nuitka", str(FUENTE),
           "--onefile" if ONEFILE else "--standalone",
           "--enable-plugin=pyqt6",
           f"--windows-console-mode={'force' if CONSOLA else 'disable'}",
           f"--include-data-files={LICENCIA}=LICENSE",
           f"--include-data-files={AVISOS}=THIRD_PARTY_NOTICES.txt",
           f"--output-dir={salida}",
           f"--output-filename={NOMBRE_EXE}.exe",
           f"--company-name={AUTOR_EXE}",
           f"--product-name={APP['APP_NOMBRE']}",
           f"--file-description={APP['APP_NOMBRE']}",
           f"--copyright={COPYRIGHT}",
           f"--file-version={version}", f"--product-version={version}",
           "--assume-yes-for-downloads", "--remove-output"]
    if ICONO.exists():
        cmd.append(f"--windows-icon-from-ico={ICONO}")
    if RECURSOS.is_dir():
        cmd.append(f"--include-data-dir={RECURSOS}=recursos")
    traduccion = traduccion_qt()
    if traduccion is not None:      # Nuitka no incluye las traducciones de Qt (PyInstaller sí)
        cmd.append(f"--include-data-files={traduccion}=traducciones/{traduccion.name}")
    if ONEFILE:
        # Carpeta fija de extracción: a partir del segundo arranque abre al instante
        # (%LOCALAPPDATA%\UtilidadesArchivos\onefile_<versión>, junto a la configuración y los registros)
        cmd.append(f"--onefile-tempdir-spec={{CACHE_DIR}}/{NOMBRE_EXE}/onefile_{APP['APP_VERSION']}")
    for modulo in EXCLUIR:
        cmd.append(f"--nofollow-import-to={modulo}")
    print(f"\n=== Nuitka ({'un solo .exe' if ONEFILE else 'carpeta'}) — puede tardar varios minutos ===")
    if subprocess.run(cmd, cwd=RAIZ).returncode != 0:
        sys.exit("Nuitka falló.")

    destino.mkdir(parents=True, exist_ok=True)
    if ONEFILE:
        exe = destino / f"{NOMBRE_EXE}.exe"
        borrar(exe)
        shutil.move(str(salida / f"{NOMBRE_EXE}.exe"), str(exe))
    else:
        carpeta = destino / NOMBRE_EXE
        borrar(carpeta)
        shutil.move(str(salida / f"{FUENTE.stem}.dist"), str(carpeta))
        quitar_sobrantes(carpeta)
        exe = carpeta / f"{NOMBRE_EXE}.exe"
    copiar_documentos_legales(exe.parent)
    print(f"Listo: {exe}  ({tamano_mb(exe if ONEFILE else exe.parent):.0f} MB)")
    return exe


# ─── Autoprueba ─────────────────────────────────────────────────────────────

def autoprueba(exe: Path, intento: int = 1) -> bool:
    print(f"\nAutoprueba de {exe.name} (sin ventana, con configuración temporal)...")
    datos = Path(tempfile.mkdtemp(prefix="utilidades_autoprueba_"))
    try:
        codigo = subprocess.run([str(exe), "--autoprueba"], env=dict(os.environ, UTILIDADES_DATOS=str(datos)),
                                timeout=600).returncode
        informe = datos / "autoprueba.json"
        if not informe.exists():
            print(f"Autoprueba: FALLÓ, el .exe no dejó informe (código {codigo}).")
            return False
        d = json.loads(informe.read_text(encoding="utf-8"))
        for nombre, r in d["pruebas"].items():
            extra = {k: v for k, v in r.items() if k != "ok"}
            print(f"  {'OK   ' if r['ok'] else 'FALLO'} {nombre}  {json.dumps(extra, ensure_ascii=False)}")
        print(f"Autoprueba: {d['resultado']} ({d['ejecucion']}, Python {d['python']}, Qt {d['qt']})")
        fallos = [n for n, r in d["pruebas"].items() if not r["ok"]]
        if fallos == ["interfaz_sin_congelarse"] and intento == 1:
            # Un .exe recién compilado y sin firma lo revisa el antivirus la primera vez que lanza
            # procesos (Avast llega a pausar todo el programa unos segundos): se repite una vez.
            print("Solo falló la medición de congelamiento: suele ser el antivirus revisando un .exe nuevo. "
                  "Se repite la autoprueba...")
            return autoprueba(exe, intento=2)
        return codigo == 0
    except subprocess.TimeoutExpired:
        print("Autoprueba: el .exe no terminó a tiempo.")
        return False
    finally:
        shutil.rmtree(datos, ignore_errors=True)


def main():
    herramienta = next((a for a in sys.argv[1:] if not a.startswith("--")), "").lower()
    compiladores = {"pyinstaller": [compilar_pyinstaller], "nuitka": [compilar_nuitka],
                    "todo": [compilar_pyinstaller, compilar_nuitka]}
    if herramienta not in compiladores:
        print(__doc__)
        sys.exit(2)
    print(f"{APP['APP_NOMBRE']} {APP['APP_VERSION']}")
    if not LICENCIA.exists():
        sys.exit("Falta el archivo LICENSE en la raíz del proyecto.")
    preparar_icono()
    escribir_avisos_de_terceros()
    todo_ok = True
    for compilar in compiladores[herramienta]:
        exe = compilar()
        if "--sin-prueba" not in sys.argv:
            todo_ok = autoprueba(exe) and todo_ok
    sys.exit(0 if todo_ok else 1)


if __name__ == "__main__":
    main()
