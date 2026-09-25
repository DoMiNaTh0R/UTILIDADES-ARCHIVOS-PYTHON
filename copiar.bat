@echo off
REM =====================================================================
REM SCRIPT DE COPIADO CON ROBOCOPY
REM =====================================================================
REM Descripcion: Copia carpetas de forma recursiva excluyendo entornos
REM              virtuales y carpetas de compilacion.
REM
REM Uso: doble clic sobre este archivo y sigue las instrucciones.
REM =====================================================================

echo ===================================
echo   Script de respaldo con Robocopy
echo ===================================
echo.
echo.

set /p "ORIGEN=Ruta de origen: "
echo.
set /p "DESTINO=Ruta de destino: "
echo.

if "%ORIGEN:~-1%"=="\" set "ORIGEN=%ORIGEN:~0,-1%"
if "%DESTINO:~-1%"=="\" set "DESTINO=%DESTINO:~0,-1%"

echo Copiando, un momento...
echo.

robocopy "%ORIGEN%" "%DESTINO%" /E /XD ".venv*" "__pycache__" "venv*" "build*" /R:4 /W:5 /ETA

pause