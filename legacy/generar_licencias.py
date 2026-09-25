"""
generar_licencias.py — Genera un THIRD_PARTY_NOTICES.txt a partir de un entorno
virtual: recorre TODOS los paquetes instalados, saca su licencia completa, los
ordena alfabéticamente y arma el documento con su encabezado.

Sirve para cualquier app: lo específico de cada una (texto de cabecera y
componentes que no son paquetes de Python, como FFmpeg o Ghostscript) se pone
en un JSON aparte y se pasa con --extra.

USO (con el venv de la app activado, o llamando a su python):

    build_env_DMT\\Scripts\\python.exe generar_licencias.py ^
        --salida imgtype\\THIRD_PARTY_NOTICES.txt ^
        --app "DEUS MACHINA | TOOLS" ^
        --extra licencias_extra.json

Opciones:
    --salida RUTA      Archivo a escribir (por defecto THIRD_PARTY_NOTICES.txt)
    --app NOMBRE       Nombre de la aplicación para el encabezado
    --extra RUTA.json  Componentes externos + encabezado propio (ver abajo)
    --excluir a,b,c    Paquetes a omitir (por ejemplo pip,setuptools)
    --solo-requeridos  Solo los paquetes listados en un requirements.txt
    --requirements RUTA  El requirements.txt a usar con --solo-requeridos
    --listar           No escribe nada: solo enseña qué encontró

FORMATO DEL JSON de --extra (todo es opcional):

{
  "encabezado": "Texto libre que va debajo del título del documento.",
  "componentes": [
    {
      "nombre": "FFmpeg",
      "version": "9.0.1",
      "tipo": "GNU GPL v3",
      "url": "https://ffmpeg.org/download.html",
      "nota": "Se ejecuta como proceso externo (CLI).",
      "archivo": "tools/ffmpeg/LICENSE"      <- o "texto": "..."
    }
  ]
}
"""

import argparse
import json
import os
import re
import sys
from importlib import metadata

ANCHO = 60
SEPARADOR = "-" * ANCHO

# Nombres de archivo que suelen contener la licencia dentro de un .dist-info
PATRON_LICENCIA = re.compile(
    r"(^|/)(licen[cs]e|licence|copying|notice|authors|copyright)[^/]*$", re.I)

# Solo se leen archivos de TEXTO: hay paquetes con módulos llamados 'authors.py'
# o 'license.py' que no son licencias (y pueden traer datos personales).
EXT_TEXTO = {"", ".txt", ".md", ".rst", ".text", ".apache", ".bsd", ".mit", ".gpl"}


def parece_texto(contenido):
    """Descarta binarios y código fuente disfrazado de archivo de licencia."""
    if not contenido or "\x00" in contenido[:2000]:
        return False
    muestra = contenido[:2000]
    raros = sum(1 for c in muestra if not c.isprintable() and c not in "\n\r\t")
    if raros > len(muestra) * 0.02:
        return False
    # Señales de que es código, no una licencia
    pistas = ("import ", "def ", "class ", "@dataclass", "#!/usr/bin/env")
    if sum(1 for p in pistas if p in muestra) >= 2:
        return False
    return True

ENCABEZADO_POR_DEFECTO = (
    "Este documento contiene los textos completos y sin modificar de las licencias\n"
    "de todas las librerías externas que usa {app}.\n"
    "Las licencias se reproducen tal cual para cumplir con los requisitos legales\n"
    "de redistribución.\n\n"
    "Este archivo se entrega únicamente con fines informativos y de cumplimiento legal.\n"
)


def titulo(texto):
    """Bloque de título centrado entre líneas de '=' (como en el documento original)."""
    return "=" * ANCHO + "\n" + texto.center(ANCHO) + "\n" + "=" * ANCHO


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
    """Tipo de licencia declarado: License-Expression, clasificadores o campo License."""
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
    """
    Texto completo de la licencia: primero los archivos LICENSE/COPYING/NOTICE
    que el paquete trae en su .dist-info; si no hay ninguno, el campo License.
    """
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
            # read_text() resuelve relativo al .dist-info, así que no sirve para
            # rutas como 'paquete.dist-info/licenses/LICENSE' (el formato nuevo)
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
            print(f"[aviso] {dist.metadata.get('Name')}: '{nombre}' no parece una licencia; se omite",
                  file=sys.stderr)
            contenido = ""
        if contenido:
            etiqueta = f"[{nombre}]\n" if len(vistos) > 1 else ""
            partes.append(etiqueta + contenido)
    if partes:
        return "\n\n".join(partes)

    lic = (dist.metadata.get("License") or "").strip()
    if lic and ("\n" in lic or len(lic) > 80):
        return lic            # algunos paquetes meten la licencia entera en el campo
    if lic:
        return (f"Licencia declarada: {lic}\n"
                "El paquete no incluye el texto completo en su distribución.")
    return ("El paquete no declara licencia ni incluye su texto en la distribución.\n"
            "Consulta el proyecto original para conocer sus términos.")


