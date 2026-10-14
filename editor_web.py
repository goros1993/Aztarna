#!/usr/bin/env python3
"""Editor de pruebas YAML con interfaz web local (pywebview).

Uso:
    python editor_web.py                 # la última carpeta usada, o ejemplos/yaml
    python editor_web.py ruta/a/yaml     # abre otra carpeta
    python editor_web.py --depurar       # con herramientas de desarrollo

No arranca ningún servidor: la interfaz (web/) se carga como archivos locales
dentro de una ventana nativa y se comunica con Python por un puente interno.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from editor_api import EditorApi


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
    return next((c for c in candidatas if (c / "indice.yaml").is_file()), None)


def archivo_ajustes() -> Path:
    """Dónde se guarda la última carpeta usada (se puede cambiar con EDITOR_PRUEBAS_AJUSTES)."""
    personalizado = os.environ.get("EDITOR_PRUEBAS_AJUSTES")
    if personalizado:
        return Path(personalizado)
    raiz = Path(os.environ.get("APPDATA") or Path.home() / ".config")
    return raiz / "EditorPruebasYaml" / "ajustes.json"


def ultima_carpeta() -> Path | None:
    try:
        carpeta = Path(json.loads(archivo_ajustes().read_text(encoding="utf-8"))["ultima_carpeta"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return carpeta if carpeta.is_dir() else None


def recordar_carpeta(carpeta: Path) -> None:
    try:
        ruta = archivo_ajustes()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps({"ultima_carpeta": str(carpeta)}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # no poder recordar la carpeta no debe impedir trabajar


def main() -> None:
    parser = argparse.ArgumentParser(description="Editor de pruebas YAML")
    parser.add_argument("carpeta", nargs="?", help="carpeta con indice.yaml y los capítulos")
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
    webview.start(debug=args.depurar)


if __name__ == "__main__":
    main()
