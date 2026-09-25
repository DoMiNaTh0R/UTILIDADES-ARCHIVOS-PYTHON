# Utilidades de archivos

<img src="utilidades_archivos/recursos/logo_app.png" width="96" align="right" alt="Logo">

App de escritorio para Windows (PyQt6) que junta en una sola ventana varias utilidades que antes eran scripts sueltos.

**Versión 1.0.0** · Creada por **DoMiNaTh0R** (Kevin González) · © 2026

## Pestañas

| Pestaña | Qué hace | Script original |
|---|---|---|
| **Copiar** | Robocopy con carpetas (`/XD`) y archivos (`/XF`) a omitir, reintentos, simulación (`/L`) y salida en vivo. Copia la carpeta completa (como Ctrl+C / Ctrl+V) o solo su contenido. Muestra %, velocidad y tiempo restante. Multihilo (`/MT`) automático según el disco: USB 4 hilos, HDD 8, SSD según tu CPU. Sesiones con nombre. | `copiar.bat` |
| **Organizar** | Escanea una carpeta (recursivo), cuenta archivos por extensión y mueve o copia las marcadas a `<destino>/<extensión>/`. Nunca sobrescribe (añade `_1`, `_2`…). | `Filtrador_y_movedor_de_archivos V2.py` |
| **Listar rutas** | `.txt` con las rutas de archivos y/o carpetas (recursivo). Filtro *Todo / Solo estas / Excluir estas* extensiones y carpetas a ignorar. Sesiones con nombre. | `Sacar rutas de subcarpetas.py` |
| **Info entorno** | Versión de Python y de cada paquete de un venv o del Python global; guarda un único `requirements.txt` (pip freeze). | `info_entorno.py` |
| **Licencias** | `THIRD_PARTY_NOTICES.txt` con la licencia completa de cada paquete de un venv o del Python global. Admite el JSON extra (ver abajo). Sesiones con nombre. | `generar_licencias.py` |
| **Acerca de** | Versión, creador, cómo se está ejecutando (código fuente, PyInstaller o Nuitka) y dónde se guarda la configuración. | — |

Las pestañas de venv ejecutan el `python` del entorno elegido, así que no hace falta activarlo (también funciona desde el `.exe` compilado).
Todo el trabajo pesado corre en segundo plano: la ventana no se congela al copiar, escanear o generar documentos.

## Usar desde el código

```bat
crear_venv.bat
.venv\Scripts\pythonw.exe utilidades_archivos\utilidades_archivos.py
```

`crear_venv.bat` crea `.venv` (Python 3.13 si lo tienes, si no el más nuevo) e instala `requirements-dev.txt`: PyQt6, PyInstaller, Nuitka y Pillow. Si ya existe, lo actualiza.
Con `pythonw` se abre sin ventana de consola.

## Compilar

Doble clic en **`compilar.bat`** y elige una opción:

| Opción | Resultado |
|---|---|
| 1. PyInstaller, carpeta (recomendado) | `dist\pyinstaller\UtilidadesArchivos\UtilidadesArchivos.exe` (~75 MB, abre rápido) |
| 2. PyInstaller, un solo .exe | `dist\pyinstaller\UtilidadesArchivos.exe` |
| 3. Nuitka, carpeta | `dist\nuitka\UtilidadesArchivos\UtilidadesArchivos.exe` (código C nativo, tarda varios minutos) |
| 4. Nuitka, un solo .exe | `dist\nuitka\UtilidadesArchivos.exe` |
| 5. Ambos | PyInstaller y Nuitka, en carpeta |

También desde la terminal, con más opciones:

```bat
.venv\Scripts\python.exe compilar.py pyinstaller [--onefile] [--consola] [--sin-prueba]
.venv\Scripts\python.exe compilar.py nuitka      [--onefile] [--consola] [--sin-prueba]
.venv\Scripts\python.exe compilar.py todo
```

