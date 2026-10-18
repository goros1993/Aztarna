@echo off
REM Genera dist\Aztarna.exe (un solo archivo, sin consola).
REM Hay que ejecutarlo en Windows: PyInstaller no compila de forma cruzada.
REM Requiere Python 3.10 o posterior (py -3).

cd /d "%~dp0"

REM Se usa el python.exe del entorno directamente (sin activate.bat ni pyinstaller.exe):
REM esos guardan la ruta absoluta de la carpeta y dejan de funcionar si se mueve o renombra.
set PY=.venv-build\Scripts\python.exe
if exist %PY% (
    %PY% -c "import sys" 2>nul || rmdir /s /q .venv-build
)
if not exist %PY% (
    py -3 -m venv .venv-build || goto :error
)
%PY% -m pip install --upgrade pip || goto :error
%PY% -m pip install -r requirements.txt pyinstaller || goto :error

REM web\ va dentro del .exe. No se empaquetan los ejemplos: el .exe se extrae en una
REM carpeta temporal y lo que se editara ahi se perderia al cerrar.
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name Aztarna ^
    --icon recursos\icono.ico ^
    --add-data "web;web" ^
    --add-data "recursos\icono.ico;recursos" ^
    --add-data "MANUAL.md;." ^
    --add-data "docs\manual;docs\manual" ^
    --collect-submodules webview ^
    --collect-submodules app ^
    --collect-submodules markdown ^
    editor_web.py || goto :error

REM version.txt junto al .exe: si se publica en una carpeta compartida, el editor de cada
REM persona avisa cuando hay una version nueva (Ajustes, «Carpeta con la ultima version»).
%PY% -c "import app; print(app.__version__)" > dist\version.txt || goto :error

echo.
echo Listo: dist\Aztarna.exe y dist\version.txt
echo Para publicarlo, copia los dos a la carpeta compartida del programa.
echo Necesita WebView2 (viene con Windows 11 y con Windows 10 actualizado).
goto :eof

:error
echo.
echo La construccion ha fallado. Revisa el mensaje anterior.
exit /b 1
