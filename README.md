# Utilidades de archivos

App de escritorio (PyQt6) que junta en una sola ventana varias utilidades que antes eran scripts sueltos.

```
utilidades_archivos/
├── utilidades_archivos.py     ← la app
└── utilidades_config.json     ← tema, sesiones guardadas, último venv… (se actualiza sola)
legacy/                        ← scripts originales, solo como referencia
```

## Uso

```
pip install -r requirements.txt
python utilidades_archivos/utilidades_archivos.py
```

Con `pythonw` en lugar de `python` se abre sin la ventana de consola.

## Pestañas

| Pestaña | Qué hace | Script original |
|---|---|---|
| **Copiar** | Robocopy con carpetas (`/XD`) y archivos (`/XF`) a omitir, reintentos, multihilo (`/MT`), simulación (`/L`) y salida en vivo. Sesiones con nombre. | `copiar.bat` |
| **Organizar** | Escanea una carpeta (recursivo), cuenta archivos por extensión y mueve o copia las marcadas a `<destino>/<extensión>/`. Nunca sobrescribe. | `Filtrador_y_movedor_de_archivos V2.py` |
| **Listar rutas** | `.txt` con las rutas de archivos y/o carpetas (recursivo). Filtro *Todo / Solo estas / Excluir estas* extensiones y carpetas a ignorar. Sesiones con nombre. | `Sacar rutas de subcarpetas.py` |
| **Info entorno** | Versión de Python y de cada paquete de un venv o del Python global; guarda un único `requirements.txt` (pip freeze). | `info_entorno.py` |
| **Licencias** | `THIRD_PARTY_NOTICES.txt` con la licencia completa de cada paquete de un venv o del Python global. Admite el JSON extra. Sesiones con nombre. | `generar_licencias.py` |

Las pestañas de venv ejecutan el `python` del entorno elegido, así que no hace falta activarlo.
