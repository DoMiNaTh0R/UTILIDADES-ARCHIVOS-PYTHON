# Instalar y compilar

## Usar la app ya compilada

Descarga el instalador de la página de [Releases](https://github.com/DoMiNaTh0R/UTILIDADES-ARCHIVOS-PYTHON/releases) y ejecútalo. No necesitas Python.

## Compilar tú mismo (PyInstaller)

**Necesitas:** Windows 10/11 y [Python](https://www.python.org/downloads/windows/) 3.9 o superior (recomendado 3.13, con el lanzador `py`).

### 1. Crear el entorno virtual

Doble clic en **`build_env.bat`**. Crea la carpeta `build_env\` con PyQt6, Pillow y PyInstaller (si ya existe, solo los actualiza).

Para abrir la app sin compilar:

```bat
build_env\Scripts\pythonw.exe utilidades_archivos.py
```

### 2. Compilar

Doble clic en **`compilar.bat`** y elige:

| Opción | Resultado |
|---|---|
| 1. Carpeta (recomendado) | `dist\pyinstaller\UtilidadesArchivos\UtilidadesArchivos.exe` — abre más rápido. Copia la carpeta completa, no solo el `.exe`. |
| 2. Un solo .exe | `dist\pyinstaller\UtilidadesArchivos.exe` — más cómodo de pasar, tarda un poco más en abrir. |

O desde la terminal:

```bat
build_env\Scripts\python.exe compilar.py [--onefile] [--consola] [--sin-prueba]
```

- `--consola`: con ventana de consola, para ver errores.
- `--sin-prueba`: no ejecuta la autoprueba al terminar.

Al terminar, `compilar.py` abre el `.exe` con `--autoprueba` (sin mostrar la ventana y sin tocar tu configuración) y muestra `OK` o `FALLO` por cada prueba. Junto al `.exe` quedan `LICENSE`, `THIRD_PARTY_NOTICES.txt` y `LICENCIA_LOGO_Y_AVATAR.txt`.

### Notas

- La versión, el nombre y el autor del `.exe` salen de las constantes `APP_*` al inicio de `utilidades_archivos.py`: para una versión nueva basta con cambiar `APP_VERSION`.
- Sin la carpeta `recursos\` se compila igual, pero sin icono ni imágenes.
- Un `.exe` sin firma digital puede tardar en abrir la primera vez (el antivirus lo revisa) o incluso ser bloqueado.
