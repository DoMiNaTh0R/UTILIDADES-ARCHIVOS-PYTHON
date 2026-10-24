@echo off
setlocal
:: Menu para compilar con el venv del proyecto (lo crea build_env.bat).
:: Para opciones extra (--consola, --sin-prueba) usa compilar.py directamente.
cd /d "%~dp0"
if not exist "build_env\Scripts\python.exe" goto sin_entorno
"build_env\Scripts\python.exe" -c "import PyInstaller, PyQt6" >nul 2>nul
if not errorlevel 1 goto menu
echo build_env esta roto o le falta PyInstaller. Ejecuta build_env.bat y vuelve a intentarlo.
pause
exit /b 1

:sin_entorno
echo No existe el entorno virtual. Ejecuta primero build_env.bat
pause
exit /b 1

:menu
echo === Utilidades de archivos: compilar con PyInstaller ===
echo.
echo   1) Carpeta          (recomendado, abre mas rapido; es la que usa el instalador)
echo   2) Un solo .exe
echo   3) Salir
echo.
choice /c 123 /n /m "Elige una opcion: "
set "OPCION=%errorlevel%"
if "%OPCION%"=="3" exit /b 0
set "ARGS="
if "%OPCION%"=="2" set "ARGS=--onefile"

echo.
"build_env\Scripts\python.exe" compilar.py %ARGS%
echo.
if errorlevel 1 echo Algo fallo: revisa los mensajes de arriba.
if not errorlevel 1 echo Todo listo. El ejecutable quedo en la carpeta dist\pyinstaller.
pause
