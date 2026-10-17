#!/usr/bin/env python3
"""Zoom de la ventana del editor (todo más grande o más pequeño).

Se usa el zoom del propio navegador integrado, como el de un navegador web:
agranda texto, botones e imágenes y la página se recoloca sola. Un zoom por CSS
no vale: rompe las medidas que dependen del alto de la ventana (paneles y
listas que ocupan toda la altura).

- Windows (WebView2): `ZoomFactor` del control, desde el hilo de la ventana.
- Linux (WebKitGTK): `set_zoom_level` de la vista, desde el bucle de GTK.

En otras plataformas no se hace nada (devuelve False).
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


def aplicar(ventana: Any, nivel: float) -> bool:
    """Pone el zoom de la ventana de pywebview. True si se ha podido."""
    import webview

    guilib = getattr(webview, "guilib", None)
    if ventana is None or guilib is None:
        return False
    nombre = getattr(guilib, "__name__", "")
    vista = getattr(guilib, "BrowserView", None)
    instancia = vista.instances.get(ventana.uid) if vista is not None else None
    if instancia is None:
        return False
    try:
        if nombre.endswith(".gtk"):
            from gi.repository import GLib

            def _gtk() -> bool:
                instancia.webview.set_zoom_level(nivel)
                return False                      # una sola vez

            GLib.idle_add(_gtk)
            return True
        if nombre.endswith(".winforms"):
            navegador = getattr(instancia, "browser", None)
            control = getattr(navegador, "webview", None)
            if control is None or not hasattr(control, "ZoomFactor"):
                return False                      # no es WebView2 (p. ej. el antiguo de Internet Explorer)

            def _windows() -> None:
                control.ZoomFactor = float(nivel)

            instancia.Invoke(guilib.Func[guilib.Type](_windows))
            return True
    except Exception:  # noqa: BLE001 - sin zoom no se rompe nada
        return False
    return False