def paquetes_instalados(excluir):
    """(nombre, versión, tipo, texto) de cada paquete del entorno, sin repetidos."""
    salida = {}
    for dist in metadata.distributions():
        try:
            md = dist.metadata
            nombre = (md.get("Name") or "").strip()
            if not nombre or nombre.lower() in excluir:
                continue
            clave = nombre.lower()
            if clave in salida:
                continue
            salida[clave] = (nombre, dist.version or "?",
                             tipo_de_licencia(md), texto_de_licencia(dist))
        except Exception as e:
            print(f"[aviso] No se pudo leer un paquete: {e}", file=sys.stderr)
    return list(salida.values())


def componentes_extra(config, base):
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
            texto = leer(ruta)
            if not texto:
                print(f"[aviso] No se pudo leer la licencia de {nombre}: {ruta}", file=sys.stderr)
        encabezado = []
        if comp.get("url"):
            encabezado.append(f"Proyecto: {comp['url']}")
        if comp.get("nota"):
            encabezado.append(comp["nota"])
        cuerpo = "\n".join(encabezado + ([""] if encabezado else []) + [texto or "(sin texto)"])
        salida.append((nombre, comp.get("version", "?"),
                       comp.get("tipo", "Ver texto de la licencia"), cuerpo.strip()))
    return salida


def completar_faltantes(paquetes, config, base):
    """
    Rellena a mano los paquetes que no traen su licencia dentro del wheel,
    usando la sección "faltantes" del JSON: {"nombre": {"tipo": ..., "texto": ...}}.
    """
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
                nuevo = leer(ruta)
            if nuevo:
                texto = nuevo
                tipo = datos.get("tipo", tipo)
        salida.append((nombre, version, tipo, texto))
    return salida


def nombres_de_requirements(ruta):
    nombres = set()
    for linea in (leer(ruta) or "").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea or linea.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9._-]+)", linea)
        if m:
            nombres.add(m.group(1).lower().replace("_", "-"))
    return nombres


def main():
    p = argparse.ArgumentParser(description="Genera el documento de licencias de terceros.")
    p.add_argument("--salida", default="THIRD_PARTY_NOTICES.txt")
    p.add_argument("--app", default="esta aplicación")
    p.add_argument("--extra", default=None)
    p.add_argument("--excluir", default="")
    p.add_argument("--solo-requeridos", action="store_true")
    p.add_argument("--requirements", default="requirements.txt")
    p.add_argument("--listar", action="store_true")
    args = p.parse_args()

    base = os.path.dirname(os.path.abspath(args.extra)) if args.extra else os.getcwd()
    config = {}
    if args.extra:
        try:
            with open(args.extra, "r", encoding="utf-8") as fh:
                config = json.load(fh)
        except Exception as e:
            print(f"[error] No se pudo leer {args.extra}: {e}", file=sys.stderr)
            return 2

    excluir = {x.strip().lower() for x in args.excluir.split(",") if x.strip()}
    paquetes = paquetes_instalados(excluir)

    if args.solo_requeridos:
        pedidos = nombres_de_requirements(args.requirements)
        if pedidos:
            paquetes = [x for x in paquetes
                        if x[0].lower().replace("_", "-") in pedidos]

    paquetes = completar_faltantes(paquetes, config, base)
    filas = sorted(paquetes + componentes_extra(config, base), key=lambda x: x[0].lower())
    if not filas:
        print("[error] No se encontró ningún paquete. ¿Estás usando el python del venv?",
              file=sys.stderr)
        return 1

    if args.listar:
        for nombre, version, tipo, _ in filas:
            print(f"{nombre}=={version}   [{tipo}]")
        print(f"\nTotal: {len(filas)} componentes.")
        return 0

    partes = [titulo("LICENSE INFORMATION DOCUMENT"), ""]
    partes.append((config.get("encabezado")
                   or ENCABEZADO_POR_DEFECTO.format(app=args.app)).strip())
    partes += ["", "", titulo("SUMMARY OF INCLUDED PACKAGES"), ""]
    partes += [f"{nombre}=={version}" for nombre, version, _, _ in filas]
    partes += ["", "", titulo("DETAILED LICENSE TEXTS"), ""]
    for nombre, version, tipo, texto in filas:
        partes.append(f"--- {nombre} ({version}) ---")
        partes.append(f"License Type: {tipo}")
        partes.append("")
        partes.append(texto)
        partes.append("")
        partes.append(SEPARADOR)
        partes.append("")

    contenido = "\n".join(partes).rstrip() + "\n"
    carpeta = os.path.dirname(os.path.abspath(args.salida))
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(args.salida, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(contenido)

    sin_texto = [n for n, _, _, t in filas if t.startswith("El paquete no declara")]
    print(f"✅ {args.salida}: {len(filas)} componentes, {len(contenido) / 1024:.0f} KB.")
    if sin_texto:
        print(f"⚠️  Sin texto de licencia ({len(sin_texto)}): {', '.join(sin_texto)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
