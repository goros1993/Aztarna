#!/usr/bin/env python3
"""Zoom de la ventana del editor (todo más grande o más pequeño).

Se usa el zoom del propio navegador integrado, como el de un navegador web:
agranda texto, botones e imágenes y la página se recoloca sola. Un zoom por CSS
no vale: rompe las medidas que dependen del alto de la ventana (paneles y
listas que ocupan toda la altura).

- Windows (WebView2): `ZoomFactor` del control, pedido al hilo de la ventana
  sin esperar (BeginInvoke): esperar a ese hilo desde la llamada de la página
  puede bloquearse.
- Linux (WebKitGTK): `set_zoom_level` de la vista, desde el bucle de GTK.

Si no se puede, devuelve el motivo; la página deja entonces que el navegador
haga su propio zoom con Ctrl+rueda (en Windows, WebView2 lo trae).
"""
from __future__ import annotations

from typing import Any

MINIMO, MAXIMO = 0.5, 3.0


def limitar(nivel: Any) -> float:
    try:
        valor = float(nivel)
    except (TypeError, ValueError):
        return 1.0
    return round(min(max(valor, MINIMO), MAXIMO), 2)


def _formulario(ventana: Any, guilib: Any) -> Any:
    """La ventana nativa: `window.native` (pywebview ≥ 5) o la de la lista del módulo de la plataforma."""
    nativa = getattr(ventana, "native", None)
    if nativa is not None:
        return nativa
    vista = getattr(guilib, "BrowserView", None)
    return vista.instances.get(ventana.uid) if vista is not None else None


def aplicar(ventana: Any, nivel: float) -> tuple[bool, str]:
    """Pone el zoom de la ventana de pywebview. Devuelve (hecho, motivo si no se ha podido)."""
    import webview

    guilib = getattr(webview, "guilib", None)
    if ventana is None or guilib is None:
        return False, "sin ventana"
    nombre = getattr(guilib, "__name__", "")
    try:
        if nombre.endswith(".gtk"):
            from gi.repository import GLib
            vista = getattr(guilib, "BrowserView", None)
            instancia = vista.instances.get(ventana.uid) if vista is not None else None
            if instancia is None:
                return False, "no se encuentra la vista de GTK"

            def _gtk() -> bool:
                instancia.webview.set_zoom_level(nivel)
                return False                      # una sola vez

            GLib.idle_add(_gtk)
            return True, ""
        if nombre.endswith(".winforms"):
            formulario = _formulario(ventana, guilib)
            navegador = getattr(formulario, "browser", None)
            control = getattr(navegador, "webview", None)
            if control is None:
                return False, f"no se encuentra el control del navegador ({type(navegador).__name__})"

            def _windows() -> None:
                control.ZoomFactor = float(nivel)

            from System import Action
            if getattr(formulario, "InvokeRequired", False):
                formulario.BeginInvoke(Action(_windows))
            else:
                _windows()
            return True, ""
        return False, f"plataforma sin zoom ({nombre or 'desconocida'})"
    except Exception as error:  # noqa: BLE001 - sin zoom no se rompe nada
        return False, f"{type(error).__name__}: {error}"
