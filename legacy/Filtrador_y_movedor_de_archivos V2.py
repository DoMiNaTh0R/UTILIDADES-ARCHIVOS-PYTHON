import os
import shutil
from collections import Counter
from pathlib import Path

# ── Configuración ──────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent

CARPETA_ORIGEN         = SCRIPT_DIR                       # 📂 carpeta a escanear (con subcarpetas). Cámbiala si quieres, ej: Path(r"C:\Users\Kevin\Downloads")
TXT_EXTENSIONES        = SCRIPT_DIR / "extensiones.txt"   # txt con la lista simple de extensiones encontradas
NOMBRE_CARPETA_DESTINO = "Organizado"                      # se crea junto al script
DESTINO_BASE           = SCRIPT_DIR / NOMBRE_CARPETA_DESTINO
MODO                   = "mover"                           # "mover" o "copiar"
# ───────────────────────────────────────────────────────────


def normaliza(linea: str) -> str:
    """Convierte una línea del txt de extensiones al formato de Path.suffix ('.jpg', '', etc.)."""
    e = linea.strip().lower()
    if e in ("", "(sin extensión)", "sin", "sin extension"):
        return ""
    return e if e.startswith(".") else f".{e}"


# 1. Recorrer la carpeta origen y TODAS sus subcarpetas
print(f"Escaneando '{CARPETA_ORIGEN}' y subcarpetas...\n")

script_path = Path(__file__).resolve()
destino_resuelto = DESTINO_BASE.resolve()

archivos = []
for p in CARPETA_ORIGEN.rglob("*"):
    if not p.is_file():
        continue
    rp = p.resolve()
    if rp == script_path or rp == TXT_EXTENSIONES.resolve():
        continue                            # no contarse a sí mismo ni al txt generado
    if destino_resuelto in rp.parents:
        continue                            # ya organizado en una corrida anterior
    archivos.append(p)

# 2. Contar cuántos archivos hay de cada extensión
conteo = Counter()
for archivo in archivos:
    ext = archivo.suffix.lower() or "(sin extensión)"
    conteo[ext] += 1

# 3. Mostrar resumen en pantalla
print(f"{'EXTENSIÓN':<20} {'CANTIDAD':>8}")
print("─" * 30)
for ext, n in sorted(conteo.items(), key=lambda x: -x[1]):
    print(f"{ext:<20} {n:>8}")
print(f"\nTotal: {sum(conteo.values())} archivos  |  {len(conteo)} extensiones distintas\n")

# 4. Guardar un txt con las extensiones así solas (una por línea, sin cantidades)
extensiones_ordenadas = sorted(conteo.keys())
with open(TXT_EXTENSIONES, "w", encoding="utf-8") as f:
    f.write("\n".join(extensiones_ordenadas))

print(f"✓ '{TXT_EXTENSIONES.name}' generado junto al script con la lista de extensiones.\n")

# 5. Preguntar si se quiere el paso 2
resp = input("¿Quieres continuar con el paso 2 y mover archivos según extensiones? [s/n]: ").strip().lower()

if resp in ("s", "si", "sí"):
    print(f"\nSe abrirá '{TXT_EXTENSIONES.name}' en el bloc de notas.")
    print("Deja solo las extensiones que SÍ quieres mover (borra las demás) y guarda el archivo.")
    try:
        os.startfile(TXT_EXTENSIONES)
    except Exception:
        print(f"(No se pudo abrir automáticamente, ábrelo tú desde: {TXT_EXTENSIONES})")
    input("Cuando termines de editar y guardar, presiona Enter para continuar...\n")

    # Releer el txt YA editado por el usuario
    with open(TXT_EXTENSIONES, encoding="utf-8", errors="ignore") as f:
        seleccionadas = {normaliza(linea) for linea in f if linea.strip()}

    if not seleccionadas:
        print("No quedó ninguna extensión en el txt, no se movió nada.")
    else:
        a_mover = [a for a in archivos if a.suffix.lower() in seleccionadas]

        DESTINO_BASE.mkdir(parents=True, exist_ok=True)
        mover = MODO.strip().lower() == "mover"
        label = "Moviendo" if mover else "Copiando"
        ok = errores = 0

        print(f"\n{label} {len(a_mover)} archivos a '{DESTINO_BASE}'...\n")

        for origen in a_mover:
            carpeta_nombre = origen.suffix.lower().lstrip(".") or "sin_extension"
            carpeta_destino = DESTINO_BASE / carpeta_nombre
            carpeta_destino.mkdir(parents=True, exist_ok=True)

            destino_archivo = carpeta_destino / origen.name

            # Evitar sobreescritura: añade _1, _2, etc.
            if destino_archivo.exists():
                n = 1
                while destino_archivo.exists():
                    destino_archivo = carpeta_destino / f"{origen.stem}_{n}{origen.suffix}"
                    n += 1

            try:
                if mover:
                    shutil.move(str(origen), str(destino_archivo))
                else:
                    shutil.copy2(str(origen), str(destino_archivo))
                ok += 1
            except Exception as e:
                print(f"  ✗ {origen.name}  →  {e}")
                errores += 1

        print(f"\n✓ {'Movidos' if mover else 'Copiados'}: {ok} archivos")
        if errores:
            print(f"  ✗ Con errores: {errores}")
        print(f"  → Destino: {DESTINO_BASE}")
else:
    print(f"\nOk. '{TXT_EXTENSIONES.name}' quedó guardado junto al script por si quieres revisarlo o usarlo después.")

input("\nPresiona Enter para cerrar...")
