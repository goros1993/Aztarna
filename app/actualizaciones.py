#!/usr/bin/env python3
"""Aviso de versión nueva del programa (cada persona tiene su copia del .exe).

En la carpeta compartida donde se publica el programa están `EditorPruebas.exe`
y `version.txt` (lo escribe `construir_exe.bat`) con su número de versión.
Cada persona indica esa carpeta en ⋯ → Ajustes…; al arrancar, el editor mira
si allí hay una versión más nueva que la suya y lo avisa. No actualiza nada
por su cuenta.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

ARCHIVO_VERSION = "version.txt"


def numero(version: str) -> tuple[int, ...]:
    """«0.12.0» → (0, 12, 0); lo que no sea un número cuenta como 0."""
    return tuple(int(x) for x in re.findall(r"\d+", str(version or ""))[:3]) or (0,)


def version_en(carpeta: str | Path, espera: float = 3.0) -> str | None:
    """Versión publicada en la carpeta (None si no hay o no se puede leer a tiempo: unidad de red caída)."""
    resultado: list[str | None] = [None]

    def leer() -> None:
        try:
            texto = (Path(carpeta) / ARCHIVO_VERSION).read_text(encoding="utf-8-sig").strip()
            resultado[0] = texto.splitlines()[0].strip() if texto else None
        except (OSError, IndexError):
            resultado[0] = None

    hilo = threading.Thread(target=leer, daemon=True)
    hilo.start()
    hilo.join(espera)
    return resultado[0]


def comprobar(carpeta: str | Path | None, actual: str) -> dict[str, Any]:
    """{"configurada", "carpeta", "version", "nueva"}: si en la carpeta hay una versión más nueva que `actual`."""
    if not carpeta:
        return {"configurada": False, "nueva": False}
    publicada = version_en(carpeta)
    return {"configurada": True, "carpeta": str(carpeta), "version": publicada,
            "accesible": publicada is not None,
            "nueva": bool(publicada) and numero(publicada) > numero(actual)}
