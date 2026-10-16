#!/usr/bin/env python3
"""El manual de usuario (MANUAL.md) como página HTML para verlo dentro del editor.

Se convierte con Python-Markdown (tablas, bloques de código e índice con los
mismos anclajes que GitHub, para que funcionen los enlaces del índice) y las
capturas de docs/manual/ se enlazan con su ruta absoluta. No necesita Internet.
"""
from __future__ import annotations

import html
import re
import sys
import tempfile
from pathlib import Path

from app import firma


def raiz() -> Path:
    """Carpeta del programa: la del proyecto o, en el .exe, donde PyInstaller extrae los datos."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def _anclaje(texto: str, _separador: str = "-") -> str:
    """Anclaje al estilo de GitHub: minúsculas, sin signos y espacios -> guiones (conserva tildes)."""
    texto = re.sub(r"[^\w\- ]", "", texto.strip().lower())
    return texto.replace(" ", "-")


def a_html(markdown_texto: str, base: Path) -> str:
    import markdown

    cuerpo = markdown.markdown(
        markdown_texto,
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
        extension_configs={"toc": {"slugify": _anclaje}},
    )
    # Rutas relativas (capturas y documentos) -> absolutas, para que se vean desde el archivo temporal.
    def absoluta(m: re.Match) -> str:
        atributo, ruta = m.group(1), m.group(2)
        if re.match(r"^[a-z]+:|^#|^/", ruta):
            return m.group(0)
        return f'{atributo}="{(base / ruta).resolve().as_uri()}"'

    cuerpo = re.sub(r'(src|href)="([^"]+)"', absoluta, cuerpo)
    return PLANTILLA.replace("{{titulo}}", html.escape(f"Manual · {firma()}")).replace("{{cuerpo}}", cuerpo)


def generar() -> Path:
    """Convierte MANUAL.md y devuelve el HTML (en la carpeta temporal del sistema)."""
    origen = raiz() / "MANUAL.md"
    if not origen.is_file():
        raise ValueError(f"No se encuentra el manual ({origen}).")
    destino = Path(tempfile.gettempdir()) / "pruebas_yaml_manual.html"
    destino.write_text(a_html(origen.read_text(encoding="utf-8"), origen.parent), encoding="utf-8")
    return destino


PLANTILLA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{{titulo}}</title>
<style>
:root { --bg: #ffffff; --ink: #18242b; --ink-2: #485862; --rule: #d2d9de; --panel: #f5f7f8; --accent: #0b5f73; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #1c262c; --ink: #e3eaed; --ink-2: #aab9c1; --rule: #2a363d; --panel: #172025; --accent: #5cc0d6; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
       font: 15px/1.6 "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, Arial, sans-serif; }
main { max-width: 900px; margin: 0 auto; padding: 24px 28px 80px; }
h1 { font-size: 26px; margin: 0 0 12px; }
h2 { font-size: 21px; margin: 36px 0 10px; padding-top: 12px; border-top: 1px solid var(--rule); }
h3 { font-size: 17px; margin: 26px 0 8px; }
h4 { font-size: 15px; margin: 20px 0 6px; }
a { color: var(--accent); }
img { max-width: 100%; height: auto; border: 1px solid var(--rule); border-radius: 6px; margin: 8px 0; }
table { border-collapse: collapse; margin: 12px 0; font-size: 14px; }
th, td { border: 1px solid var(--rule); padding: 5px 9px; text-align: left; vertical-align: top; }
th { background: var(--panel); }
td img { max-width: 420px; }
code { font-family: "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace; font-size: 13px;
       background: var(--panel); padding: 1px 4px; border-radius: 3px; }
pre { background: var(--panel); padding: 10px 14px; border-radius: 6px; overflow-x: auto; }
pre code { padding: 0; background: none; }
blockquote { margin: 12px 0; padding: 8px 14px; border-left: 4px solid var(--accent); background: var(--panel); color: var(--ink-2); }
hr { border: 0; border-top: 1px solid var(--rule); margin: 28px 0; }
</style>
</head>
<body><main>
{{cuerpo}}
</main></body>
</html>
"""
