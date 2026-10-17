#!/usr/bin/env python3
"""Ajustes del usuario en este PC (última carpeta, configuración de Robot…).

Se guardan en un JSON (por defecto, %APPDATA%/Aztarna/ajustes.json o
~/.config/Aztarna/ajustes.json; se puede cambiar con la variable de entorno
AZTARNA_AJUSTES). Cada cambio se fusiona con lo que ya había.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def archivo() -> Path:
    personalizado = os.environ.get("AZTARNA_AJUSTES")
    if personalizado:
        return Path(personalizado)
    raiz = Path(os.environ.get("APPDATA") or Path.home() / ".config")
    return raiz / "Aztarna" / "ajustes.json"


def leer() -> dict[str, Any]:
    try:
        datos = json.loads(archivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def guardar(cambios: dict[str, Any]) -> None:
    """Fusiona `cambios` (primer nivel) con los ajustes guardados."""
    ruta = archivo()
    datos = {**leer(), **cambios}
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporal, ruta)
    except OSError:
        pass  # no poder guardar los ajustes no debe impedir trabajar
