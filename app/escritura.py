"""Escritura de archivos que aguanta un apagón (un pantallazo azul, un corte de luz).

Escribir en un temporal y renombrarlo protege de un fallo del programa a mitad,
pero no de un apagón: el sistema puede apuntar el renombrado en disco antes que
los datos, y al reiniciar el archivo aparece lleno de ceros o vacío. Por eso:

- `escribir_texto` vuelca el temporal al disco (`fsync`) antes de renombrarlo y,
  si se pide, guarda antes la versión que había como `<archivo>.anterior`.
- `danado` dice si un archivo tiene pinta de haberse quedado a medias (vacío o
  con bytes nulos), y `recuperar` lo aparta como `<archivo>.dañado-<fecha>` y
  pone en su sitio la copia `.anterior`.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

SUFIJO_ANTERIOR = ".anterior"


def ruta_anterior(ruta: Path) -> Path:
    return ruta.with_name(ruta.name + SUFIJO_ANTERIOR)


def _sincronizar_carpeta(carpeta: Path) -> None:
    """En Linux/macOS el renombrado queda en disco al sincronizar la carpeta (en Windows no se puede ni hace falta)."""
    if os.name == "nt":
        return
    try:
        fd = os.open(carpeta, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _escribir_bytes(ruta: Path, contenido: bytes) -> None:
    """Escritura atómica y volcada al disco: o queda el archivo viejo o el nuevo entero."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(contenido)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise
    _sincronizar_carpeta(ruta.parent)


def danado(contenido: bytes) -> bool:
    """Vacío o con bytes nulos: lo que deja un apagón a mitad de escribir (un YAML de texto nunca los tiene)."""
    return not contenido.strip() or b"\0" in contenido


def escribir_texto(ruta: str | Path, texto: str, conservar_anterior: bool = False) -> None:
    """Guarda `texto` (UTF-8). Con `conservar_anterior`, antes copia lo que había a `<archivo>.anterior`."""
    ruta = Path(ruta)
    nuevo = texto.encode("utf-8")
    if conservar_anterior and ruta.is_file():
        try:
            actual = ruta.read_bytes()
        except OSError:
            actual = b""
        # Solo una versión sana, y solo si cambia: un guardado sin cambios no se come la copia buena.
        if actual != nuevo and not danado(actual):
            _escribir_bytes(ruta_anterior(ruta), actual)
    _escribir_bytes(ruta, nuevo)


def recuperar(ruta: str | Path) -> Path:
    """Aparta el archivo dañado como `<archivo>.dañado-<fecha>` y pone en su sitio la copia `.anterior`.

    Devuelve dónde ha quedado el dañado (para decírselo al usuario).
    """
    ruta = Path(ruta)
    apartado = ruta.with_name(f"{ruta.name}.dañado-{datetime.now():%Y%m%d-%H%M%S}")
    _escribir_bytes(apartado, ruta.read_bytes())
    _escribir_bytes(ruta, ruta_anterior(ruta).read_bytes())
    return apartado


def temporales_sueltos(ruta: str | Path) -> list[Path]:
    """Temporales que dejó un guardado interrumpido (pueden tener la última versión)."""
    ruta = Path(ruta)
    return sorted(p for p in ruta.parent.glob(f"*{ruta.name}*.tmp") if p.is_file())
