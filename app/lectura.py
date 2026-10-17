#!/usr/bin/env python3
"""Lecturas en caché para consultar (no para editar).

Consolidar una validación lee muchos YAML: los de sus ejecuciones, las pruebas
congeladas, los requisitos y los de la validación anterior. Con 1000 pruebas,
leerlos cuesta segundos, y se consolida cada vez que cambia algo. Aquí se
guarda lo leído y solo se vuelve a leer un archivo si ha cambiado (fecha de
modificación o tamaño).

Lo que devuelve se comparte entre llamadas: NO se debe modificar. Para editar,
usa las funciones normales (`read_chapters`, `ejecucion_core.cargar`).
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

_cache: dict[tuple[str, str], tuple[Any, Any]] = {}
_lock = threading.Lock()
MAXIMO = 64


def _firma(rutas: list[Path]) -> tuple:
    firma = []
    for ruta in rutas:
        try:
            st = ruta.stat()
            firma.append((ruta.name, st.st_mtime_ns, st.st_size))
        except OSError:
            firma.append((ruta.name, None, None))
    return tuple(firma)


def _en_cache(tipo: str, carpeta: Path, rutas: list[Path], leer: Callable[[], Any]) -> Any:
    clave = (tipo, str(carpeta))
    firma = _firma(rutas)
    with _lock:
        guardado = _cache.get(clave)
        if guardado is not None and guardado[0] == firma:
            return guardado[1]
    valor = leer()
    with _lock:
        if len(_cache) >= MAXIMO:
            _cache.pop(next(iter(_cache)))
        _cache[clave] = (firma, valor)
    return valor


def capitulos(carpeta: str | Path) -> list[dict[str, Any]]:
    """Como `read_chapters`, pero en caché (solo lectura)."""
    from app.editor_core import read_chapters
    carpeta = Path(carpeta).resolve()
    rutas = sorted(carpeta.glob("*.yaml"))
    return _en_cache("capitulos", carpeta, rutas, lambda: read_chapters(carpeta))


def requisitos(carpeta_pruebas: str | Path) -> list[dict[str, Any]]:
    """Como `trazabilidad.leer_requisitos`, pero en caché (solo lectura)."""
    from app import trazabilidad
    carpeta = trazabilidad.carpeta_requisitos(carpeta_pruebas)
    if not carpeta.is_dir() or not any(carpeta.glob("*.yaml")):
        return []
    return capitulos(carpeta)


def ejecucion(carpeta: str | Path) -> dict[str, Any]:
    """Como `ejecucion_core.cargar`, pero en caché (solo lectura)."""
    from app import ejecucion_core as ej
    carpeta = Path(carpeta).resolve()
    rutas = [ej.archivo_datos(carpeta), carpeta / ej.ARCHIVO_RESULTADOS]
    return _en_cache("ejecucion", carpeta, rutas, lambda: ej.cargar(carpeta))


def vaciar() -> None:
    with _lock:
        _cache.clear()
