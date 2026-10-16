#!/usr/bin/env python3
"""Bloqueo de capítulos: que dos personas no editen a la vez el mismo capítulo.

Pensado para una carpeta de pruebas en una unidad de red compartida. Quien
empieza a editar un capítulo crea junto a él un archivo de bloqueo
(`.01_capitulo.yaml.lock`) con su nombre, su PC y la hora; los demás lo
abren en solo lectura hasta que lo deja. El bloqueo:

- se renueva cada minuto mientras el editor está abierto;
- caduca si no se renueva en 5 minutos (el editor se cerró mal o el PC se
  apagó), y entonces otro puede tomarlo;
- se suelta al cambiar de capítulo o de carpeta, al cerrar el editor y tras
  15 minutos sin cambios (si no hay nada sin guardar);
- se puede forzar (con confirmación en la interfaz).

El archivo se crea con O_EXCL para que dos editores no lo tomen a la vez. Cada
editor abierto es una «sesión» distinta, aunque sea la misma persona.
"""
from __future__ import annotations

import getpass
import json
import os
import socket
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

CADUCIDAD_S = 300          # sin renovar durante este tiempo, el bloqueo no vale
RENOVAR_S = 60
INACTIVO_S = 900           # sin cambios durante este tiempo, se suelta


def ruta_bloqueo(archivo: Path) -> Path:
    return Path(archivo).with_name(f".{Path(archivo).name}.lock")


def leer(archivo: Path) -> dict[str, Any] | None:
    """Datos del bloqueo de un capítulo, o None si no está bloqueado (o el archivo no se entiende)."""
    try:
        datos = json.loads(ruta_bloqueo(archivo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def caducado(datos: dict[str, Any], ahora: float | None = None) -> bool:
    try:
        renovado = float(datos.get("renovado") or 0)
    except (TypeError, ValueError):
        return True
    return (ahora or time.time()) - renovado > CADUCIDAD_S


def persona_del_sistema() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - sin usuario conocido
        return "alguien"


class Bloqueos:
    """Los bloqueos de una sesión del editor."""

    def __init__(self, persona: Callable[[], str] | None = None, ocupado: Callable[[], bool] | None = None) -> None:
        self.sesion = uuid.uuid4().hex
        self._persona = persona or persona_del_sistema
        self._ocupado = ocupado or (lambda: False)       # hay cambios sin guardar: no soltar por inactividad
        self._mios: dict[Path, float] = {}               # capítulo -> última actividad
        self._lock = threading.RLock()
        self._hilo: threading.Thread | None = None
        self._parar = threading.Event()

    # --- consultar -------------------------------------------------------------
    def de_otro(self, archivo: Path) -> dict[str, Any] | None:
        """Quién tiene el capítulo, si es otra sesión y su bloqueo vale; None si está libre o es mío."""
        datos = leer(archivo)
        if not datos or datos.get("sesion") == self.sesion or caducado(datos):
            return None
        return datos

    def es_mio(self, archivo: Path) -> bool:
        return Path(archivo) in self._mios

    # --- tomar y soltar ---------------------------------------------------------
    def _datos(self, desde: str | None = None) -> dict[str, Any]:
        return {"sesion": self.sesion, "persona": self._persona() or persona_del_sistema(), "equipo": socket.gethostname(),
                "desde": desde or datetime.now().isoformat(timespec="minutes"), "renovado": time.time()}

    def tomar(self, archivo: Path, forzar: bool = False) -> dict[str, Any] | None:
        """Toma el bloqueo del capítulo. Devuelve None si lo tiene esta sesión o los datos de quien lo tiene."""
        archivo = Path(archivo)
        with self._lock:
            otro = self.de_otro(archivo)
            if otro and not forzar:
                self._mios.pop(archivo, None)
                return otro
            if archivo in self._mios and not otro:
                self._mios[archivo] = time.time()
                return None
            ruta = ruta_bloqueo(archivo)
            if ruta.exists():
                try:
                    ruta.unlink()                         # caducado, de una sesión anterior o forzado
                except OSError:
                    pass
            try:
                fd = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:                       # otro editor lo ha tomado justo ahora
                return leer(archivo) or {"persona": "otra persona", "equipo": "", "desde": ""}
            except OSError:
                return None                               # sin permiso para crear el archivo: no se bloquea
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._datos(), f, ensure_ascii=False)
            self._mios[archivo] = time.time()
            self._arrancar()
            return None

    def soltar(self, archivo: Path) -> None:
        archivo = Path(archivo)
        with self._lock:
            if self._mios.pop(archivo, None) is None:
                return
            datos = leer(archivo)
            if datos and datos.get("sesion") == self.sesion:
                try:
                    ruta_bloqueo(archivo).unlink()
                except OSError:
                    pass

    def soltar_todos(self) -> None:
        with self._lock:
            for archivo in list(self._mios):
                self.soltar(archivo)

    # --- mantener ---------------------------------------------------------------
    def renovar(self) -> list[Path]:
        """Renueva los bloqueos de esta sesión y suelta los inactivos. Devuelve los que se han perdido (forzados)."""
        perdidos = []
        ahora = time.time()
        with self._lock:
            for archivo, actividad in list(self._mios.items()):
                datos = leer(archivo)
                if not datos or datos.get("sesion") != self.sesion:
                    self._mios.pop(archivo, None)         # alguien lo forzó (o se borró a mano)
                    perdidos.append(archivo)
                    continue
                if ahora - actividad > INACTIVO_S and not self._ocupado():
                    self.soltar(archivo)
                    continue
                try:
                    ruta_bloqueo(archivo).write_text(json.dumps({**datos, "renovado": ahora}, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
        return perdidos

    def _arrancar(self) -> None:
        if self._hilo is not None and self._hilo.is_alive():
            return

        def bucle() -> None:
            while not self._parar.wait(RENOVAR_S):
                self.renovar()

        self._hilo = threading.Thread(target=bucle, name="bloqueos", daemon=True)
        self._hilo.start()

    def cerrar(self) -> None:
        self._parar.set()
        self.soltar_todos()


def texto(datos: dict[str, Any], capitulo: str = "") -> str:
    """«Ana (PC-23) está editando «Llamadas» desde las 10:05»."""
    quien = str(datos.get("persona") or "Otra persona")
    equipo = f" ({datos['equipo']})" if datos.get("equipo") else ""
    desde = str(datos.get("desde") or "")
    hora = desde[11:16] if len(desde) >= 16 else desde
    cuando = f" desde las {hora}" if hora else ""
    if desde[:10] and desde[:10] != datetime.now().date().isoformat():
        cuando = f" desde el {desde[8:10]}/{desde[5:7]} a las {hora}"
    que = f"«{capitulo}»" if capitulo else "este capítulo"
    return f"{quien}{equipo} está editando {que}{cuando}"
