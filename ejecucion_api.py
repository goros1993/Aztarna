#!/usr/bin/env python3
"""API de las campañas de ejecución para la interfaz web.

Amplía `EditorApi`: la misma ventana sirve para editar las pruebas y para
apuntar sus resultados. La lógica está en `ejecucion_core.py`; aquí solo se
adapta a la interfaz (diálogos del sistema, rutas, datos en JSON).
"""
from __future__ import annotations

import base64
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import ajustes
import ejecucion_core as ej
import robot_core
from editor_api import EditorApi, respuesta, to_plain


def _nombre_carpeta(nombre: str) -> str:
    """«Regresión v2.3» -> «2026-11-03_Regresión_v2.3» (válido en Windows y Linux)."""
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nombre).strip().replace(" ", "_")
    return f"{date.today().isoformat()}_{limpio or 'campaña'}"


class EditorEjecucionApi(EditorApi):
    def __init__(self, carpeta_inicial: str | Path | None = None) -> None:
        super().__init__(carpeta_inicial)
        self._campaña: dict[str, Any] | None = None
        self._robot: dict[str, Any] | None = None       # ejecución de Robot en curso (o la última)

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
        opciones = ej.opciones_filtro(self._chapters)
        if self._robot_config().get("suites"):
            opciones["robot"] = ["con", "sin"]
        return opciones

    @respuesta
    def campana_previsualizar(self, filtro: dict[str, Any]) -> list[dict[str, str]]:
        """Pruebas que entrarían en una campaña con este filtro."""
        self._require_dir()
        return [
            {"id": item["id"], "archivo": item["archivo"],
             "titulo": str(item["prueba"].get("titulo") or item["prueba"].get("nombre") or "")}
            for item in ej.seleccionar(self._chapters, filtro or {}, self._ids_robot(filtro))
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
        self._campaña = ej.crear(destino, pruebas, nombre, filtro or {}, datos or {}, self._ids_robot(filtro))
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
    def campana_elegir_destino_informe(self) -> dict[str, Any]:
        """«Guardar como» para el informe; la interfaz muestra la espera solo mientras se genera."""
        campaña = self._requiere_campaña()
        archivo = self._guardar_como(campaña["carpeta"], f"Informe_{campaña['carpeta'].name}.docx")
        return {"archivo": archivo} if archivo else {"cancelado": True}

    @respuesta
    def campana_informe(self, salida: str | None = None, pdf: bool = False) -> dict[str, Any]:
        """Genera el informe DOCX (y el PDF si se pide). Sin `salida`, abre «Guardar como»."""
        import informe_docx

        campaña = self._requiere_campaña()
        if salida is None:
            salida = self._guardar_como(campaña["carpeta"], f"Informe_{campaña['carpeta'].name}.docx")
            if salida is None:
                return {"cancelado": True}
        datos = informe_docx.generar_informe(campaña, salida, self._chapters)
        resultado = {"archivo": datos["archivo"], "pruebas": datos["pruebas"], "pdf": None, "aviso_pdf": None}
        if pdf:
            try:
                resultado["pdf"] = str(informe_docx.convertir_a_pdf(datos["archivo"]))
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                resultado["aviso_pdf"] = str(error)
        return resultado

    # --- Robot Framework ---------------------------------------------------------------
    @respuesta
    def campana_robot_elegir(self) -> dict[str, Any]:
        """Selector del sistema para elegir el output.xml de Robot Framework."""
        import webview

        campaña = self._requiere_campaña()
        if self._window is None:
            raise ValueError("El selector de archivos solo está disponible en la aplicación.")
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        elegido = self._window.create_file_dialog(
            kind, directory=str(campaña["carpeta"].parent),
            file_types=("Resultados de Robot Framework (*.xml)", "Todos los archivos (*.*)"),
        )
        if not elegido:
            return {"cancelado": True}
        return {"ruta": elegido if isinstance(elegido, str) else elegido[0]}

    @respuesta
    def campana_robot_previsualizar(self, ruta: str) -> dict[str, Any]:
        """Qué haría la importación del output.xml, sin cambiar nada."""
        import robot_core

        return robot_core.plan(self._requiere_campaña(), robot_core.leer_output(ruta), self._chapters)

    @respuesta
    def campana_robot_importar(self, ruta: str) -> dict[str, Any]:
        """Apunta en la campaña los resultados del output.xml."""
        import robot_core

        datos = robot_core.importar(self._requiere_campaña(), ruta, self._chapters)
        return {**self._estado(), "importacion": datos}

    @respuesta
    def campana_resincronizar(self) -> dict[str, Any]:
        campaña = self._requiere_campaña()
        cambios = ej.resincronizar(campaña, self._chapters, self._ids_robot(campaña["datos"].get("seleccion")))
        return {**self._estado(), "cambios": cambios}

    # --- Robot Framework: configuración y cobertura ---------------------------------
    def _robot_config(self) -> dict[str, str]:
        """Configuración de Robot para la carpeta de pruebas abierta (es de cada PC)."""
        if self._yaml_dir is None:
            return {}
        valor = (ajustes.leer().get("robot") or {}).get(str(self._yaml_dir)) or {}
        return {k: str(v) for k, v in valor.items() if isinstance(v, str)}

    def _robot_suites(self) -> Path | None:
        suites = self._robot_config().get("suites")
        return Path(suites).expanduser() if suites else None

    def _cobertura(self) -> dict[str, Any] | None:
        suites = self._robot_suites()
        if suites is None or not suites.exists():
            return None
        return robot_core.cobertura(self._chapters, robot_core.escanear_suites(suites))

    def _keywords(self) -> dict[str, Any] | None:
        """Keywords de Robot de la carpeta de suites y de las carpetas de keywords configuradas."""
        config = self._robot_config()
        carpetas = [c.strip() for c in re.split(r"[;\n]", config.get("keywords", "")) if c.strip()]
        if config.get("suites"):
            carpetas.insert(0, config["suites"])
        if not carpetas:
            return None
        return robot_core.escanear_keywords([Path(c).expanduser() for c in carpetas])

    def _ids_robot(self, filtro: Any) -> set[str] | None:
        """IDs con test de Robot, solo si el filtro lo necesita."""
        if not isinstance(filtro, dict) or not filtro.get("robot"):
            return None
        cobertura = self._cobertura()
        if cobertura is None:
            raise ValueError("Para filtrar por test de Robot, configura antes la carpeta de tests de Robot.")
        return set(cobertura["por_id"])

    @staticmethod
    def _comando_por_defecto() -> str:
        if shutil.which("robot"):
            return "robot"
        return "python -m robot" if not sys.platform.startswith("win") else "py -m robot"

    @staticmethod
    def _partir_comando(comando: str) -> list[str]:
        partes = shlex.split(comando, posix=not sys.platform.startswith("win"))
        return [p.strip('"') for p in partes if p.strip('"')]

    @respuesta
    def robot_config(self) -> dict[str, Any]:
        self._require_dir()
        return {"config": self._robot_config(), "comando_defecto": self._comando_por_defecto()}

    @respuesta
    def robot_guardar_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Guarda la configuración de Robot de esta carpeta de pruebas y devuelve la cobertura."""
        base = self._require_dir()
        limpia = {k: str(config.get(k) or "").strip() for k in ("suites", "comando", "argumentos", "keywords")}
        if limpia["suites"] and not Path(limpia["suites"]).expanduser().exists():
            raise ValueError(f"No existe la carpeta de tests de Robot: {limpia['suites']}")
        for carpeta in re.split(r"[;\n]", limpia["keywords"]):
            if carpeta.strip() and not Path(carpeta.strip()).expanduser().exists():
                raise ValueError(f"No existe la carpeta de keywords: {carpeta.strip()}")
        todas = dict(ajustes.leer().get("robot") or {})
        if any(limpia.values()):
            todas[str(base)] = {k: v for k, v in limpia.items() if v}
        else:
            todas.pop(str(base), None)
        ajustes.guardar({"robot": todas})
        return {"cobertura": self._cobertura(), "keywords": self._keywords()}

    @respuesta
    def robot_elegir_carpeta(self) -> dict[str, Any]:
        carpeta = self._dialogo_carpeta()
        return {"carpeta": str(carpeta)} if carpeta else {"cancelado": True}

    @respuesta
    def robot_comprobar(self, comando: str = "") -> dict[str, Any]:
        """Ejecuta «<comando> --version» para comprobar que Robot está disponible."""
        partes = self._partir_comando(comando or self._comando_por_defecto())
        try:
            r = subprocess.run([*partes, "--version"], capture_output=True, text=True, timeout=60,
                               **_sin_ventana())
        except (OSError, subprocess.SubprocessError) as error:
            raise ValueError(f"No se pudo ejecutar «{' '.join(partes)}»: {error}") from None
        salida = (r.stdout + r.stderr).strip()
        if "Robot Framework" not in salida:
            raise ValueError(f"«{' '.join(partes)}» no parece Robot Framework: {salida[:300] or 'sin salida'}")
        return {"version": salida.splitlines()[-1]}

    @respuesta
    def robot_cobertura(self) -> dict[str, Any] | None:
        """Qué pruebas tienen test de Robot (None si no está configurado)."""
        self._require_dir()
        return self._cobertura()

    @respuesta
    def robot_keywords(self) -> dict[str, Any] | None:
        """Keywords de Robot para proponerlas al escribir los pasos (None si no está configurado)."""
        self._require_dir()
        return self._keywords()

    @respuesta
    def validar(self) -> dict[str, Any]:
        informe = EditorApi.validar.__wrapped__(self)
        try:
            cobertura = self._cobertura()
        except (OSError, ValueError):
            cobertura = None
        if cobertura:
            ubicacion = {}
            for ci, capitulo in enumerate(self._chapters):
                for indice, prueba in ej.tests_in_chapter(capitulo):
                    ubicacion.setdefault(str(prueba.get("id") or "").strip(), (ci, indice))
            for test_id in cobertura["hecho_sin_robot"]:
                ci, indice = ubicacion[test_id]
                informe["problemas"].append({
                    "severidad": "aviso", "capitulo": ci, "indice": indice, "id": test_id,
                    "archivo": self._chapters[ci]["path"].name,
                    "mensaje": f"Automatizable «hecho», pero ningún test de Robot lleva la etiqueta id:{test_id}.",
                })
            informe["avisos"] = sum(1 for p in informe["problemas"] if p["severidad"] == "aviso")
        return informe

    # --- Robot Framework: ejecutar desde el editor -----------------------------------
    @respuesta
    def campana_robot_lanzar(self, ids: list[str]) -> dict[str, Any]:
        """Lanza Robot solo con los tests de esas pruebas; el avance se consulta con campana_robot_progreso."""
        campaña = self._requiere_campaña()
        if campaña["datos"].get("estado") == "cerrada":
            raise ValueError("La campaña está cerrada.")
        if self._robot and self._robot["proceso"].poll() is None:
            raise ValueError("Ya hay una ejecución de Robot en marcha.")
        config = self._robot_config()
        suites = self._robot_suites()
        if suites is None or not suites.exists():
            raise ValueError("Configura antes la carpeta de tests de Robot (botón Robot de la barra superior).")
        marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        salida = campaña["carpeta"] / ej.CARPETA_EVIDENCIAS / "robot" / marca
        argumentos = robot_core.preparar_ejecucion(
            salida, suites, [str(i) for i in ids], self._partir_comando(config.get("argumentos", "")))
        orden = [*self._partir_comando(config.get("comando") or self._comando_por_defecto()), *argumentos]
        consola = open(salida / "consola.txt", "w", encoding="utf-8", errors="replace")
        try:
            proceso = subprocess.Popen(
                orden, cwd=str(suites if suites.is_dir() else suites.parent), stdout=consola,
                stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}, **_sin_ventana())
        except OSError as error:
            consola.close()
            raise ValueError(f"No se pudo lanzar Robot («{orden[0]}»): {error}. Revisa el comando en la configuración de Robot.") from None
        self._robot = {"proceso": proceso, "salida": salida, "consola": consola, "ids": list(ids),
                       "inicio": datetime.now(), "cancelada": False}
        return {"carpeta": str(salida), "pruebas": len(ids)}

    @respuesta
    def campana_robot_progreso(self) -> dict[str, Any] | None:
        if not self._robot:
            return None
        ejecucion = self._robot
        codigo = ejecucion["proceso"].poll()
        avance = robot_core.leer_progreso(ejecucion["salida"] / "progreso.jsonl")
        if codigo is not None and not ejecucion["consola"].closed:
            ejecucion["consola"].close()
        output = ejecucion["salida"] / "output.xml"
        try:
            consola = (ejecucion["salida"] / "consola.txt").read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            consola = []
        return {
            "en_marcha": codigo is None,
            "codigo": codigo,
            "cancelada": ejecucion["cancelada"],
            "segundos": int((datetime.now() - ejecucion["inicio"]).total_seconds()),
            "total": avance["total"],
            "terminados": avance["terminados"],
            "actual": avance["actual"],
            "output": str(output) if codigo is not None and output.is_file() else None,
            "consola": consola[-12:],
        }

    @respuesta
    def campana_robot_cancelar(self) -> dict[str, Any]:
        if self._robot and self._robot["proceso"].poll() is None:
            self._robot["cancelada"] = True
            self._robot["proceso"].terminate()
        return {}


def _sin_ventana() -> dict[str, Any]:
    """En Windows, que Robot no abra una consola encima del editor."""
    if sys.platform.startswith("win"):
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}
