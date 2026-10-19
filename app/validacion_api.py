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
from app import proyecto
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
        estado = to_plain(vc.consolidar(validacion, self._chapters if mismas else None))
        estado["relacion"] = self._relacion(validacion["datos"], pruebas)
        estado["proyecto"] = proyecto.de_datos(validacion["datos"])
        return estado

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
    def validacion_abrir(self, carpeta: str | None = None, confirmar_otro: bool = False) -> dict[str, Any]:
        """Abre la validación (y sus pruebas). Si es de otro proyecto, sin `confirmar_otro` no la abre:
        devuelve `otro_proyecto` para que la interfaz pregunte."""
        if carpeta is None:
            elegida = self._dialogo_carpeta(self._carpeta_validaciones())
            if elegida is None:
                return {"cancelado": True}
        else:
            elegida = Path(carpeta)
        validacion = vc.cargar(elegida)
        suyas = vc.carpeta_pruebas(validacion)
        relacion = self._relacion(validacion["datos"], suyas)
        if relacion == proyecto.OTRO and not confirmar_otro and self._yaml_dir is not None:
            return self._otro_proyecto("validacion", elegida, validacion["datos"], suyas)
        if relacion == proyecto.MISMO:
            self._apuntar_proyecto(validacion, vc.guardar)
        return self._abrir_validacion(elegida)

    # --- portada del modo Validación y proyecto ---------------------------------------
    @respuesta
    def validacion_portada(self, validaciones: list[str] | None = None, ejecuciones: list[str] | None = None) -> dict[str, Any]:
        """El proyecto abierto y, de cada validación y ejecución (las recientes y las de la carpeta de
        validaciones del proyecto), si es de este proyecto. Lo que no existe ya se omite."""
        abierto = self._proyecto_abierto()
        recientes_v = [str(c) for c in (validaciones or [])]
        candidatas = [Path(c) for c in recientes_v]
        en_carpeta: set[str] = set()
        carpeta = self._carpeta_validaciones()
        if carpeta is not None:
            for c in vc.buscar_validaciones(carpeta):
                en_carpeta.add(str(c.resolve()))
                candidatas.append(c)
        lista_v, vistas = [], set()
        for c in candidatas:
            clave = str(c.resolve()) if c.exists() else str(c)
            if clave in vistas:
                continue
            vistas.add(clave)
            try:
                v = vc.cargar(c)
            except (OSError, ValueError):
                continue
            lista_v.append({"carpeta": str(c), "nombre": str(v["datos"].get("nombre") or c.name),
                            "version": str(v["datos"].get("version") or ""), "relacion": self._relacion(v["datos"], vc.carpeta_pruebas(v)),
                            "proyecto": proyecto.de_datos(v["datos"]).get("nombre", ""), "reciente": str(c) in recientes_v,
                            "en_carpeta": clave in en_carpeta})
        lista_e = []
        for c in [Path(x) for x in (ejecuciones or [])]:
            try:
                e = ej.cargar(c)
            except (OSError, ValueError):
                continue
            suyas = ej.carpeta_pruebas(e) or self._pruebas_en_este_pc(e)
            lista_e.append({"carpeta": str(c), "nombre": str(e["datos"].get("nombre") or c.name),
                            "cerrada": e["datos"].get("estado") == "cerrada",
                            "relacion": self._relacion(e["datos"], suyas, ej.ids_de(e)),
                            "proyecto": proyecto.de_datos(e["datos"]).get("nombre", "")})
        return {"proyecto": abierto, "validaciones": lista_v, "ejecuciones": lista_e}

    @respuesta
    def proyecto_configurar(self, nombre: str | None = None, validaciones: str | None = None,
                            elegir_validaciones: bool = False) -> dict[str, Any]:
        """Cambia el nombre del proyecto o su carpeta de validaciones (en su aztarna.yaml)."""
        if self._yaml_dir is None or self._solo_lectura:
            raise ValueError("Abre la carpeta de pruebas del proyecto (no unas pruebas congeladas) para cambiarlo.")
        self._exigir_escritura()
        if elegir_validaciones:
            elegida = self._dialogo_carpeta(self._carpeta_validaciones())
            if elegida is None:
                return {"cancelado": True}
            validaciones = str(elegida)
        self._proyecto = proyecto.configurar(self._yaml_dir, nombre, validaciones)
        return {"proyecto": self._proyecto_abierto(), "carpeta": self._summary()}

    @respuesta
    def validacion_crear(self, nombre: str, version: str = "", filtro: dict[str, Any] | None = None,
                         carpeta: str | None = None) -> dict[str, Any]:
        """Crea la validación en una subcarpeta nueva de la carpeta elegida."""
        pruebas = self._require_dir()
        if carpeta is None:
            padre = self._dialogo_carpeta(self._carpeta_validaciones())
            if padre is None:
                return {"cancelado": True}
            destino = padre / _nombre_carpeta(str(nombre or ""))
            if destino.exists():
                raise ValueError(f"Ya existe {destino}. Elige otra carpeta o cambia el nombre.")
        else:
            destino = Path(carpeta)
        self._validacion = vc.crear(destino, pruebas, nombre, version, filtro or {}, proyecto=self._proyecto_para_crear())
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
        self._ejecucion = ej.crear(destino, self._require_dir(), nombre, filtro or {}, datos or {}, self._ids_robot(filtro),
                                   proyecto=self._proyecto_para_crear())
        vc.anadir_ejecucion(validacion, destino)
        return self._estado()
