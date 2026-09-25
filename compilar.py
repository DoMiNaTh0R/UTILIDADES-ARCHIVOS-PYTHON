"""
Compila Utilidades de archivos con PyInstaller o con Nuitka.

Uso (con el venv del proyecto; lo crea crear_venv.bat):
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

Al terminar ejecuta el .exe con --autoprueba (sin mostrar la ventana): prueba recursos,
complementos de Qt y cada pestaña (incluido el JSON extra de Licencias) y muestra el resultado.
"""
import ast
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
FUENTE = RAIZ / "utilidades_archivos" / "utilidades_archivos.py"
RECURSOS = FUENTE.parent / "recursos"
ICONO = RECURSOS / "app.ico"
LOGO = RECURSOS / "logo_app.png"
TRABAJO = RAIZ / "build"
DIST = RAIZ / "dist"

ONEFILE = "--onefile" in sys.argv
CONSOLA = "--consola" in sys.argv

# Módulos que la app no usa (menos tamaño y menos tiempo de análisis)
EXCLUIR = ["tkinter", "numpy", "PIL", "PyQt5", "PySide2", "PySide6"]
# Archivos grandes de Qt que no hacen falta (la interfaz no usa OpenGL)
SOBRANTES = ["opengl32sw.dll"]


def datos_app() -> dict:
    """APP_NOMBRE, APP_VERSION... leídos del código fuente sin importarlo (no hace falta PyQt6)."""
    datos = {}
    for nodo in ast.parse(FUENTE.read_text(encoding="utf-8")).body:
        if isinstance(nodo, ast.Assign) and isinstance(nodo.value, ast.Constant):
            for destino in nodo.targets:
                if isinstance(destino, ast.Name) and destino.id.startswith("APP_"):
                    datos[destino.id] = nodo.value.value
    return datos


APP = datos_app()
NOMBRE_EXE = APP["APP_ID"]
COPYRIGHT = f"© {APP['APP_ANIO']} {APP['APP_AUTOR_NOMBRE']} ({APP['APP_AUTOR']})"


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
    if ICONO.exists() and ICONO.stat().st_mtime >= LOGO.stat().st_mtime:
        return
    try:
        from PIL import Image
    except ImportError:
        if not ICONO.exists():
            sys.exit("Falta recursos\\app.ico y Pillow para crearlo:  pip install -r requirements-dev.txt")
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
        StringStruct('CompanyName', '{APP['APP_AUTOR_NOMBRE']} ({APP['APP_AUTOR']})'),
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
        sys.exit("PyInstaller no está instalado:  pip install -r requirements-dev.txt")
    destino = DIST / "pyinstaller"
    exe = destino / f"{NOMBRE_EXE}.exe" if ONEFILE else destino / NOMBRE_EXE / f"{NOMBRE_EXE}.exe"
    borrar(exe if ONEFILE else exe.parent)
    cmd = [sys.executable, "-m", "PyInstaller", str(FUENTE),
           "--name", NOMBRE_EXE, "--noconfirm", "--clean",
           "--distpath", str(destino),
           "--workpath", str(TRABAJO / "pyinstaller"), "--specpath", str(TRABAJO / "pyinstaller"),
           "--icon", str(ICONO),
           "--version-file", str(escribir_version_info()),
           "--add-data", f"{RECURSOS}{os.pathsep}recursos",
           "--onefile" if ONEFILE else "--onedir",
           "--console" if CONSOLA else "--windowed"]
    for modulo in EXCLUIR:
        cmd += ["--exclude-module", modulo]
    print(f"\n=== PyInstaller ({'un solo .exe' if ONEFILE else 'carpeta'}) ===")
    if subprocess.run(cmd, cwd=RAIZ).returncode != 0:
        sys.exit("PyInstaller falló.")
    if not ONEFILE:
        quitar_sobrantes(exe.parent)
    print(f"Listo: {exe}  ({tamano_mb(exe if ONEFILE else exe.parent):.0f} MB)")
    return exe


# ─── Nuitka ─────────────────────────────────────────────────────────────────

def compilar_nuitka() -> Path:
    try:
        import nuitka  # noqa: F401
    except ImportError:
        sys.exit("Nuitka no está instalado:  pip install -r requirements-dev.txt")
    salida = TRABAJO / "nuitka"
    destino = DIST / "nuitka"
    version = ".".join(version_windows())
    cmd = [sys.executable, "-m", "nuitka", str(FUENTE),
           "--onefile" if ONEFILE else "--standalone",
           "--enable-plugin=pyqt6",
           f"--windows-console-mode={'force' if CONSOLA else 'disable'}",
           f"--windows-icon-from-ico={ICONO}",
           f"--include-data-dir={RECURSOS}=recursos",
           f"--output-dir={salida}",
           f"--output-filename={NOMBRE_EXE}.exe",
           f"--company-name={APP['APP_AUTOR_NOMBRE']} ({APP['APP_AUTOR']})",
           f"--product-name={APP['APP_NOMBRE']}",
           f"--file-description={APP['APP_NOMBRE']}",
           f"--copyright={COPYRIGHT}",
           f"--file-version={version}", f"--product-version={version}",
           "--assume-yes-for-downloads", "--remove-output"]
    if ONEFILE:
        # Carpeta fija de extracción: a partir del segundo arranque abre al instante
        # (subcarpeta propia: %LOCALAPPDATA%\UtilidadesArchivos también puede guardar la configuración)
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
    print(f"Listo: {exe}  ({tamano_mb(exe if ONEFILE else exe.parent):.0f} MB)")
    return exe


# ─── Autoprueba ─────────────────────────────────────────────────────────────

def autoprueba(exe: Path) -> bool:
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
    preparar_icono()
    todo_ok = True
    for compilar in compiladores[herramienta]:
        exe = compilar()
        if "--sin-prueba" not in sys.argv:
            todo_ok = autoprueba(exe) and todo_ok
    sys.exit(0 if todo_ok else 1)


if __name__ == "__main__":
    main()
