@echo off
REM Genera dist\EditorPruebas.exe (un solo archivo, sin consola).
REM Hay que ejecutarlo en Windows: PyInstaller no compila de forma cruzada.
REM Requiere Python 3.10 o posterior (py -3).

cd /d "%~dp0"

if not exist .venv-build (
    py -3 -m venv .venv-build || goto :error
)
call .venv-build\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt pyinstaller || goto :error

REM web\ va dentro del .exe. No se empaquetan los ejemplos: el .exe se extrae en una
REM carpeta temporal y lo que se editara ahi se perderia al cerrar.
pyinstaller --noconfirm --clean --onefile --windowed ^
    --name EditorPruebas ^
    --add-data "web;web" ^
    --collect-submodules webview ^
    editor_web.py || goto :error

echo.
echo Listo: dist\EditorPruebas.exe
echo Necesita WebView2 (viene con Windows 11 y con Windows 10 actualizado).
goto :eof

:error
echo.
echo La construccion ha fallado. Revisa el mensaje anterior.
exit /b 1
