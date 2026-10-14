#!/usr/bin/env python3
"""Resultados de Robot Framework en las campañas de ejecución.

Convención: cada test de Robot lleva la etiqueta `id:<ID de la prueba YAML>`
(puede llevar varias). Se lee el `output.xml` directamente, sin depender de
Robot Framework, y se admiten los formatos de RF 6 y RF 7.

Equivalencias: PASS -> OK, FAIL -> NO OK, SKIP -> No aplica. Si varios tests
de Robot cubren la misma prueba: alguno FAIL -> NO OK; si no, alguno PASS ->
OK; si todos SKIP -> No aplica. Los tests NOT RUN no cuentan.
"""
from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any

import ejecucion_core as ej

PREFIJO_ID = "id:"
EJECUTOR = "Robot Framework"
ESTADO_ROBOT = {"PASS": "ok", "FAIL": "no_ok", "SKIP": "no_aplica"}
_IMG = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)


# ----------------------------------------------------------------------
# Lectura del output.xml
# ----------------------------------------------------------------------
def _fecha(texto: str | None) -> datetime | None:
    """RF 7: «2026-10-14T23:01:12.471182»; RF 6: «20261014 23:01:12.747»."""
    if not texto or texto == "N/A":
        return None
    for formato in ("%Y%m%d %H:%M:%S.%f", "%Y%m%d %H:%M:%S"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def _tiempos(status: ET.Element | None) -> tuple[datetime | None, datetime | None]:
    if status is None:
        return None, None
    if "start" in status.attrib:                          # RF 7
        inicio = _fecha(status.get("start"))
        try:
            duracion = float(status.get("elapsed") or 0)
        except ValueError:
            duracion = 0.0
        return inicio, inicio + timedelta(seconds=duracion) if inicio else None
    return _fecha(status.get("starttime")), _fecha(status.get("endtime"))   # RF 6 y anteriores


def _etiquetas(test: ET.Element) -> list[str]:
    # RF 4+: <tag> directamente bajo <test>; versiones antiguas: <tags><tag>.
    return [t.text.strip() for t in [*test.findall("tag"), *test.findall("tags/tag")] if t.text and t.text.strip()]


def ids_de_etiquetas(etiquetas: list[str]) -> list[str]:
    ids = []
    for etiqueta in etiquetas:
        if etiqueta.lower().startswith(PREFIJO_ID):
            valor = etiqueta[len(PREFIJO_ID):].strip()
            if valor and valor not in ids:
                ids.append(valor)
    return ids


def _imagenes(test: ET.Element) -> list[str]:
    """Capturas enlazadas en los mensajes HTML del test (rutas relativas a la carpeta de resultados)."""
    rutas: list[str] = []
    for msg in test.iter("msg"):
        if msg.get("html") not in ("true", "yes") or not msg.text:
            continue
        for src in _IMG.findall(unescape(msg.text)):
            if not re.match(r"^(?:[a-z]+:|/|\\\\)", src, re.IGNORECASE) and src not in rutas:
                rutas.append(src)
    return rutas


def leer_output(ruta: str | Path) -> dict[str, Any]:
    """Lee un output.xml de Robot Framework y devuelve sus tests con su resultado."""
    ruta = Path(ruta)
    try:
        raiz = ET.parse(ruta).getroot()
    except ET.ParseError as error:
        raise ValueError(f"{ruta.name} no es un XML válido: {error}") from None
    except OSError as error:
        raise ValueError(f"No se puede leer {ruta}: {error}") from None
    if raiz.tag != "robot":
        raise ValueError(f"{ruta.name} no es un output.xml de Robot Framework.")

    tests: list[dict[str, Any]] = []

    def recorrer(suite: ET.Element, ruta_suite: list[str]) -> None:
        nombre = suite.get("name") or ""
        camino = [*ruta_suite, nombre] if nombre else ruta_suite
        for test in suite.findall("test"):
            status = test.find("status")            # el estado del test es su <status> directo
            inicio, fin = _tiempos(status)
            tests.append({
                "id_robot": test.get("id") or "",
                "nombre": test.get("name") or "",
                "suite": ".".join(camino),
                "etiquetas": _etiquetas(test),
                "ids": ids_de_etiquetas(_etiquetas(test)),
                "estado": (status.get("status") if status is not None else "NOT RUN") or "NOT RUN",
                "mensaje": ((status.text or "") if status is not None else "").strip(),
                "inicio": inicio,
                "fin": fin,
                "imagenes": _imagenes(test),
            })
        for hija in suite.findall("suite"):
            recorrer(hija, camino)

    for suite in raiz.findall("suite"):
        recorrer(suite, [])
    return {
        "carpeta": ruta.parent,
        "archivo": ruta,
        "generador": raiz.get("generator") or "",
        "generado": _fecha(raiz.get("generated")),
        "tests": tests,
    }


# ----------------------------------------------------------------------
# Plan de importación
# ----------------------------------------------------------------------
def estado_consolidado(estados: list[str]) -> str | None:
    """Resultado de una prueba a partir de los de sus tests de Robot (None si ninguno se ejecutó)."""
    if "FAIL" in estados:
        return "no_ok"
    if "PASS" in estados:
        return "ok"
    if "SKIP" in estados:
        return "no_aplica"
    return None


def _observaciones(tests: list[dict[str, Any]], estado: str) -> str:
    def linea(t: dict[str, Any]) -> str:
        texto = f"{t['estado']} · {t['nombre']}"
        return f"{texto}: {t['mensaje']}" if t["mensaje"] else texto
    if len(tests) == 1:
        t = tests[0]
        if estado == "ok":
            return f"Robot: «{t['nombre']}» PASS."
        return f"Robot: «{t['nombre']}» {t['estado']}. {t['mensaje']}".strip()
    cuenta = {e: sum(1 for x in tests if x["estado"] == e) for e in ("PASS", "FAIL", "SKIP")}
    cabecera = f"Robot: {len(tests)} tests (" + ", ".join(f"{n} {e}" for e, n in cuenta.items() if n) + ")."
    importantes = [t for t in tests if t["estado"] != "PASS"] if estado != "ok" else tests
    return "\n".join([cabecera, *(linea(t) for t in importantes)])


def plan(campaña: dict[str, Any], robot: dict[str, Any], capitulos: list[dict[str, Any]]) -> dict[str, Any]:
    """Qué haría la importación, sin cambiar nada (para la vista previa)."""
    en_campaña = set(ej.ids_de(campaña))
    en_yaml = set(ej.indice_por_id(capitulos))
    por_id: dict[str, list[dict[str, Any]]] = {}
    for test in robot["tests"]:
        for test_id in test["ids"]:
            por_id.setdefault(test_id, []).append(test)

    resultados = []
    for test_id in ej.ids_de(campaña):            # en el orden de la campaña
        tests = [t for t in por_id.get(test_id, []) if t["estado"] in ESTADO_ROBOT]
        estado = estado_consolidado([t["estado"] for t in tests])
        if estado is None:
            continue
        finales = [t["fin"] for t in tests if t["fin"]]
        anterior = campaña["resultados"].get(test_id) or {}
        resultados.append({
            "id": test_id,
            "estado": estado,
            "tests": [t["nombre"] for t in tests],
            "observaciones": _observaciones(tests, estado),
            "fecha": max(finales).isoformat(timespec="minutes") if finales else None,
            "imagenes": [img for t in tests for img in t["imagenes"]],
            "anterior": str(anterior.get("estado")) if anterior else None,
            "anterior_robot": anterior.get("origen") == "robot" if anterior else False,
        })
    sin_id = [t["nombre"] for t in robot["tests"] if not t["ids"]]
    fuera = sorted(i for i in por_id if i not in en_campaña and i in en_yaml)
    inexistentes = sorted(i for i in por_id if i not in en_yaml)
    cubiertos = {r["id"] for r in resultados}
    return {
        "generador": robot["generador"],
        "tests_robot": len(robot["tests"]),
        "resultados": resultados,
        "totales": {e: sum(r["estado"] == e for r in resultados) for e in ("ok", "no_ok", "no_aplica")},
        "sustituyen_manual": [r["id"] for r in resultados if r["anterior"] and r["anterior"] != "pendiente" and not r["anterior_robot"]],
        "sin_id": sin_id,
        "fuera_de_campaña": fuera,
        "inexistentes": inexistentes,
        "sin_robot": [i for i in ej.ids_de(campaña) if i not in cubiertos],
    }


# ----------------------------------------------------------------------
# Importación
# ----------------------------------------------------------------------
def _copiar_resultados(campaña: dict[str, Any], robot: dict[str, Any], imagenes: set[str]) -> str:
    """Copia output.xml, log.html, report.html y las capturas a evidencias/robot/<fecha>/."""
    marca = (robot["generado"] or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    relativa = f"{ej.CARPETA_EVIDENCIAS}/robot/{marca}"
    destino = campaña["carpeta"] / relativa
    destino.mkdir(parents=True, exist_ok=True)
    origen = robot["carpeta"]
    copiar = [robot["archivo"].name, "log.html", "report.html", *sorted(imagenes)]
    for nombre in copiar:
        fuente = (origen / nombre).resolve()
        if fuente.is_file() and (origen.resolve() in fuente.parents):
            (destino / nombre).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fuente, destino / nombre)
    return relativa


def importar(campaña: dict[str, Any], ruta_output: str | Path, capitulos: list[dict[str, Any]],
             ejecutor: str = EJECUTOR) -> dict[str, Any]:
    """Apunta en la campaña los resultados de un output.xml. El resultado anterior queda en el historial."""
    if campaña["datos"].get("estado") == "cerrada":
        raise ValueError("La campaña está cerrada; no se pueden importar resultados.")
    robot = leer_output(ruta_output)
    propuesta = plan(campaña, robot, capitulos)
    if not propuesta["resultados"]:
        return propuesta
    imagenes = {img for r in propuesta["resultados"] for img in r["imagenes"]}
    carpeta = _copiar_resultados(campaña, robot, imagenes)
    log = f"{carpeta}/log.html"
    hay_log = (campaña["carpeta"] / log).is_file()
    por_id = ej.indice_por_id(capitulos)
    for r in propuesta["resultados"]:
        evidencias = [f"{carpeta}/{img}" for img in r["imagenes"] if (campaña["carpeta"] / carpeta / img).is_file()]
        if hay_log:
            evidencias.append(log)
        prueba = por_id.get(r["id"])
        ej.registrar(
            campaña, r["id"], r["estado"], observaciones=r["observaciones"], evidencias=evidencias,
            ejecutor=ejecutor, huella_actual=ej.huella(prueba["prueba"]) if prueba else "",
            fecha=r["fecha"], origen="robot",
        )
    propuesta["carpeta_evidencias"] = carpeta
    return propuesta
