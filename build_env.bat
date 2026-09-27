@echo off
setlocal
:: Crea (o actualiza) el entorno virtual build_env con todo lo necesario para
:: ejecutar y compilar la app. Funciona en rutas con espacios y parentesis.
cd /d "%~dp0"
echo === Utilidades de archivos: entorno virtual (build_env) ===
echo.

if exist "build_env\Scripts\python.exe" goto elegir_compilador

echo Creando build_env ...
where py >nul 2>nul
if errorlevel 1 goto sin_py
py -3.13 -m venv build_env 2>nul
if not exist "build_env\Scripts\python.exe" py -3 -m venv build_env
goto revisar

:sin_py
python -m venv build_env

:revisar
if exist "build_env\Scripts\python.exe" goto elegir_compilador
echo No se pudo crear el entorno virtual. Instala Python 3.9 o superior.
pause
exit /b 1

:elegir_compilador
echo.
echo Que empaquetador quieres instalar/actualizar?
echo   1. PyInstaller
echo   2. Nuitka
echo   3. Ambos
echo   4. Ninguno (solo dependencias base)
choice /c 1234 /n /m "Elige una opcion (1-4): "
set COMPILADOR=%errorlevel%

:instalar
"build_env\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error_pip

"build_env\Scripts\python.exe" -m pip install --upgrade PyQt6 Pillow
if errorlevel 1 goto error_pip

if %COMPILADOR%==1 (
    "build_env\Scripts\python.exe" -m pip install --upgrade "pyinstaller>=6.10" pyinstaller-hooks-contrib
    if errorlevel 1 goto error_pip
)
if %COMPILADOR%==2 (
    "build_env\Scripts\python.exe" -m pip install --upgrade "nuitka>=2.7"
    if errorlevel 1 goto error_pip
)
if %COMPILADOR%==3 (
    "build_env\Scripts\python.exe" -m pip install --upgrade "pyinstaller>=6.10" pyinstaller-hooks-contrib "nuitka>=2.7"
    if errorlevel 1 goto error_pip
)

echo.
echo Listo.
echo   Abrir la app:  build_env\Scripts\pythonw.exe utilidades_archivos.py
echo   Compilar:      compilar.bat
pause
exit /b 0

:error_pip
echo.
echo Error instalando las dependencias (revisa tu conexion a internet).
pause
exit /b 1
