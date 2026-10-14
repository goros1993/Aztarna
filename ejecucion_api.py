#!/usr/bin/env python3
"""API de las campañas de ejecución para la interfaz web.

Amplía `EditorApi`: la misma ventana sirve para editar las pruebas y para
apuntar sus resultados. La lógica está en `ejecucion_core.py`; aquí solo se
adapta a la interfaz (diálogos del sistema, rutas, datos en JSON).
"""
from __future__ import annotations

import base64
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import ejecucion_core as ej
from editor_api import EditorApi, respuesta, to_plain


def _nombre_carpeta(nombre: str) -> str:
    """«Regresión v2.3» -> «2026-11-03_Regresión_v2.3» (válido en Windows y Linux)."""
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nombre).strip().replace(" ", "_")
    return f"{date.today().isoformat()}_{limpio or 'campaña'}"


class EditorEjecucionApi(EditorApi):
    def __init__(self, carpeta_inicial: str | Path | None = None) -> None:
        super().__init__(carpeta_inicial)
        self._campaña: dict[str, Any] | None = None

    # --- utilidades -----------------------------------------------------------
    def _requiere_campaña(self) -> dict[str, Any]:
        if self._campaña is None:
            raise ValueError("No hay ninguna campaña abierta.")
        return self._campaña

    def _estado(self) -> dict[str, Any]:
        campaña = self._requiere_campaña()
        datos = {k: v for k, v in to_plain(campaña["datos"]).items() if k != "pruebas"}
        return {
            "carpeta": str(campaña["carpeta"]),
            "datos": datos,
            "cerrada": datos.get("estado") == "cerrada",
            "resumen": ej.resumen(campaña, self._chapters),
            "estados": ej.ESTADOS_VISIBLES,
        }

    def _dialogo_carpeta(self) -> Path | None:
        import webview

        if self._window is None:
            raise ValueError("El selector de carpetas solo está disponible en la aplicación.")
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        elegida = self._window.create_file_dialog(kind, directory=str(Path.home()))
        return Path(elegida[0]) if elegida else None

    def _prueba(self, test_id: str) -> dict[str, Any] | None:
        encontrada = ej.indice_por_id(self._chapters).get(test_id)
        return encontrada["prueba"] if encontrada else None

    # --- crear y abrir ------------------------------------------------------------
    @respuesta
    def campana_opciones(self) -> dict[str, list[str]]:
        """Valores que existen para cada criterio de selección."""
        self._require_dir()
        return ej.opciones_filtro(self._chapters)

    @respuesta
    def campana_previsualizar(self, filtro: dict[str, Any]) -> list[dict[str, str]]:
        """Pruebas que entrarían en una campaña con este filtro."""
        self._require_dir()
        return [
            {"id": item["id"], "archivo": item["archivo"],
             "titulo": str(item["prueba"].get("titulo") or item["prueba"].get("nombre") or "")}
            for item in ej.seleccionar(self._chapters, filtro or {})
        ]

    @respuesta
    def campana_crear(self, nombre: str, filtro: dict[str, Any], datos: dict[str, Any] | None = None,
                      carpeta: str | None = None) -> dict[str, Any]:
        """Crea la campaña en una subcarpeta nueva dentro de la carpeta elegida."""
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
        self._campaña = ej.crear(destino, pruebas, nombre, filtro or {}, datos or {})
        return self._estado()

    def _abrir(self, carpeta: Path) -> dict[str, Any]:
        """Abre la campaña y su carpeta de pruebas (la congelada, en solo lectura, si está cerrada)."""
        campaña = ej.cargar(carpeta)
        congelada = ej.carpeta_congelada(campaña) if campaña["datos"].get("estado") == "cerrada" else None
        pruebas = congelada or ej.carpeta_pruebas(campaña)
        if pruebas is None:
            # Se movió la carpeta de pruebas (o la campaña viene de otro PC): la interfaz pregunta dónde está.
            return {"faltan_pruebas": True, "carpeta": str(campaña["carpeta"]),
                    "nombre": str(campaña["datos"].get("nombre") or ""),
                    "rutas": [str(campaña["datos"].get(k)) for k in ("pruebas_yaml", "pruebas_yaml_absoluta")
                              if campaña["datos"].get(k)]}
        solo_lectura = congelada is not None
        cambia_carpeta = (self._yaml_dir is None or pruebas.resolve() != self._yaml_dir
                          or self._solo_lectura != solo_lectura)
        if cambia_carpeta:
            self._load(pruebas)
        self._solo_lectura = solo_lectura
        self._campaña = campaña
        return {**self._estado(), "carpeta_pruebas": self._summary() if cambia_carpeta else None}

    @respuesta
    def campana_abrir(self, carpeta: str | None = None) -> dict[str, Any]:
        """Abre una campaña; si sus pruebas están en otra carpeta, abre también esa carpeta."""
        if carpeta is None:
            elegida = self._dialogo_carpeta()
            if elegida is None:
                return {"cancelado": True}
        else:
            elegida = Path(carpeta)
        return self._abrir(elegida)

    @respuesta
    def campana_reubicar(self, carpeta: str, pruebas: str | None = None) -> dict[str, Any]:
        """Indica dónde están ahora las pruebas de una campaña y la abre."""
        campaña = ej.cargar(carpeta)
        if pruebas is None:
            elegida = self._dialogo_carpeta()
            if elegida is None:
                return {"cancelado": True}
        else:
            elegida = Path(pruebas)
        ej.reubicar_pruebas(campaña, elegida)
        return self._abrir(Path(carpeta))

    @respuesta
    def campana_estado(self) -> dict[str, Any] | None:
        return self._estado() if self._campaña is not None else None

    @respuesta
    def campana_soltar(self) -> dict[str, Any]:
        """Deja de trabajar con la campaña abierta (no borra nada)."""
        self._campaña = None
        return {}

    # --- resultados ------------------------------------------------------------------
    @respuesta
    def campana_resultado(self, test_id: str) -> dict[str, Any]:
        campaña = self._requiere_campaña()
        resultado = to_plain(campaña["resultados"].get(test_id) or {"estado": "pendiente"})
        prueba = self._prueba(test_id)
        ejecutada = resultado.get("huella")
        return {
            "resultado": resultado,
            "en_campaña": test_id in ej.ids_de(campaña),
            "prueba_cambiada": bool(prueba is not None and ejecutada and ejecutada != ej.huella(prueba)),
        }

    @respuesta
    def campana_registrar(self, test_id: str, estado: str, observaciones: str = "", incidencia: str = "",
                          evidencias: list[str] | None = None, ejecutor: str = "") -> dict[str, Any]:
        """Guarda el resultado. Con el mismo estado solo se corrigen las notas (sin otro intento)."""
        campaña = self._requiere_campaña()
        actual = ej.estado_de(campaña, test_id)
        if estado == actual and actual != "pendiente":
            ej.editar_notas(campaña, test_id, observaciones=observaciones, incidencia=incidencia,
                            evidencias=list(evidencias or []))
        else:
            prueba = self._prueba(test_id)
            ej.registrar(campaña, test_id, estado, observaciones=observaciones, incidencia=incidencia,
                         evidencias=list(evidencias or []), ejecutor=ejecutor,
                         huella_actual=ej.huella(prueba) if prueba is not None else "")
        return self._estado()

    @respuesta
    def campana_evidencia_base64(self, test_id: str, nombre: str, datos: str) -> dict[str, str]:
        """Guarda una evidencia pegada o soltada en la ventana."""
        campaña = self._requiere_campaña()
        if "," in datos[:100]:
            datos = datos.split(",", 1)[1]
        return {"ruta": ej.guardar_evidencia(campaña, test_id, nombre, base64.b64decode(datos))}

    @respuesta
    def campana_elegir_evidencias(self, test_id: str) -> dict[str, list[str]]:
        """Selector del sistema; copia los archivos elegidos a `evidencias/`."""
        import webview

        campaña = self._requiere_campaña()
        if self._window is None:
            raise ValueError("El selector de archivos solo está disponible en la aplicación.")
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        elegidos = self._window.create_file_dialog(kind, allow_multiple=True)
        rutas = []
        for archivo in elegidos or []:
            ruta = Path(archivo)
            if ruta.stat().st_size > ej.MAX_EVIDENCIA_BYTES:
                raise ValueError(f"{ruta.name} supera los 25 MB.")
            rutas.append(ej.guardar_evidencia(campaña, test_id, ruta.name, ruta.read_bytes()))
        return {"rutas": rutas}

    @respuesta
    def campana_imagen(self, ruta: str, ancho: int = 480) -> dict[str, Any]:
        """Miniatura de una evidencia (si es una imagen)."""
        return self._miniatura(ej.ruta_evidencia(self._requiere_campaña(), ruta), ancho)

    @respuesta
    def campana_abrir_evidencia(self, ruta: str) -> dict[str, Any]:
        """Abre una evidencia con el programa predeterminado del sistema."""
        archivo = ej.ruta_evidencia(self._requiere_campaña(), ruta)
        if not archivo.is_file():
            raise ValueError("No se encuentra el archivo.")
        if sys.platform.startswith("win"):
            import os
            os.startfile(archivo)  # noqa: S606 - archivo local elegido por el usuario
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(archivo)])  # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", str(archivo)])  # noqa: S603,S607
        return {}

    @respuesta
    def campana_cerrar(self) -> dict[str, Any]:
        """Cierra la campaña: congela sus pruebas y pasa a mostrarlas en solo lectura."""
        campaña = self._requiere_campaña()
        if self._solo_lectura:
            raise ValueError("La campaña ya está cerrada.")
        ej.cerrar(campaña, self._chapters)
        return self._abrir(campaña["carpeta"])

    @respuesta
    def campana_pdf_disponible(self) -> str | None:
        import informe_docx

        return informe_docx.pdf_disponible()

    @respuesta
    def campana_informe(self, salida: str | None = None, pdf: bool = False) -> dict[str, Any]:
        """Genera el informe DOCX (y el PDF si se pide). Sin `salida`, abre «Guardar como»."""
        import informe_docx

        campaña = self._requiere_campaña()
        if salida is None:
            import webview

            if self._window is None:
                raise ValueError("«Guardar como» solo está disponible en la aplicación.")
            kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
            elegido = self._window.create_file_dialog(
                kind, directory=str(campaña["carpeta"]), save_filename=f"Informe_{campaña['carpeta'].name}.docx",
                file_types=("Documento de Word (*.docx)",),
            )
            if not elegido:
                return {"cancelado": True}
            salida = elegido if isinstance(elegido, str) else elegido[0]
        datos = informe_docx.generar_informe(campaña, salida, self._chapters)
        resultado = {"archivo": datos["archivo"], "pruebas": datos["pruebas"], "pdf": None, "aviso_pdf": None}
        if pdf:
            try:
                resultado["pdf"] = str(informe_docx.convertir_a_pdf(datos["archivo"]))
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                resultado["aviso_pdf"] = str(error)
        return resultado

    @respuesta
    def campana_resincronizar(self) -> dict[str, Any]:
        cambios = ej.resincronizar(self._requiere_campaña(), self._chapters)
        return {**self._estado(), "cambios": cambios}
