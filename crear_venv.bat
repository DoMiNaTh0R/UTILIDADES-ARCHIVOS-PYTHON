@echo off
setlocal
:: Crea (o actualiza) el entorno virtual .venv con todo lo necesario para
:: ejecutar y compilar la app. Funciona en rutas con espacios y parentesis.
cd /d "%~dp0"
echo === Utilidades de archivos: entorno virtual ===
echo.

if exist ".venv\Scripts\python.exe" goto instalar

echo Creando .venv ...
where py >nul 2>nul
if errorlevel 1 goto sin_py
py -3.13 -m venv .venv 2>nul
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
goto revisar

:sin_py
python -m venv .venv

:revisar
if exist ".venv\Scripts\python.exe" goto instalar
echo No se pudo crear el entorno virtual. Instala Python 3.9 o superior.
pause
exit /b 1

:instalar
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install --upgrade -r requirements-dev.txt
if errorlevel 1 goto error_pip

echo.
echo Listo.
echo   Abrir la app:  .venv\Scripts\pythonw.exe utilidades_archivos\utilidades_archivos.py
echo   Compilar:      compilar.bat
pause
exit /b 0

:error_pip
echo.
echo Error instalando las dependencias (revisa tu conexion a internet).
pause
exit /b 1
