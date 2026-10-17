#!/usr/bin/env python3
"""API de la validación de una versión para la interfaz web (ver validacion_core.py).

Amplía la de las ejecuciones: una validación agrupa varias ejecuciones y da el
resultado consolidado por prueba y entorno. Se puede trabajar con una
ejecución dentro de la validación o con una ejecución suelta, como antes.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from app import ejecucion_core as ej
from app import validacion_core as vc
from app.editor_api import respuesta, to_plain
from app.ejecucion_api import EditorEjecucionApi, _nombre_carpeta


class EditorValidacionApi(EditorEjecucionApi):
    def __init__(self, carpeta_inicial: str | Path | None = None) -> None:
        super().__init__(carpeta_inicial)
        self._validacion: dict[str, Any] | None = None

    def _estado(self) -> dict[str, Any]:
        """Estado de la ejecución abierta y si forma parte de la validación abierta (None si no hay validación)."""
        estado = super()._estado()
        if self._validacion is not None:
            carpeta = Path(estado["carpeta"]).resolve()
            estado["en_validacion"] = any(ruta is not None and ruta.resolve() == carpeta
                                          for _e, ruta in vc.rutas_ejecuciones(self._validacion))
        else:
            estado["en_validacion"] = None
        return estado

    def _requiere_validacion(self) -> dict[str, Any]:
        if self._validacion is None:
            raise ValueError("No hay ninguna validación abierta.")
        return self._validacion

    def _estado_validacion(self) -> dict[str, Any]:
        validacion = self._requiere_validacion()
        pruebas = vc.carpeta_pruebas(validacion)
        mismas = pruebas is not None and self._yaml_dir is not None and pruebas.resolve() == self._yaml_dir \
            and not self._solo_lectura
        return to_plain(vc.consolidar(validacion, self._chapters if mismas else None))

    def _abrir_validacion(self, carpeta: Path) -> dict[str, Any]:
        validacion = vc.cargar(carpeta)
        pruebas = vc.carpeta_pruebas(validacion)
        if pruebas is None:
            raise ValueError("No se encuentra la carpeta de pruebas de la validación "
                             f"({validacion['datos'].get('pruebas_yaml')}).")
        cambia = self._yaml_dir is None or pruebas.resolve() != self._yaml_dir or self._solo_lectura
        if cambia:
            self._ejecucion = None           # la ejecución abierta era de otra carpeta de pruebas
            self._load(pruebas)
        self._validacion = validacion
        return {**self._estado_validacion(), "carpeta_pruebas": self._summary() if cambia else None}

    # --- abrir, crear, cambiar ---------------------------------------------
    @respuesta
    def validacion_estado(self) -> dict[str, Any] | None:
        """Resultado consolidado de la validación abierta (o None)."""
        return self._estado_validacion() if self._validacion is not None else None

    @respuesta
    def validacion_abrir(self, carpeta: str | None = None) -> dict[str, Any]:
        if carpeta is None:
            elegida = self._dialogo_carpeta()
            if elegida is None:
                return {"cancelado": True}
        else:
            elegida = Path(carpeta)
        return self._abrir_validacion(elegida)

    @respuesta
    def validacion_crear(self, nombre: str, version: str = "", filtro: dict[str, Any] | None = None,
                         carpeta: str | None = None) -> dict[str, Any]:
        """Crea la validación en una subcarpeta nueva de la carpeta elegida."""
        pruebas = self._require_dir()
        if carpeta is None:
            padre = self._dialogo_carpeta()
            if padre is None:
                return {"cancelado": True}
            destino = padre / _nombre_carpeta(str(nombre or ""))
            if destino.exists():
                raise ValueError(f"Ya existe {destino}. Elige otra carpeta o cambia el nombre.")
        else:
            destino = Path(carpeta)
        self._validacion = vc.crear(destino, pruebas, nombre, version, filtro or {})
        self._ejecucion = None
        return self._estado_validacion()

    @respuesta
    def validacion_soltar(self) -> dict[str, Any]:
        """Deja de trabajar con la validación (no borra nada)."""
        self._validacion = None
        return {}

    @respuesta
    def validacion_editar(self, cambios: dict[str, Any]) -> dict[str, Any]:
        vc.editar(self._requiere_validacion(), cambios or {})
        return self._estado_validacion()

    @respuesta
    def ejecucion_soltar(self) -> dict[str, Any]:
        """Deja la ejecución abierta. Con una validación abierta vuelve a su carpeta de pruebas
        (una ejecución cerrada muestra sus pruebas congeladas, en solo lectura)."""
        self._ejecucion = None
        if self._validacion is None:
            return {}
        pruebas = vc.carpeta_pruebas(self._validacion)
        if pruebas is not None and (self._solo_lectura or self._yaml_dir is None or pruebas.resolve() != self._yaml_dir):
            self._load(pruebas)
            return {"carpeta_pruebas": self._summary()}
        return {}

    # --- resultados en CSV para Excel -------------------------------------------
    @respuesta
    def validacion_exportar_csv(self, salida: str | None = None) -> dict[str, Any]:
        from app import exportar_resultados
        validacion = self._requiere_validacion()
        if salida is None:
            salida = self._guardar_como(validacion["carpeta"], f"resultados_{validacion['carpeta'].name}.csv", "CSV para Excel (*.csv)")
            if salida is None:
                return {"cancelado": True}
        return {"archivo": str(exportar_resultados.csv_validacion(self._estado_validacion(), salida))}

    @respuesta
    def ejecucion_exportar_csv(self, salida: str | None = None) -> dict[str, Any]:
        from app import exportar_resultados
        ejecucion = self._requiere_ejecucion()
        if salida is None:
            salida = self._guardar_como(ejecucion["carpeta"], f"resultados_{Path(ejecucion['carpeta']).name}.csv", "CSV para Excel (*.csv)")
            if salida is None:
                return {"cancelado": True}
        return {"archivo": str(exportar_resultados.csv_ejecucion(ejecucion, ej.capitulos_de(ejecucion), salida))}

    # --- informe ---------------------------------------------------------------
    @respuesta
    def validacion_elegir_destino_informe(self) -> dict[str, Any]:
        validacion = self._requiere_validacion()
        archivo = self._guardar_como(validacion["carpeta"], f"Informe_{validacion['carpeta'].name}.docx")
        return {"archivo": archivo} if archivo else {"cancelado": True}

    @respuesta
    def validacion_informe(self, salida: str | None = None, pdf: bool = False, detalle: bool = True) -> dict[str, Any]:
        """Informe DOCX de la validación (y el PDF si se pide). Sin `salida`, abre «Guardar como».

        Sin `detalle`, solo el resumen (con la tabla por capítulos)."""
        from app import informe_docx, informe_validacion

        validacion = self._requiere_validacion()
        if salida is None:
            salida = self._guardar_como(validacion["carpeta"], f"Informe_{validacion['carpeta'].name}.docx")
            if salida is None:
                return {"cancelado": True}
        datos = informe_validacion.generar_informe(validacion, salida, detalle=detalle)
        resultado = {"archivo": datos["archivo"], "pruebas": datos["pruebas"], "pdf": None, "aviso_pdf": None}
        if pdf:
            try:
                resultado["pdf"] = str(informe_docx.convertir_a_pdf(datos["archivo"]))
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                resultado["aviso_pdf"] = f"No se pudo generar el PDF: {error}"
        return resultado

    # --- comparar con la anterior ----------------------------------------------
    @respuesta
    def validacion_comparar_con(self, carpeta: str | None = None) -> dict[str, Any]:
        """Elige la validación con la que se compara esta (normalmente, la de la versión anterior)."""
        validacion = self._requiere_validacion()
        if carpeta is None:
            elegida = self._dialogo_carpeta()
            if elegida is None:
                return {"cancelado": True}
        else:
            elegida = Path(carpeta)
        vc.comparar_con(validacion, elegida)
        return self._estado_validacion()

    @respuesta
    def validacion_quitar_comparacion(self) -> dict[str, Any]:
        vc.comparar_con(self._requiere_validacion(), None)
        return self._estado_validacion()

    @respuesta
    def ejecucion_comparar(self, carpeta: str | None = None) -> dict[str, Any]:
        """Compara la ejecución abierta con otra (la elegida es la anterior)."""
        from app import comparar
        ejecucion = self._requiere_ejecucion()
        if carpeta is None:
            elegida = self._dialogo_carpeta()
            if elegida is None:
                return {"cancelado": True}
        else:
            elegida = Path(carpeta)
        if not ej.es_ejecucion(elegida):
            raise ValueError("Esa carpeta no contiene una ejecución.")
        return to_plain(comparar.comparar_carpetas(elegida, ejecucion["carpeta"]))

    # --- sus ejecuciones -----------------------------------------------------
    @respuesta
    def validacion_anadir_ejecucion(self, carpeta: str | None = None) -> dict[str, Any]:
        """Añade a la validación una ejecución que ya existe, o todas las que haya dentro de la carpeta elegida."""
        validacion = self._requiere_validacion()
        if carpeta is None:
            elegida = self._dialogo_carpeta()
            if elegida is None:
                return {"cancelado": True}
        else:
            elegida = Path(carpeta)
        cambios = vc.anadir_ejecuciones(validacion, elegida)
        return {**self._estado_validacion(), **cambios,
                "ejecucion": self._estado() if self._ejecucion is not None else None}

    @respuesta
    def validacion_quitar_ejecucion(self, indice: int) -> dict[str, Any]:
        """Quita una ejecución de la validación (la ejecución no se borra)."""
        validacion = self._requiere_validacion()
        quitada = dict(vc.rutas_ejecuciones(validacion)[indice][0]) if 0 <= indice < len(validacion["datos"]["ejecuciones"]) else None
        vc.quitar_ejecucion(validacion, indice)
        if quitada and self._ejecucion is not None and \
                str(Path(str(quitada.get("ruta_absoluta") or "")).resolve()) == str(Path(self._ejecucion["carpeta"]).resolve()):
            self._ejecucion = None
        return self._estado_validacion()

    @respuesta
    def validacion_nueva_ejecucion(self, nombre: str, filtro: dict[str, Any], datos: dict[str, Any] | None = None) -> dict[str, Any]:
        """Crea una ejecución dentro de la carpeta de la validación, la añade a ella y la abre."""
        validacion = self._requiere_validacion()
        destino = validacion["carpeta"] / _nombre_carpeta(str(nombre or ""))
        if destino.exists():
            raise ValueError(f"Ya existe {destino.name} en la validación. Cambia el nombre.")
        self._ejecucion = ej.crear(destino, self._require_dir(), nombre, filtro or {}, datos or {}, self._ids_robot(filtro))
        vc.anadir_ejecucion(validacion, destino)
        return self._estado()
