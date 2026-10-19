#!/usr/bin/env python3
"""API del asistente de importación (⋯ → Importar…). La lógica está en importacion.py
(y, para un Excel, en importacion_excel.py).

El asistente analiza el Word o el Excel, deja elegir qué es cada familia de tablas (u hoja) y a
qué campo va cada etiqueta, muestra lo que se va a importar (con los IDs que
hay que revisar) y lo escribe en un proyecto nuevo o en el abierto. El mapeo
elegido se recuerda en los ajustes del PC para la próxima importación.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app import ajustes
from app import ejecucion_core as ej
from app import importacion as imp
from app import importacion_excel as ix
from app import importacion_resultados as ir
from app import mapeo_importacion as mi
from app import validacion_core as vc
from app.editor_api import respuesta, to_plain
from app.ejecucion_api import _nombre_carpeta
from app.validacion_api import EditorValidacionApi

AJUSTE_MAPEO = "importacion_mapeo"
AJUSTE_MAPEO_EXCEL = "importacion_mapeo_excel"      # las columnas de un Excel no son etiquetas del Word: aparte
AJUSTE_MAPEO_RESULTADOS = "importacion_resultados_mapeo"
EXTENSIONES = (".docx", ".xlsx", ".xlsm")


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
        if ruta.suffix.lower() not in EXTENSIONES or not ruta.is_file():
            raise ValueError("Elige un documento de Word (.docx) o un Excel (.xlsx) que exista.")
        return ruta

    @respuesta
    def importar_elegir_documento(self) -> dict[str, Any]:
        import webview

        if self._window is None:
            raise ValueError("El selector de archivos solo está disponible en la aplicación.")
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        guardada = ajustes.leer().get("carpeta_importacion")
        inicio = Path(guardada) if isinstance(guardada, str) and Path(guardada).is_dir() else Path.home()
        elegidos = self._window.create_file_dialog(kind, directory=str(inicio), file_types=(
            "Word o Excel (*.docx;*.xlsx;*.xlsm)", "Documentos de Word (*.docx)", "Libros de Excel (*.xlsx;*.xlsm)"))
        if not elegidos:
            return {"cancelado": True}
        archivo = Path(elegidos[0] if isinstance(elegidos, (list, tuple)) else elegidos)
        ajustes.guardar({"carpeta_importacion": str(archivo.parent)})
        return {"archivo": str(archivo)}

    def _pruebas_del_proyecto(self) -> Path:
        """Carpeta de pruebas con la que se enlazan los resultados (la de la validación, si hay una abierta)."""
        if self._validacion is not None and vc.carpeta_pruebas(self._validacion) is not None:
            return vc.carpeta_pruebas(self._validacion)
        if self._ejecucion is not None and ej.carpeta_pruebas(self._ejecucion) is not None:
            return ej.carpeta_pruebas(self._ejecucion)
        if self._abierto() is None:
            raise ValueError("Abre primero la carpeta de pruebas del proyecto: los resultados se enlazan con sus pruebas por el ID.")
        return self._abierto()

    @respuesta
    def importar_analizar(self, archivo: str, tipo: str | None = None) -> dict[str, Any]:
        """Familias de tablas del Word y el mapeo propuesto (con lo elegido la última vez)."""
        if tipo == "resultado" and imp.es_excel(archivo):
            raise ValueError("Los resultados de una ejecución se importan desde un Word. Desde un Excel se importan pruebas o requisitos.")
        if tipo == "resultado":
            self._pruebas_del_proyecto()
            analisis = ir.analizar(self._documento(archivo))
            recordado = ajustes.leer().get(AJUSTE_MAPEO_RESULTADOS)
            return {
                **analisis,
                "mapeo": ir.mapeo_propuesto(analisis, recordado if isinstance(recordado, dict) else None),
                "tipos": [{"valor": t, "texto": v} for t, v in ir.TIPOS_VISIBLES.items()],
                "opciones": {"resultado": [{"valor": k, "texto": v} for k, v in {**ir.DATOS, **ir.ESPECIALES}.items()]},
                "estados": [{"valor": e, "texto": "Sin resultado (pendiente)" if e == ir.SIN_RESULTADO else ej.ESTADOS_VISIBLES[e]}
                            for e in ("ok", "no_ok", "bloqueada", "no_aplica", ir.SIN_RESULTADO)],
                "nombre_propuesto": f"Resultados {Path(archivo).stem}",
            }
        excel = imp.es_excel(archivo)
        origen = "excel" if excel else "word"
        analisis = imp.analizar(self._documento(archivo), tipo if tipo in imp.CLASES else None)
        self._ultimo_analisis = (str(archivo), analisis)       # para guardar el mapeo con los nombres del documento
        recordado = ajustes.leer().get(AJUSTE_MAPEO_EXCEL if excel else AJUSTE_MAPEO)
        abierto = self._abierto()
        # Primero lo del proyecto (importacion.yaml), después lo del PC y, si no, lo propuesto.
        del_proyecto, leido, problemas = mi.leer(abierto, origen)
        return {
            **analisis,
            "origen": origen,
            "mapeo": imp.mapeo_propuesto(analisis, mi.combinar(recordado if isinstance(recordado, dict) else None, del_proyecto)),
            "mapeo_proyecto": {"archivo": str(leido) if leido else None, "problemas": problemas,
                               "destino": str(mi.archivo(abierto)) if abierto else None},
            "tipos": [{"valor": t, "texto": imp.TIPOS_VISIBLES[t]} for t in imp.TIPOS if not (excel and t == "tabla")],
            "opciones": {t: ix.opciones(t) if excel else _opciones(t) for t in imp.CLASES},
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
    def importar_elegir_carpeta(self, nombre: str = "", ejecucion: bool = False) -> dict[str, Any]:
        """Carpeta donde se creará el proyecto nuevo (o la ejecución): una subcarpeta `nombre` de la elegida."""
        padre = self._dialogo_carpeta()
        if padre is None:
            return {"cancelado": True}
        destino = padre / (_nombre_carpeta(nombre) if ejecucion else _nombre_proyecto(nombre))
        if destino.exists() and any(destino.iterdir()):
            raise ValueError(f"Ya existe {destino} y no está vacía. Cambia el nombre del proyecto.")
        return {"carpeta": str(destino)}

    @respuesta
    def importar_ejecutar(self, archivo: str, mapeo: dict[str, Any], modo: str = "nuevo",
                          ids: dict[str, dict[str, str]] | None = None, nombre: str = "",
                          carpeta: str | None = None, acciones: dict[str, dict[str, str]] | None = None,
                          guardar_mapeo: bool = True) -> dict[str, Any]:
        """Importa y abre el resultado. En modo «nuevo», sin `carpeta`, pide dónde crear el proyecto.

        Con `guardar_mapeo`, lo elegido se guarda también en el importacion.yaml del proyecto.
        """
        documento = self._documento(archivo)
        if modo == "anadir":
            self._exigir_escritura()
            if self._sin_guardar:
                raise ValueError("Guarda o descarta los cambios antes de importar.")
            destino = self._abierto()
            if destino is None:
                raise ValueError("No hay ningún proyecto abierto al que añadir.")
            # Se pueden actualizar capítulos que ya existen: ninguno puede estar en manos de otra persona.
            from app import bloqueos
            ocupados = [bloqueos.texto(otro, archivo.name) for carpeta in imp.carpetas_destino(destino, "anadir").values()
                        if carpeta.is_dir() for archivo in sorted(carpeta.glob("*.yaml"))
                        if (otro := self._bloqueos.de_otro(archivo))]
            if ocupados:
                raise ValueError("No se puede importar ahora: " + "; ".join(ocupados) + ".")
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
        self._recordar_mapeo(mapeo, AJUSTE_MAPEO_EXCEL if imp.es_excel(documento) else AJUSTE_MAPEO)
        guardado = None
        if guardar_mapeo:
            ultimo = getattr(self, "_ultimo_analisis", None)
            analisis = ultimo[1] if ultimo and ultimo[0] == str(archivo) else imp.analizar(documento)
            guardado = mi.guardar(imp.carpetas_destino(destino, modo)["prueba"], "excel" if imp.es_excel(documento) else "word",
                                  mapeo, analisis)
        self._ejecucion = None
        self._load(destino)
        self._coleccion = "requisitos" if "prueba" not in resultado["carpetas"] and self._req_chapters else "pruebas"
        return {"resultado": resultado, "carpeta": self._summary(), "proyecto": str(destino),
                "mapeo_guardado": str(guardado) if guardado else None}

    # --- resultados -----------------------------------------------------------
    @respuesta
    def importar_resultados_revisar(self, archivo: str, mapeo: dict[str, Any]) -> dict[str, Any]:
        """Cuántos resultados hay de cada tipo, qué pruebas no están en el proyecto y ejemplos."""
        from app.editor_core import read_chapters
        preparado = ir.preparar(self._documento(archivo), mapeo, read_chapters(self._pruebas_del_proyecto()))
        return to_plain(ir.revision(preparado))

    @respuesta
    def importar_resultados_ejecutar(self, archivo: str, mapeo: dict[str, Any], nombre: str, datos: dict[str, Any],
                                     en_validacion: bool = False, carpeta: str | None = None) -> dict[str, Any]:
        """Crea la ejecución con los resultados del Word y la abre (dentro de la validación abierta si se pide)."""
        documento = self._documento(archivo)
        nombre = str(nombre or "").strip()
        if not nombre:
            raise ValueError("La ejecución necesita un nombre.")
        if en_validacion and self._validacion is not None:
            destino = self._validacion["carpeta"] / _nombre_carpeta(nombre)
        elif carpeta:
            destino = Path(carpeta)
        else:
            raise ValueError("Elige dónde crear la ejecución.")
        if destino.exists():
            raise ValueError(f"Ya existe {destino.name}. Cambia el nombre de la ejecución.")
        r = ir.importar(documento, mapeo, destino, self._pruebas_del_proyecto(), nombre, datos)
        if en_validacion and self._validacion is not None:
            vc.anadir_ejecucion(self._validacion, destino)
        self._recordar_mapeo_resultados(mapeo)
        pruebas = self._pruebas_del_proyecto()
        cambia = self._solo_lectura or self._yaml_dir is None or pruebas.resolve() != self._yaml_dir
        if cambia:                               # p. ej., estaban abiertas las pruebas congeladas de otra ejecución
            self._load(pruebas)
        self._ejecucion = r["ejecucion"]
        estado = {**self._estado(), "carpeta_pruebas": self._summary() if cambia else None}
        return {"ejecucion": estado, "pruebas": r["pruebas"], "con_resultado": r["con_resultado"], "avisos": r["avisos"]}

    @staticmethod
    def _recordar_mapeo_resultados(mapeo: dict[str, Any]) -> None:
        anterior = ajustes.leer().get(AJUSTE_MAPEO_RESULTADOS)
        anterior = anterior if isinstance(anterior, dict) else {}
        ajustes.guardar({AJUSTE_MAPEO_RESULTADOS: {
            "tipos": {**dict(anterior.get("tipos") or {}), **dict(mapeo.get("tipos") or {})},
            "campos": {"resultado": {**dict((anterior.get("campos") or {}).get("resultado") or {}),
                                     **dict((mapeo.get("campos") or {}).get("resultado") or {})}},
            "valores": {**dict(anterior.get("valores") or {}), **dict(mapeo.get("valores") or {})},
        }})

    @respuesta
    def importar_plantilla_excel(self, tipo: str = "prueba", salida: str | None = None) -> dict[str, Any]:
        """Excel vacío con una columna por campo, para rellenar e importar. Sin `salida`, abre «Guardar como»."""
        if tipo not in imp.CLASES:
            raise ValueError(f"Tipo desconocido: {tipo}")
        if salida is None:
            carpeta = self._abierto().parent if self._abierto() is not None else Path.home()
            salida = self._guardar_como(carpeta, f"plantilla_{'pruebas' if tipo == 'prueba' else 'requisitos'}.xlsx", "Libro de Excel (*.xlsx)")
            if salida is None:
                return {"cancelado": True}
        ruta = Path(salida)
        if ruta.suffix.lower() != ".xlsx":
            ruta = ruta.with_suffix(".xlsx")
        return {"archivo": str(ix.plantilla(ruta, tipo))}

    @staticmethod
    def _recordar_mapeo(mapeo: dict[str, Any], clave: str = AJUSTE_MAPEO) -> None:
        """Fusiona el mapeo elegido con el recordado (las etiquetas de otros documentos se conservan)."""
        anterior = ajustes.leer().get(clave)
        anterior = anterior if isinstance(anterior, dict) else {}
        campos = {t: {**dict((anterior.get("campos") or {}).get(t) or {}), **dict((mapeo.get("campos") or {}).get(t) or {})}
                  for t in imp.CLASES}
        ajustes.guardar({clave: {"tipos": {**dict(anterior.get("tipos") or {}), **dict(mapeo.get("tipos") or {})},
                                 "campos": campos}})
