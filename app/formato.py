#!/usr/bin/env python3
"""Versión del formato de los datos, para poder migrarlos algún día.

No es la versión del programa (que cambia con cada mejora), sino un número que
solo sube cuando cambia la forma de guardar los datos. Va una vez por carpeta:

- en `pruebas/` y `requisitos/`, el archivo `formato.yaml`;
- en una ejecución (`ejecucion.yaml`) y en una validación (`validacion.yaml`),
  la clave `formato`.

Lo que no lo indica es del formato 1 (todo lo anterior a esta marca). Se
escribe al guardar. Un programa que encuentra un formato más nuevo que el suyo
no guarda nada (y lo dice): así una copia antigua del programa no estropea
datos que no entiende.

Para cambiar de formato: sube FORMATO, escribe la migración del anterior y
anótalo en CHANGELOG.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

FORMATO = 1
ARCHIVO = "formato.yaml"


class FormatoNuevo(ValueError):
    """Los datos están en un formato más nuevo que el que entiende este programa."""


def _numero(valor: Any) -> int:
    try:
        return max(int(valor), 1)
    except (TypeError, ValueError):
        return 1


def mensaje(formato: int, que: str) -> str:
    from app import firma
    return (f"{que} se guardó con una versión más nueva del programa (formato de datos {formato}; "
            f"este programa, {firma()}, entiende hasta el {FORMATO}). Se puede consultar, pero no guardar: "
            "actualiza el programa.")


# --- carpetas de pruebas y de requisitos -----------------------------------------
def de_carpeta(carpeta: str | Path) -> int:
    """Formato de una carpeta de pruebas o de requisitos (1 si no lo indica)."""
    ruta = Path(carpeta) / ARCHIVO
    if not ruta.is_file():
        return 1
    from ruamel.yaml import YAML, YAMLError
    try:
        datos = YAML(typ="safe").load(ruta.read_text(encoding="utf-8"))
    except (OSError, YAMLError):
        return 1
    return _numero(datos.get("formato")) if isinstance(datos, dict) else 1


def es_nuevo(formato: int) -> bool:
    return formato > FORMATO


def comprobar_carpeta(carpeta: str | Path, que: str = "Esta carpeta") -> None:
    formato = de_carpeta(carpeta)
    if es_nuevo(formato):
        raise FormatoNuevo(mensaje(formato, que))


def marcar_carpeta(carpeta: str | Path) -> None:
    """Escribe (o pone al día) `formato.yaml` en la carpeta, si hace falta. No baja nunca el formato."""
    from app import firma
    carpeta = Path(carpeta)
    if not carpeta.is_dir() or de_carpeta(carpeta) > FORMATO:
        return
    ruta = carpeta / ARCHIVO
    texto = ("# Formato de los datos de esta carpeta (lo escribe el editor; no lo cambies a mano).\n"
             f"formato: {FORMATO}\nescrito_con: {firma()}\n")
    try:
        if not ruta.is_file() or ruta.read_text(encoding="utf-8") != texto:
            ruta.write_text(texto, encoding="utf-8")
    except OSError:
        pass                      # no poder marcarla no debe impedir guardar


# --- ejecuciones y validaciones (una clave en su YAML) -----------------------------
def de_datos(datos: Any) -> int:
    return _numero(datos.get("formato")) if isinstance(datos, dict) else 1


def comprobar_datos(datos: Any, que: str) -> None:
    formato = de_datos(datos)
    if es_nuevo(formato):
        raise FormatoNuevo(mensaje(formato, que))


def marcar_datos(datos: Any) -> None:
    """Pone `formato` en los datos (al principio, para que se vea) si falta o es más antiguo."""
    if not isinstance(datos, dict) or ("formato" in datos and de_datos(datos) >= FORMATO):
        return
    if hasattr(datos, "insert"):                         # CommentedMap de ruamel
        if "formato" in datos:
            datos["formato"] = FORMATO
        else:
            datos.insert(0, "formato", FORMATO)
    else:
        datos["formato"] = FORMATO
