#!/usr/bin/env python3
"""Editor de pruebas YAML con interfaz web local (pywebview).

Uso:
    python editor_web.py                 # la última carpeta usada, o ejemplos/yaml
    python editor_web.py ruta/a/yaml     # abre otra carpeta (el proyecto o su carpeta pruebas/)
    python editor_web.py --depurar       # con herramientas de desarrollo

No arranca ningún servidor: la interfaz (web/) se carga como archivos locales
dentro de una ventana nativa y se comunica con Python por un puente interno.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app import ajustes
from app.validacion_api import EditorValidacionApi as EditorApi


def recurso(relativa: str) -> Path:
    """Ruta de un recurso, tanto en desarrollo como dentro del .exe de PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relativa


def carpeta_por_defecto() -> Path | None:
    """Carpeta de ejemplos junto al programa, si existe; si no, None (se pedirá una)."""
    candidatas = [
        Path.cwd() / "ejemplos" / "yaml",
        Path(sys.executable).resolve().parent / "ejemplos" / "yaml",
        recurso("ejemplos/yaml"),
    ]
    return next((c for c in candidatas if (c / "pruebas" / "indice.yaml").is_file() or (c / "indice.yaml").is_file()), None)


def ultima_carpeta() -> Path | None:
    valor = ajustes.leer().get("ultima_carpeta")
    carpeta = Path(valor) if isinstance(valor, str) and valor else None
    return carpeta if carpeta and carpeta.is_dir() else None


def recordar_carpeta(carpeta: Path) -> None:
    ajustes.guardar({"ultima_carpeta": str(carpeta)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Editor de pruebas YAML")
    parser.add_argument("carpeta", nargs="?", help="carpeta del proyecto (pruebas/ y requisitos/) o la de pruebas")
    parser.add_argument("--depurar", action="store_true", help="activa las herramientas de desarrollo")
    args = parser.parse_args()

    try:
        import webview
    except ImportError:
        raise SystemExit("Falta pywebview. Instálalo con: python -m pip install -r requirements.txt")

    pagina = recurso("web/index.html")
    if not pagina.is_file():
        raise SystemExit(f"No se encuentra la interfaz web: {pagina}")

    # Con --windowed (PyInstaller) no hay consola: sys.stdout/stderr valen None.
    for nombre in ("stdout", "stderr"):
        if getattr(sys, nombre) is None:
            setattr(sys, nombre, open(os.devnull, "w", encoding="utf-8"))

    carpeta = Path(args.carpeta).expanduser() if args.carpeta else (ultima_carpeta() or carpeta_por_defecto())
    api = EditorApi(carpeta)
    api._al_cargar = recordar_carpeta
    ventana = webview.create_window(
        "Editor de pruebas YAML",
        url=pagina.as_uri(),
        js_api=api,
        width=1360,
        height=880,
        min_size=(980, 640),
        text_select=True,    # sin esto pywebview impide seleccionar y copiar texto (IDs, mensajes)
    )
    api._window = ventana
    ventana.events.closing += api._al_cerrar_ventana   # pregunta si hay cambios sin guardar
    icono = recurso("recursos/icono.png")
    # El icono de la ventana: en Linux se indica aquí; en Windows se usa el del .exe.
    webview.start(debug=args.depurar, icon=str(icono) if icono.is_file() else None)


if __name__ == "__main__":
    main()
