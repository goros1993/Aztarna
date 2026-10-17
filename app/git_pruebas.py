#!/usr/bin/env python3
"""Qué versión de las pruebas se usa, si están en un repositorio de Git.

Cada persona trabaja con su copia (clon) del repositorio de pruebas, así que
dos ejecuciones pueden hacerse con versiones distintas. Al crear y al cerrar
una ejecución se guarda el estado de la carpeta de pruebas:

    git:
      commit: 3f2a9c1e…          # commit en el que estaba la copia
      etiqueta: v2.3             # si ese commit tiene una (o «v2.3-4-g3f2a9c1»)
      rama: main
      cambios: false             # cambios sin commit en la carpeta de pruebas

Sin Git (no instalado, o la carpeta no es de un repositorio) no se guarda
nada y todo sigue igual.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _git(carpeta: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(carpeta), *args], capture_output=True, text=True, timeout=10,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def estado(carpeta_pruebas: str | Path) -> dict[str, Any] | None:
    """Commit, etiqueta, rama y si hay cambios sin commit en la carpeta de pruebas; None sin Git."""
    carpeta = Path(carpeta_pruebas)
    if not carpeta.is_dir():
        return None
    commit = _git(carpeta, "rev-parse", "HEAD")
    if not commit:
        return None
    datos: dict[str, Any] = {"commit": commit}
    etiqueta = _git(carpeta, "describe", "--tags", "--always")
    if etiqueta and not commit.startswith(etiqueta):        # sin etiquetas, describe da el commit abreviado
        datos["etiqueta"] = etiqueta
    rama = _git(carpeta, "rev-parse", "--abbrev-ref", "HEAD")
    if rama and rama != "HEAD":
        datos["rama"] = rama
    # Solo los cambios de las pruebas cuentan (y el aztarna.yaml del proyecto, que da sus opciones).
    rutas = ["."] + (["../aztarna.yaml"] if (carpeta.parent / "aztarna.yaml").is_file() else [])
    cambios = _git(carpeta, "status", "--porcelain", "--", *rutas)
    datos["cambios"] = bool(cambios)
    return datos


def texto(datos: dict[str, Any] | None, con_cambios: bool = True) -> str:
    """«v2.3 (3f2a9c1)», «3f2a9c1, con cambios sin commit»… o "" sin datos de Git."""
    if not datos or not datos.get("commit"):
        return ""
    corto = str(datos["commit"])[:7]
    base = f"{datos['etiqueta']} ({corto})" if datos.get("etiqueta") else corto
    return base + (", con cambios sin commit" if con_cambios and datos.get("cambios") else "")


def texto_ejecucion(datos_ejecucion: dict[str, Any]) -> str:
    """Versión de las pruebas de una ejecución: la de cuando se creó y, si cambió, la de cuando se cerró."""
    inicio, cierre = datos_ejecucion.get("git"), datos_ejecucion.get("git_cierre")
    if not cierre or (inicio and cierre.get("commit") == inicio.get("commit") and cierre.get("cambios") == inicio.get("cambios")):
        return texto(inicio)
    if not inicio:
        return f"{texto(cierre)} al cerrarla"
    return f"{texto(inicio)} al crearla; {texto(cierre)} al cerrarla"
