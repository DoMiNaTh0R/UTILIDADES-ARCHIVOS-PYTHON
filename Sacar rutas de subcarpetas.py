from pathlib import Path
import os

RUTA_ANALIZAR = Path.cwd()
NOMBRE_TXT = "lista_archivos.txt"
EXTENSIONES_PREDETERMINADAS = (".bat", ".lnk", ".exe", ".msi", ".pdf")


def normalizar_extensiones(texto):
    extensiones = []
    vistos = set()

    for parte in texto.split(","):
        ext = parte.strip().lower()
        if not ext:
            continue

        if not ext.startswith("."):
            ext = "." + ext

        if ext == ".":
            continue

        if ext not in vistos:
            extensiones.append(ext)
            vistos.add(ext)

    if not extensiones:
        raise ValueError("No se ingresaron extensiones válidas.")

    return tuple(extensiones)


def combinar_extensiones(*grupos):
    resultado = []
    vistos = set()

    for grupo in grupos:
        for ext in grupo:
            ext = ext.strip().lower()
            if not ext.startswith("."):
                ext = "." + ext
            if ext not in vistos:
                resultado.append(ext)
                vistos.add(ext)

    return tuple(resultado)


def barra_progreso(actual, total, prefijo="", ancho=30):
    if total <= 0:
        total = 1

    porcentaje = actual / total
    llenado = int(ancho * porcentaje)
    barra = "█" * llenado + "-" * (ancho - llenado)

    print(f"\r{prefijo} |{barra}| {actual}/{total}", end="", flush=True)


def elegir_modo_guardado():
    while True:
        print("\n¿Qué deseas guardar?")
        print("1) Solo archivos")
        print("2) Solo carpetas")
        print("3) Archivos y carpetas")

        opcion = input("Elige una opción: ").strip()

        if opcion in ("1", "2", "3"):
            return opcion

        print("Opción inválida. Intenta de nuevo.")


def elegir_filtro_de_archivos():
    while True:
        print("\nFiltro de archivos:")
        print("1) Sin filtro")
        print("2) Filtro predeterminado")
        print("3) Predeterminado + extras")
        print("4) Personalizado")

        opcion = input("Elige una opción: ").strip()

        try:
            if opcion == "1":
                return None

            elif opcion == "2":
                return EXTENSIONES_PREDETERMINADAS

            elif opcion == "3":
                extras = input("Extensiones extra separadas por coma (ej: mp4,mkv,zip): ").strip()
                if not extras:
                    return EXTENSIONES_PREDETERMINADAS

                extras_norm = normalizar_extensiones(extras)
                return combinar_extensiones(EXTENSIONES_PREDETERMINADAS, extras_norm)

            elif opcion == "4":
                custom = input("Escribe tus extensiones separadas por coma (ej: mp4,jpg,png): ").strip()
                return normalizar_extensiones(custom)

            else:
                print("Opción inválida. Intenta otra vez.")

        except ValueError as e:
            print(f"Error: {e}")


def recolectar_elementos(base, modo):
    elementos = []

    def error_walk(err):
        print(f"\n[AVISO] No se pudo acceder a una carpeta: {err}")

    for raiz, carpetas, archivos in os.walk(base, onerror=error_walk):
        raiz_path = Path(raiz)

        if modo in ("2", "3"):
            for carpeta in sorted(carpetas):
                elementos.append((raiz_path / carpeta, True))

        if modo in ("1", "3"):
            for archivo in sorted(archivos):
                elementos.append((raiz_path / archivo, False))

    return elementos


def filtrar_elementos(elementos, extensiones):
    if extensiones is None:
        return elementos

    filtrados = []
    for ruta, es_carpeta in elementos:
        if es_carpeta:
            filtrados.append((ruta, True))
        else:
            if ruta.suffix.lower() in extensiones:
                filtrados.append((ruta, False))

    return filtrados


def generar_y_guardar(ruta_a_analizar, modo, extensiones):
    base = Path(ruta_a_analizar)

    if not base.exists():
        raise FileNotFoundError(f"No existe la ruta a analizar: {base}")

    if not base.is_dir():
        raise NotADirectoryError(f"La ruta no es una carpeta: {base}")

    salida = Path(__file__).resolve().parent / NOMBRE_TXT

    print("\nReuniendo elementos...")
    elementos = recolectar_elementos(base, modo)

    if not elementos:
        raise FileNotFoundError("No se encontraron elementos en la ruta indicada.")

    print(f"Total encontrados: {len(elementos)}")

    elementos_filtrados = filtrar_elementos(elementos, extensiones)

    if modo == "2":
        print("Seleccionaste solo carpetas.")
    elif modo == "1":
        if extensiones is None:
            print("No se aplicó filtro. Se conservaron todos los archivos.")
        else:
            print("Filtro aplicado a los archivos.")
    elif modo == "3":
        if extensiones is None:
            print("No se aplicó filtro. Se conservaron archivos y carpetas.")
        else:
            print("Filtro aplicado a los archivos. Las carpetas se conservaron.")

    temp = salida.with_name(salida.stem + "_tmp" + salida.suffix)

    with open(temp, "w", encoding="utf-8") as f:
        total = len(elementos_filtrados)

        for i, (ruta, _es_carpeta) in enumerate(elementos_filtrados, 1):
            f.write(str(ruta.resolve()) + "\n")
            barra_progreso(i, total, "Guardando")

    print()

    try:
        os.replace(temp, salida)
    except OSError as e:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass
        raise OSError(f"No se pudo reemplazar el archivo final: {e}")

    return salida, len(elementos), len(elementos_filtrados)


def main():
    print("Iniciando proceso...")

    modo = elegir_modo_guardado()

    extensiones = None
    if modo in ("1", "3"):
        print("\nAhora elige el filtro para los archivos:")
        extensiones = elegir_filtro_de_archivos()

    ruta_txt, total, guardados = generar_y_guardar(RUTA_ANALIZAR, modo, extensiones)

    print("\nProceso terminado correctamente.")
    print(f"Archivo generado en: {ruta_txt}")
    print(f"Elementos encontrados: {total}")
    print(f"Elementos guardados: {guardados}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProceso cancelado por el usuario.")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
    finally:
        try:
            input("\nPresiona ENTER para salir...")
        except EOFError:
            pass