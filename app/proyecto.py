#!/usr/bin/env python3
"""Identidad del proyecto: su nombre, un identificador y dónde viven sus validaciones.

Las ejecuciones y las validaciones están fuera del repositorio de las pruebas
(en una carpeta compartida) y cada persona tiene las pruebas en su propia
ruta, así que la ruta no basta para saber de qué proyecto es cada una. Al
crearlas se guarda el identificador del proyecto:

    # ejecucion.yaml / validacion.yaml
    proyecto:
      id: git:3f2a9c1e04b7:pruebas-ascensor/
      nombre: Controlador DEMO-A1

El proyecto se describe en su `aztarna.yaml` (todo es opcional):

    proyecto:
      nombre: Controlador DEMO-A1
      validaciones: \\\\servidor\\pruebas\\DEMO-A1\\validaciones   # dónde se crean y se buscan
      id: …               # solo si se quiere fijar a mano

El identificador es, por orden: el de `aztarna.yaml`; si las pruebas están en
Git, el primer commit del repositorio y la subcarpeta del proyecto (igual en
todos los clones, sin escribir nada); si no, uno nuevo que se escribe en
`aztarna.yaml` la primera vez que hace falta (al crear una ejecución o una
validación). El nombre, si no se indica, es el de la carpeta del proyecto.
"""
from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from app import esquema


def carpeta_proyecto(carpeta_pruebas: str | Path) -> Path:
    """La carpeta del proyecto (la que contiene pruebas/) o la de pruebas, si es una suelta."""
    carpeta = Path(carpeta_pruebas)
    return carpeta.parent if carpeta.name == esquema.CARPETA_PRUEBAS else carpeta


def _archivo(carpeta_pruebas: str | Path) -> Path:
    """El aztarna.yaml que se lee o, si no hay, donde se crearía (en la carpeta del proyecto)."""
    return esquema.archivo_configuracion(carpeta_pruebas) or carpeta_proyecto(carpeta_pruebas) / esquema.ARCHIVO_CONFIGURACION


def _del_archivo(ruta: Path) -> dict[str, Any]:
    if not ruta.is_file():
        return {}
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    try:
        with ruta.open(encoding="utf-8") as f:
            datos = YAML(typ="safe").load(f) or {}
    except (OSError, YAMLError):
        return {}
    proyecto = datos.get("proyecto") if isinstance(datos, dict) else None
    return proyecto if isinstance(proyecto, dict) else {}


def _git(carpeta: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(carpeta), *args], capture_output=True, text=True, timeout=10,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def id_de_git(carpeta: Path) -> str | None:
    """«git:<primer commit>:<subcarpeta>»: igual en todos los clones del repositorio; None sin Git."""
    if not carpeta.is_dir():
        return None
    raices = _git(carpeta, "rev-list", "--max-parents=0", "HEAD")
    if not raices:
        return None
    prefijo = _git(carpeta, "rev-parse", "--show-prefix") or ""
    return f"git:{sorted(raices.split())[0][:12]}:{prefijo}"


def leer(carpeta_pruebas: str | Path | None) -> dict[str, Any] | None:
    """{"id", "nombre", "validaciones", "archivo"} del proyecto de esa carpeta de pruebas (sin escribir nada).

    `id` es None si no está en `aztarna.yaml` ni en Git (se crea con `asegurar_id`).
    """
    if carpeta_pruebas is None:
        return None
    carpeta = carpeta_proyecto(carpeta_pruebas)
    ruta = _archivo(carpeta_pruebas)
    datos = _del_archivo(ruta)
    validaciones = str(datos.get("validaciones") or "").strip()
    destino = None
    if validaciones:
        destino = Path(validaciones).expanduser()
        destino = destino if destino.is_absolute() else (ruta.parent / destino)
    return {
        "id": str(datos.get("id") or "").strip() or id_de_git(carpeta),
        "nombre": str(datos.get("nombre") or "").strip() or carpeta.name,
        "nombre_indicado": bool(str(datos.get("nombre") or "").strip()),
        "validaciones": str(destino) if destino else None,
        "archivo": str(ruta) if ruta.is_file() else None,
    }


def _escribir(carpeta_pruebas: str | Path, cambios: dict[str, Any]) -> None:
    """Cambia claves de `proyecto:` en aztarna.yaml (lo crea si no existe) conservando sus comentarios."""
    from ruamel.yaml.comments import CommentedMap
    from app.editor_core import roundtrip_yaml
    ruta = _archivo(carpeta_pruebas)
    yaml = roundtrip_yaml()
    datos = None
    if ruta.is_file():
        with ruta.open(encoding="utf-8") as f:
            datos = yaml.load(f)
    if not isinstance(datos, dict):
        datos = CommentedMap()
        datos.yaml_set_start_comment("Configuración del proyecto para Aztarna (ver app/esquema.py y app/proyecto.py).")
    proyecto = datos.get("proyecto")
    if not isinstance(proyecto, dict):
        proyecto = CommentedMap()
        datos.insert(0, "proyecto", proyecto)     # arriba: es lo primero que se busca al abrirlo
    for clave, valor in cambios.items():
        if valor in (None, ""):
            proyecto.pop(clave, None)
        else:
            proyecto[clave] = valor
    if not proyecto:
        datos.pop("proyecto", None)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        yaml.dump(datos, f)
    esquema.configurar(carpeta_pruebas)       # vuelve a leer el archivo (y su copia para proyectos nuevos)


def asegurar_id(carpeta_pruebas: str | Path) -> dict[str, Any]:
    """Como `leer`, pero si el proyecto no tiene identificador (ni en aztarna.yaml ni en Git) le pone uno."""
    info = leer(carpeta_pruebas)
    if info is not None and not info["id"]:
        _escribir(carpeta_pruebas, {"id": uuid.uuid4().hex[:16]})
        info = leer(carpeta_pruebas)
    return info


def configurar(carpeta_pruebas: str | Path, nombre: str | None = None, validaciones: str | None = None) -> dict[str, Any]:
    """Cambia el nombre o la carpeta de validaciones del proyecto ("" los quita)."""
    cambios: dict[str, Any] = {}
    if nombre is not None:
        cambios["nombre"] = " ".join(str(nombre).split())
    if validaciones is not None:
        cambios["validaciones"] = str(validaciones).strip()
    if cambios:
        _escribir(carpeta_pruebas, cambios)
    return leer(carpeta_pruebas)


def para_guardar(info: dict[str, Any] | None) -> dict[str, str] | None:
    """Lo que se guarda en una ejecución o una validación nueva."""
    if not info or not info.get("id"):
        return None
    return {"id": info["id"], "nombre": info["nombre"]}


def de_datos(datos: dict[str, Any]) -> dict[str, str]:
    """El proyecto que dice ser una ejecución o una validación ({} si no lo dice)."""
    p = datos.get("proyecto")
    return {"id": str(p.get("id") or ""), "nombre": str(p.get("nombre") or "")} if isinstance(p, dict) else {}


MISMO, OTRO, DESCONOCIDO = "mismo", "otro", "desconocido"
