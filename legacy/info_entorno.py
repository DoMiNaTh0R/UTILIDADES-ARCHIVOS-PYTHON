import sys
import subprocess
from pathlib import Path
from importlib.metadata import distributions


def main():
    print("=" * 80)
    print("                INFORMACIÓN DEL ENTORNO PYTHON")
    print("=" * 80)

    # --------------------------------------------------
    # Python
    # --------------------------------------------------
    print(f"\nPython:")
    print(f"  Versión : {sys.version}")
    print(f"  Ejecutable: {sys.executable}")

    # --------------------------------------------------
    # Entorno virtual
    # --------------------------------------------------
    venv = Path(sys.prefix)

    print("\nEntorno virtual:")
    print(f"  Ruta    : {venv}")

    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        print("  Estado  : ✅ Virtual Environment detectado")
    else:
        print("  Estado  : ⚠️ No parece ser un venv")

    # --------------------------------------------------
    # Paquetes instalados
    # --------------------------------------------------
    paquetes = []

    for dist in distributions():
        nombre = dist.metadata.get("Name")
        version = dist.version

        if nombre:
            paquetes.append((nombre, version))

    paquetes.sort(key=lambda x: x[0].lower())

    print(f"\nPaquetes instalados: {len(paquetes)}")
    print("-" * 80)

    for nombre, version in paquetes:
        print(f"{nombre:<40} {version}")

    # --------------------------------------------------
    # Guardar requirements.txt
    # --------------------------------------------------
    requirements = venv / "requirements.txt"

    with open(requirements, "w", encoding="utf-8") as f:
        for nombre, version in paquetes:
            f.write(f"{nombre}=={version}\n")

    print("-" * 80)
    print(f"\n✅ requirements.txt creado en:")
    print(f"   {requirements}")

    # --------------------------------------------------
    # pip freeze real
    # --------------------------------------------------
    print("\n" + "=" * 80)
    print("                         PIP FREEZE")
    print("=" * 80)

    try:
        resultado = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True
        )

        print(resultado.stdout)

        freeze_file = venv / "requirements_freeze.txt"

        with open(freeze_file, "w", encoding="utf-8") as f:
            f.write(resultado.stdout)

        print(f"✅ pip freeze guardado en:")
        print(f"   {freeze_file}")

    except subprocess.CalledProcessError as e:
        print("❌ No se pudo ejecutar pip freeze.")
        print(e.stderr)

    print("\n" + "=" * 80)
    print("                           FIN")
    print("=" * 80)


if __name__ == "__main__":
    main()