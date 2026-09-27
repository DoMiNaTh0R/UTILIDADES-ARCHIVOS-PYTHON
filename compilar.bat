@echo off
setlocal
:: Menu para compilar con el venv del proyecto (lo crea build_env.bat).
:: Para opciones extra (--consola, --sin-prueba) usa compilar.py directamente.
cd /d "%~dp0"
if exist "build_env\Scripts\python.exe" goto menu
echo No existe el entorno virtual. Ejecuta primero build_env.bat
pause
exit /b 1

:menu
echo === Utilidades de archivos: compilar ===
echo.
echo   1) PyInstaller - carpeta        (recomendado, abre mas rapido)
echo   2) PyInstaller - un solo .exe
echo   3) Nuitka      - carpeta        (codigo C nativo, tarda varios minutos)
echo   4) Nuitka      - un solo .exe
echo   5) PyInstaller y Nuitka         (carpeta)
echo   6) Salir
echo.
choice /c 123456 /n /m "Elige una opcion: "
set "OPCION=%errorlevel%"
if "%OPCION%"=="6" exit /b 0
if "%OPCION%"=="1" set "ARGS=pyinstaller"
if "%OPCION%"=="2" set "ARGS=pyinstaller --onefile"
if "%OPCION%"=="3" set "ARGS=nuitka"
if "%OPCION%"=="4" set "ARGS=nuitka --onefile"
if "%OPCION%"=="5" set "ARGS=todo"

echo.
"build_env\Scripts\python.exe" compilar.py %ARGS%
echo.
if errorlevel 1 echo Algo fallo: revisa los mensajes de arriba.
if not errorlevel 1 echo Todo listo. El ejecutable quedo en la carpeta dist.
pause
