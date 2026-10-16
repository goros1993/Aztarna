#!/usr/bin/env python3
"""API del asistente de importación (⋯ → Importar…). La lógica está en importacion.py.

El asistente analiza el Word, deja elegir qué es cada familia de tablas y a
qué campo va cada etiqueta, muestra lo que se va a importar (con los IDs que
hay que revisar) y lo escribe en un proyecto nuevo o en el abierto. El mapeo
elegido se recuerda en los ajustes del PC para la próxima importación.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app import ajustes
from app import importacion as imp
from app.editor_api import respuesta, to_plain
from app.validacion_api import EditorValidacionApi

AJUSTE_MAPEO = "importacion_mapeo"


def _opciones(tipo: str) -> list[dict[str, str]]:
    """Campos a los que puede ir una etiqueta, para el desplegable."""
    campos = [{"valor": c, "texto": imp.NOMBRES[tipo].get(c, c)} for c in imp.CLASES[tipo]]
    return campos + [{"valor": k, "texto": v} for k, v in imp.ESPECIALES.items()]


def _nombre_proyecto(nombre: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(nombre or "")).strip().replace(" ", "_") or "proyecto"


class EditorImportacionApi(EditorValidacionApi):
    def _abierto(self) -> Path | None:
        return self._yaml_dir if self._yaml_dir is not None and not self._solo_lectura else None

    @staticmethod
    def _documento(archivo: str) -> Path:
        ruta = Path(str(archivo or ""))
        if ruta.suffix.lower() != ".docx" or not ruta.is_file():
            raise ValueError("Elige un documento de Word (.docx) que exista.")
        return ruta

    @respuesta
    def importar_elegir_documento(self) -> dict[str, Any]:
        import webview

        if self._window is None:
            raise ValueError("El selector de archivos solo está disponible en la aplicación.")
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        guardada = ajustes.leer().get("carpeta_importacion")
        inicio = Path(guardada) if isinstance(guardada, str) and Path(guardada).is_dir() else Path.home()
        elegidos = self._window.create_file_dialog(kind, directory=str(inicio), file_types=("Documentos de Word (*.docx)",))
        if not elegidos:
            return {"cancelado": True}
        archivo = Path(elegidos[0] if isinstance(elegidos, (list, tuple)) else elegidos)
        ajustes.guardar({"carpeta_importacion": str(archivo.parent)})
        return {"archivo": str(archivo)}

    @respuesta
    def importar_analizar(self, archivo: str, tipo: str | None = None) -> dict[str, Any]:
        """Familias de tablas del Word y el mapeo propuesto (con lo elegido la última vez)."""
        analisis = imp.analizar(self._documento(archivo), tipo if tipo in imp.CLASES else None)
        recordado = ajustes.leer().get(AJUSTE_MAPEO)
        abierto = self._abierto()
        return {
            **analisis,
            "mapeo": imp.mapeo_propuesto(analisis, recordado if isinstance(recordado, dict) else None),
            "tipos": [{"valor": t, "texto": imp.TIPOS_VISIBLES[t]} for t in imp.TIPOS],
            "opciones": {t: _opciones(t) for t in imp.CLASES},
            "proyecto_abierto": str(abierto) if abierto else None,
            "nombre_propuesto": _nombre_proyecto(Path(archivo).stem),
        }

    @respuesta
    def importar_revisar(self, archivo: str, mapeo: dict[str, Any], modo: str = "nuevo") -> dict[str, Any]:
        """Lo que se importaría con este mapeo: cifras, capítulos, avisos, IDs a revisar, los que ya existen y ejemplos."""
        documento = self._documento(archivo)
        if modo == "anadir":
            if self._abierto() is None:
                raise ValueError("No hay ningún proyecto abierto al que añadir (o está en solo lectura).")
            p = imp.preparar(documento, mapeo, self._abierto(), "anadir")
            return to_plain(imp.revision(p["conversion"], p["existentes"], p["carpetas"], p["imagenes"]))
        return to_plain(imp.revision(imp.convertir_documento_ruta(documento, mapeo)))

    @respuesta
    def importar_elegir_carpeta(self, nombre: str = "") -> dict[str, Any]:
        """Carpeta donde se creará el proyecto nuevo (una subcarpeta `nombre` de la elegida)."""
        padre = self._dialogo_carpeta()
        if padre is None:
            return {"cancelado": True}
        destino = padre / _nombre_proyecto(nombre)
        if destino.exists() and any(destino.iterdir()):
            raise ValueError(f"Ya existe {destino} y no está vacía. Cambia el nombre del proyecto.")
        return {"carpeta": str(destino)}

    @respuesta
    def importar_ejecutar(self, archivo: str, mapeo: dict[str, Any], modo: str = "nuevo",
                          ids: dict[str, dict[str, str]] | None = None, nombre: str = "",
                          carpeta: str | None = None, acciones: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
        """Importa y abre el resultado. En modo «nuevo», sin `carpeta`, pide dónde crear el proyecto."""
        documento = self._documento(archivo)
        if modo == "anadir":
            self._exigir_escritura()
            if self._sin_guardar:
                raise ValueError("Guarda o descarta los cambios antes de importar.")
            destino = self._abierto()
            if destino is None:
                raise ValueError("No hay ningún proyecto abierto al que añadir.")
        else:
            if carpeta is None:
                padre = self._dialogo_carpeta()
                if padre is None:
                    return {"cancelado": True}
                destino = padre / _nombre_proyecto(nombre or documento.stem)
            else:
                destino = Path(carpeta)
            if destino.exists() and any(destino.iterdir()):
                raise ValueError(f"Ya existe {destino} y no está vacía. Cambia el nombre del proyecto.")
        resultado = imp.importar(documento, mapeo, destino, modo, ids=ids, acciones=acciones if modo == "anadir" else None)
        self._recordar_mapeo(mapeo)
        self._campaña = None
        self._load(destino)
        self._coleccion = "requisitos" if "prueba" not in resultado["carpetas"] and self._req_chapters else "pruebas"
        return {"resultado": resultado, "carpeta": self._summary(), "proyecto": str(destino)}

    @staticmethod
    def _recordar_mapeo(mapeo: dict[str, Any]) -> None:
        """Fusiona el mapeo elegido con el recordado (las etiquetas de otros documentos se conservan)."""
        anterior = ajustes.leer().get(AJUSTE_MAPEO)
        anterior = anterior if isinstance(anterior, dict) else {}
        campos = {t: {**dict((anterior.get("campos") or {}).get(t) or {}), **dict((mapeo.get("campos") or {}).get(t) or {})}
                  for t in imp.CLASES}
        ajustes.guardar({AJUSTE_MAPEO: {"tipos": {**dict(anterior.get("tipos") or {}), **dict(mapeo.get("tipos") or {})},
                                        "campos": campos}})