- `--consola`: compila con ventana de consola, para ver errores.
- Al terminar, `compilar.py` ejecuta el `.exe` con **`--autoprueba`**: sin mostrar la ventana y con una configuración temporal, prueba los recursos, los complementos de Qt y cada pestaña con archivos de prueba (incluido el JSON extra de Licencias), y mide cuánto se traba la interfaz. Imprime `OK`/`FALLO` por prueba.
- Nuitka necesita un compilador de C: usa Visual Studio Build Tools si lo tienes; si no, lo descarga solo la primera vez.
- La versión, el nombre y el autor del `.exe` (clic derecho → Propiedades → Detalles) salen de las constantes `APP_*` al inicio de `utilidades_archivos.py`. Para una versión nueva basta con cambiar `APP_VERSION` ahí.

La autoprueba también se puede correr a mano: `UtilidadesArchivos.exe --autoprueba` deja `autoprueba.json` junto al `.exe` (tu configuración no se toca).

## Dónde se guardan los datos

| Archivo | Qué es |
|---|---|
| `utilidades_config.json` | Tema, sesiones guardadas, último venv, pestaña y tamaño de la ventana. Se actualiza solo. |
| `registros\` | Registros completos de robocopy (solo si activas la opción en Copiar). |
| `fallo_grave.log` | Si la app falla o se cierra sola, aquí queda el motivo (errores de Python, mensajes graves de Qt, pila de Python). Se reescribe en cada arranque. |

Van **junto al `.exe`** (o junto a `utilidades_archivos.py`), así la app es portable. Si esa carpeta no se puede escribir (por ejemplo en *Archivos de programa*), van a `%LOCALAPPDATA%\UtilidadesArchivos`. La pestaña *Acerca de* muestra la ruta exacta y tiene un botón para abrirla.

## JSON extra de Licencias

Opcional (pestaña Licencias → *Mostrar opciones avanzadas*). Las rutas de `archivo` son relativas a la carpeta del JSON.

```json
{
  "encabezado": "Texto propio que va debajo del título del documento.",
  "componentes": [
    {
      "nombre": "FFmpeg",
      "version": "7.0",
      "tipo": "GNU GPL v3",
      "url": "https://ffmpeg.org",
      "nota": "Se ejecuta como proceso externo.",
      "archivo": "tools/ffmpeg/LICENSE"
    }
  ],
  "faltantes": {
    "paquete-sin-licencia": { "tipo": "MIT", "texto": "…" }
  }
}
```

- `componentes`: cosas que no son paquetes de Python (programas externos, modelos…). Usa `archivo` o `texto`.
- `faltantes`: licencia para paquetes que no traen la suya dentro del wheel.

## Cambiar el logo

Reemplaza `utilidades_archivos\recursos\logo_app.png` (cuadrado, de preferencia 512 px o más, con fondo transparente) y vuelve a compilar: `compilar.py` regenera `app.ico` solo. El avatar del creador es `recursos\avatar_DoMiN.jpg`.

## Estructura

```
utilidades_archivos/
├── utilidades_archivos.py     ← la app (un solo archivo)
└── recursos/                  ← logo_app.png, app.ico, avatar_DoMiN.jpg (van dentro del .exe)
legacy/                        ← scripts originales, solo como referencia
compilar.py / compilar.bat     ← compilación con PyInstaller o Nuitka + autoprueba
crear_venv.bat                 ← crea .venv con todo lo necesario
requirements.txt               ← solo para ejecutar (PyQt6)
requirements-dev.txt           ← para compilar (PyInstaller, Nuitka, Pillow)
```

## Notas

- **Rutas largas:** Windows no carga DLLs con rutas de más de 260 caracteres. Si la app está en una carpeta muy profunda, usa la ruta corta (8.3) de sus complementos de Qt para no fallar con *"no Qt platform plugin could be initialized"*.
- **Antivirus:** un `.exe` sin firma digital puede tardar en abrir la primera vez (el antivirus lo analiza) o incluso ser bloqueado. Firmarlo con tu certificado lo evita.
- **Licencia de PyQt6:** PyQt6 es GPL v3. Si vas a repartir el `.exe`, el código de la app tiene que publicarse con una licencia compatible con la GPL.
