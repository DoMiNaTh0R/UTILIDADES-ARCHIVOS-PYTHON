@echo off
setlocal
:: Crea (o actualiza) el entorno virtual build_env con todo lo necesario para
:: ejecutar y compilar la app (PyQt6, Pillow y PyInstaller).
:: Funciona en rutas con espacios y parentesis.
cd /d "%~dp0"
echo === Utilidades de archivos: entorno virtual (build_env) ===
echo.

:: Un venv queda roto si se desinstala el Python con el que se creo: se vuelve a crear
if not exist "build_env\Scripts\python.exe" goto crear
"build_env\Scripts\python.exe" -c "import sys" >nul 2>nul
if not errorlevel 1 goto instalar
echo build_env esta roto: el Python con el que se creo ya no esta instalado. Se vuelve a crear...
rmdir /s /q build_env

:crear

echo Creando build_env ...
where py >nul 2>nul
if errorlevel 1 goto sin_py
py -3.13 -m venv build_env 2>nul
if not exist "build_env\Scripts\python.exe" py -3 -m venv build_env
goto revisar

:sin_py
python -m venv build_env

:revisar
if exist "build_env\Scripts\python.exe" goto instalar
echo No se pudo crear el entorno virtual. Instala Python 3.9 o superior.
pause
exit /b 1

:instalar
"build_env\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error_pip

"build_env\Scripts\python.exe" -m pip install --upgrade PyQt6 Pillow "pyinstaller>=6.10" pyinstaller-hooks-contrib
if errorlevel 1 goto error_pip

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
