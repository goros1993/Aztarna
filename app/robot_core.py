#!/usr/bin/env python3
"""Resultados de Robot Framework en las ejecuciones de pruebas.

Convención: cada test de Robot lleva la etiqueta `id:<ID de la prueba YAML>`
(puede llevar varias). Se lee el `output.xml` directamente, sin depender de
Robot Framework, y se admiten los formatos de RF 6 y RF 7.

Equivalencias: PASS -> OK, FAIL -> NO OK, SKIP -> No aplica. Si varios tests
de Robot cubren la misma prueba: alguno FAIL -> NO OK; si no, alguno PASS ->
OK; si todos SKIP -> No aplica. Los tests NOT RUN no cuentan.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any

from app import ejecucion_core as ej

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
    for test_id in ej.ids_de(campaña):            # en el orden de la ejecución
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
    evidencias = (campaña["carpeta"] / ej.CARPETA_EVIDENCIAS).resolve()
    origen = robot["carpeta"].resolve()
    if evidencias in origen.parents:
        # Robot se lanzó desde el editor y ya dejó sus resultados dentro de la ejecución.
        return origen.relative_to(campaña["carpeta"].resolve()).as_posix()
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
    """Apunta en la ejecución los resultados de un output.xml. El resultado anterior queda en el historial."""
    if campaña["datos"].get("estado") == "cerrada":
        raise ValueError("La ejecución está cerrada; no se pueden importar resultados.")
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


# ----------------------------------------------------------------------
# Cobertura: qué pruebas tienen test de Robot (leyendo los .robot)
# ----------------------------------------------------------------------
_SECCION = re.compile(r"^\*+\s*([A-Za-z ]+?)\s*\**\s*$")
_SEPARADOR = re.compile(r"\s{2,}|\t")


def _celdas(linea: str) -> list[str]:
    """Celdas de una línea de un .robot (formato con espacios/tabuladores o con barras)."""
    linea = linea.rstrip("\n\r")
    if linea.startswith("| ") or linea.startswith("|\t"):
        celdas = [c.strip() for c in linea.strip().strip("|").split(" | ")]
    else:
        celdas = _SEPARADOR.split(linea)
    resultado = []
    for celda in celdas:
        if celda.strip().startswith("#"):
            break                                   # comentario hasta el final de la línea
        resultado.append(celda.strip())
    return resultado


def _etiquetas_validas(valores: list[str]) -> list[str]:
    return [v for v in valores if v and "${" not in v and "@{" not in v]


def leer_robot(ruta: Path, etiquetas_heredadas: list[str] | None = None) -> dict[str, Any]:
    """Tests de un archivo .robot con sus etiquetas (sin ejecutar nada)."""
    texto = ruta.read_text(encoding="utf-8-sig", errors="replace")
    seccion, tests = "", []
    comunes = list(etiquetas_heredadas or [])          # Test Tags / Force Tags (del archivo y de __init__)
    por_defecto: list[str] = []                         # Default Tags (RF < 7)
    actual: dict[str, Any] | None = None
    ultimo_ajuste = ""
    for numero, linea in enumerate(texto.splitlines(), start=1):
        # La cabecera puede ir sola («*** Test Cases ***») o en el formato con barras («| *** Test Cases *** |»).
        primera = linea.strip().strip("|").strip()
        cabecera = _SECCION.match(primera) if primera.startswith("*") else None
        if cabecera:
            seccion = cabecera.group(1).strip().lower()
            actual, ultimo_ajuste = None, ""
            continue
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        celdas = _celdas(linea)
        if seccion in ("settings", "setting"):
            nombre = celdas[0].lower() if celdas else ""
            if nombre in ("test tags", "force tags", "default tags"):
                ultimo_ajuste = nombre
                (por_defecto if nombre == "default tags" else comunes).extend(_etiquetas_validas(celdas[1:]))
            elif nombre == "..." and ultimo_ajuste in ("test tags", "force tags", "default tags"):
                (por_defecto if ultimo_ajuste == "default tags" else comunes).extend(_etiquetas_validas(celdas[1:]))
            else:
                ultimo_ajuste = ""
        elif seccion in ("test cases", "test case", "tasks", "task"):
            if not linea[0].isspace() and celdas and celdas[0]:
                actual = {"archivo": ruta, "linea": numero, "nombre": celdas[0], "etiquetas": None}
                tests.append(actual)
                ultimo_ajuste = ""
                celdas = ["", *celdas[1:]]
            if actual is None:
                continue
            resto = [c for c in celdas[1:]]
            while resto and not resto[0]:
                resto = resto[1:]
            if not resto:
                continue
            if resto[0].lower() == "[tags]":
                actual["etiquetas"] = _etiquetas_validas(resto[1:])
                ultimo_ajuste = "[tags]"
            elif resto[0] == "..." and ultimo_ajuste == "[tags]":
                actual["etiquetas"].extend(_etiquetas_validas(resto[1:]))
            else:
                ultimo_ajuste = resto[0].lower() if resto[0].startswith("[") else ""
    for test in tests:
        propias = test["etiquetas"] if test["etiquetas"] is not None else por_defecto
        test["etiquetas"] = [*comunes, *propias]
        test["ids"] = ids_de_etiquetas(test["etiquetas"])
    return {"tests": tests, "etiquetas_comunes": comunes}


def escanear_suites(carpeta: str | Path) -> dict[str, Any]:
    """Recorre una carpeta de tests de Robot y devuelve sus tests con sus `id:`."""
    carpeta = Path(carpeta)
    if not carpeta.exists():
        raise ValueError(f"No existe la carpeta de tests de Robot: {carpeta}")
    archivos = [carpeta] if carpeta.is_file() else sorted(carpeta.rglob("*.robot"))
    heredadas: dict[Path, list[str]] = {}
    tests, errores = [], []
    # Las etiquetas de __init__.robot se aplican a su carpeta y subcarpetas.
    for init in sorted((a for a in archivos if a.name == "__init__.robot"), key=lambda a: len(a.parts)):
        try:
            propias = leer_robot(init, heredadas.get(init.parent.parent, []))["etiquetas_comunes"]
        except OSError as error:
            errores.append(f"{init}: {error}")
            continue
        heredadas[init.parent] = propias
    for archivo in archivos:
        if archivo.name == "__init__.robot" or any(p.startswith(".") for p in archivo.relative_to(carpeta if carpeta.is_dir() else archivo.parent).parts):
            continue
        base = next((heredadas[p] for p in [archivo.parent, *archivo.parents] if p in heredadas), [])
        try:
            tests.extend(leer_robot(archivo, base)["tests"])
        except OSError as error:
            errores.append(f"{archivo}: {error}")
    return {"carpeta": carpeta, "tests": tests, "errores": errores}


def cobertura(capitulos: list[dict[str, Any]], escaneo: dict[str, Any]) -> dict[str, Any]:
    """Cruza las pruebas YAML con los tests de Robot."""
    base = escaneo["carpeta"] if escaneo["carpeta"].is_dir() else escaneo["carpeta"].parent
    por_id: dict[str, list[dict[str, Any]]] = {}
    sin_id = []
    for test in escaneo["tests"]:
        relativo = test["archivo"].relative_to(base).as_posix() if base in test["archivo"].parents else test["archivo"].name
        datos = {"archivo": relativo, "linea": test["linea"], "nombre": test["nombre"]}
        if not test["ids"]:
            sin_id.append(datos)
        for test_id in test["ids"]:
            por_id.setdefault(test_id, []).append(datos)
    pruebas = ej.indice_por_id(capitulos)
    hecho_sin_robot = sorted(
        i for i, p in pruebas.items()
        if str(p["prueba"].get("automatizable") or "").strip().lower() == "hecho" and i not in por_id
    )
    return {
        "tests_robot": len(escaneo["tests"]),
        "por_id": por_id,
        "cubiertas": sorted(i for i in por_id if i in pruebas),
        "inexistentes": sorted(i for i in por_id if i not in pruebas),
        "sin_id": sin_id,
        "hecho_sin_robot": hecho_sin_robot,
        "errores": escaneo["errores"],
    }


# ----------------------------------------------------------------------
# Keywords: para proponerlas al escribir los pasos de las pruebas
# ----------------------------------------------------------------------
_ARGUMENTO_INCRUSTADO = re.compile(r"\$\{([^}:]+)(?::[^}]*)?\}")
_CONTROL = {"for", "end", "if", "else", "else if", "while", "try", "except", "finally",
            "return", "break", "continue", "in", "in range", "in enumerate", "in zip", "var"}
_CARPETAS_IGNORADAS = {"venv", ".venv", "env", "site-packages", "node_modules", "__pycache__", "build", "dist"}


def normalizar_keyword(nombre: str) -> str:
    """Como compara Robot los nombres: sin mayúsculas, espacios ni guiones bajos."""
    return re.sub(r"[\s_]+", "", nombre).lower()


def _argumento_robot(celda: str) -> dict[str, Any] | None:
    m = re.match(r"^([$@&])\{([^}]+)\}(?:=(.*))?$", celda.strip())
    if not m:
        return None
    tipo = {"$": "", "@": "*", "&": "**"}[m.group(1)]
    return {"nombre": tipo + m.group(2), "obligatorio": not tipo and m.group(3) is None,
            "defecto": m.group(3)}


def leer_keywords_robot(ruta: Path) -> dict[str, Any]:
    """Keywords de un .robot o .resource y las llamadas a keywords que hace."""
    texto = ruta.read_text(encoding="utf-8-sig", errors="replace")
    seccion, keywords, llamadas, librerias = "", [], [], []
    actual: dict[str, Any] | None = None
    ultimo_ajuste = ""
    for numero, linea in enumerate(texto.splitlines(), start=1):
        primera = linea.strip().strip("|").strip()
        cabecera = _SECCION.match(primera) if primera.startswith("*") else None
        if cabecera:
            seccion = cabecera.group(1).strip().lower()
            actual, ultimo_ajuste = None, ""
            continue
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        celdas = _celdas(linea)
        if seccion in ("settings", "setting"):
            if len(celdas) > 1 and celdas[0].lower() == "library":
                librerias.append(celdas[1])
            continue
        if seccion not in ("keywords", "keyword", "test cases", "test case", "tasks", "task"):
            continue
        if not linea[0].isspace() and celdas and celdas[0]:
            actual = None
            if seccion.startswith("keyword"):
                actual = {"nombre": celdas[0], "argumentos": [], "doc": "", "archivo": ruta, "linea": numero}
                keywords.append(actual)
            ultimo_ajuste = ""
            celdas = ["", *celdas[1:]]
        resto = celdas[1:]
        while resto and not resto[0]:
            resto = resto[1:]
        if not resto:
            continue
        clave = resto[0].lower()
        if clave == "..." and ultimo_ajuste:
            resto = [ultimo_ajuste, *resto[1:]]
            clave = ultimo_ajuste
        if clave == "[arguments]" and actual is not None:
            actual["argumentos"].extend(a for a in map(_argumento_robot, resto[1:]) if a)
            ultimo_ajuste = clave
        elif clave == "[documentation]" and actual is not None:
            if not actual["doc"]:
                actual["doc"] = " ".join(resto[1:]).strip()
            ultimo_ajuste = clave
        elif clave.startswith("["):
            ultimo_ajuste = clave if clave in ("[tags]",) else ""
        else:
            ultimo_ajuste = ""
            # Llamada a una keyword: se saltan las asignaciones (${x}=) y las estructuras de control.
            while resto and re.match(r"^[$@&]\{[^}]+\}\s*=?$", resto[0]):
                resto = resto[1:]
            if resto and resto[0].lower() not in _CONTROL and resto[0] != "...":
                llamadas.append(resto[0])
    return {"keywords": keywords, "llamadas": llamadas, "librerias": librerias}


def _nombre_python(nombre: str) -> str:
    """leer_trama_can -> Leer Trama Can (Robot ignora mayúsculas y guiones bajos)."""
    return " ".join(p[:1].upper() + p[1:] for p in nombre.split("_") if p)


def _decorador(nodo: Any, nombres: tuple[str, ...]) -> Any:
    for d in nodo.decorator_list:
        destino = d.func if isinstance(d, ast.Call) else d
        nombre = destino.attr if isinstance(destino, ast.Attribute) else getattr(destino, "id", "")
        if nombre in nombres:
            return d
    return None


def _nombre_decorado(decorador: Any) -> str | None:
    if not isinstance(decorador, ast.Call):
        return None
    for valor in [*decorador.args[:1], *(k.value for k in decorador.keywords if k.arg == "name")]:
        if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
            return valor.value
    return None


def _auto_keywords(cuerpo: list[Any]) -> bool:
    for nodo in cuerpo:
        if isinstance(nodo, ast.Assign) and any(getattr(t, "id", "") == "ROBOT_AUTO_KEYWORDS" for t in nodo.targets):
            return not (isinstance(nodo.value, ast.Constant) and nodo.value.value is False)
    return True


def leer_keywords_python(ruta: Path, es_libreria: bool = True) -> list[dict[str, Any]]:
    """Keywords de una librería de Python, leyendo el código sin importarlo.

    Siempre se toman las funciones decoradas con @keyword. Si el archivo es una
    librería (algún .robot lo importa con Library), también las funciones
    públicas del módulo y los métodos públicos de la clase que se llama como
    el archivo o que tiene ajustes de librería (ROBOT_LIBRARY_… o @library).
    Se respetan ROBOT_AUTO_KEYWORDS = False, @library y @not_keyword.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8-sig", errors="replace"), filename=str(ruta))
    keywords = []

    def añadir(funcion: Any, auto: bool) -> None:
        if _decorador(funcion, ("not_keyword",)):
            return
        decorador = _decorador(funcion, ("keyword",))
        if decorador is None and (not auto or funcion.name.startswith("_")):
            return
        a = funcion.args
        posicionales = [*a.posonlyargs, *a.args]
        if posicionales and posicionales[0].arg in ("self", "cls"):
            posicionales = posicionales[1:]
        sin_defecto = len(posicionales) - len(a.defaults)
        argumentos = [{"nombre": p.arg, "obligatorio": i < sin_defecto,
                       "defecto": None if i < sin_defecto else ast.unparse(a.defaults[i - sin_defecto])}
                      for i, p in enumerate(posicionales)]
        if a.vararg:
            argumentos.append({"nombre": "*" + a.vararg.arg, "obligatorio": False, "defecto": None})
        argumentos += [{"nombre": p.arg, "obligatorio": d is None, "defecto": None if d is None else ast.unparse(d)}
                       for p, d in zip(a.kwonlyargs, a.kw_defaults)]
        if a.kwarg:
            argumentos.append({"nombre": "**" + a.kwarg.arg, "obligatorio": False, "defecto": None})
        doc = (ast.get_docstring(funcion) or "").strip().splitlines()
        keywords.append({
            "nombre": _nombre_decorado(decorador) or _nombre_python(funcion.name),
            "argumentos": argumentos, "doc": doc[0] if doc else "", "archivo": ruta, "linea": funcion.lineno,
        })

    auto_modulo = es_libreria and _auto_keywords(arbol.body)
    funciones = (ast.FunctionDef, ast.AsyncFunctionDef)
    for nodo in arbol.body:
        if isinstance(nodo, funciones):
            añadir(nodo, auto_modulo)
        elif isinstance(nodo, ast.ClassDef) and not nodo.name.startswith("_"):
            decorada = _decorador(nodo, ("library",))
            clase_libreria = nodo.name == ruta.stem or decorada is not None or any(
                isinstance(n, ast.Assign) and any(getattr(t, "id", "").startswith("ROBOT_LIBRARY_") for t in n.targets)
                for n in nodo.body)
            auto = es_libreria and clase_libreria and _auto_keywords(nodo.body)
            if decorada is not None:                # @library: solo las decoradas, salvo auto_keywords=True
                auto = auto and any(k.arg == "auto_keywords" and getattr(k.value, "value", False) is True
                                    for k in getattr(decorada, "keywords", []))
            for metodo in nodo.body:
                if isinstance(metodo, funciones) and not metodo.name.startswith("_"):
                    añadir(metodo, auto)
    return keywords


def _patron_keyword(nombre: str) -> re.Pattern[str] | None:
    """Expresión que reconoce una keyword con argumentos incrustados (${planta})."""
    if "${" not in nombre:
        return None
    partes, inicio = [], 0
    for m in _ARGUMENTO_INCRUSTADO.finditer(nombre):
        partes.append(re.escape(nombre[inicio:m.start()]))
        partes.append("(.+?)")
        inicio = m.end()
    partes.append(re.escape(nombre[inicio:]))
    return re.compile("^" + "".join(partes) + "$", re.IGNORECASE)


def escanear_keywords(carpetas: list[str | Path]) -> dict[str, Any]:
    """Keywords de los .robot, .resource y librerías de Python de unas carpetas."""
    keywords: list[dict[str, Any]] = []
    llamadas: list[str] = []
    errores: list[str] = []
    librerias: set[str] = set()
    archivos: list[tuple[Path, Path]] = []
    vistos: set[Path] = set()
    for carpeta in map(Path, carpetas):
        if not carpeta.exists():
            errores.append(f"No existe: {carpeta}")
            continue
        base = carpeta if carpeta.is_dir() else carpeta.parent
        encontrados = [carpeta] if carpeta.is_file() else sorted(
            a for a in carpeta.rglob("*")
            if a.suffix.lower() in (".robot", ".resource", ".py")
            and not any(p.startswith(".") or p in _CARPETAS_IGNORADAS for p in a.relative_to(carpeta).parts[:-1]))
        for archivo in encontrados:
            if archivo.resolve() not in vistos and archivo.name != "__init__.py" and archivo.name != "progreso_editor.py":
                vistos.add(archivo.resolve())
                archivos.append((archivo, base))
    # Primero los .robot/.resource: dicen qué archivos de Python son librerías.
    archivos.sort(key=lambda a: a[0].suffix.lower() == ".py")
    for archivo, base in archivos:
        try:
            if archivo.suffix.lower() == ".py":
                propias = leer_keywords_python(archivo, archivo.stem in librerias)
                origen = "python"
            else:
                leido = leer_keywords_robot(archivo)
                propias, origen = leido["keywords"], "robot"
                llamadas.extend(leido["llamadas"])
                for nombre in leido["librerias"]:
                    nombre = nombre.replace("\\", "/")
                    # «lib/banco.py» -> banco; «paquete.modulo» y «paquete.modulo.Clase» -> modulo, Clase
                    partes = [Path(nombre).stem] if nombre.lower().endswith(".py") else nombre.split(".")[-2:]
                    librerias.update(partes)
        except (OSError, SyntaxError, ValueError) as error:
            errores.append(f"{archivo}: {error}")
            continue
        for kw in propias:
            kw["origen"] = origen
            kw["archivo"] = kw["archivo"].relative_to(base).as_posix() if base in kw["archivo"].parents else kw["archivo"].name
        keywords.extend(propias)
    # Cuántas veces se usa cada keyword (para ordenar las sugerencias).
    usos: dict[str, int] = {}
    for llamada in llamadas:
        usos[normalizar_keyword(llamada)] = usos.get(normalizar_keyword(llamada), 0) + 1
    for kw in keywords:
        incrustados = {m.group(1).strip() for m in _ARGUMENTO_INCRUSTADO.finditer(kw["nombre"])}
        kw["argumentos"] = [a for a in kw["argumentos"] if a["nombre"] not in incrustados]
        clave = normalizar_keyword(kw["nombre"])
        patron = _patron_keyword(kw["nombre"])
        kw["usos"] = sum(n for c, n in usos.items() if c == clave or c.endswith("." + clave)) + (
            sum(1 for llamada in llamadas if patron.match(llamada)) if patron else 0)
    keywords.sort(key=lambda k: (k["nombre"].lower(), k["archivo"]))
    return {"keywords": keywords, "errores": errores}


# ----------------------------------------------------------------------
# Ejecutar Robot desde el editor
# ----------------------------------------------------------------------
# Listener (API v3) que escribe el avance en un archivo JSON por líneas. Se
# escribe junto a los resultados al lanzar Robot, así funciona aunque el
# editor sea un .exe y Robot esté instalado en otro Python.
LISTENER = '''\
"""Escribe el avance de Robot Framework para el Editor de pruebas (generado)."""
import json


class progreso_editor:
    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, ruta):
        self._archivo = open(ruta, "a", encoding="utf-8")
        self._primera = True

    def _escribir(self, **datos):
        self._archivo.write(json.dumps(datos, ensure_ascii=False) + "\\n")
        self._archivo.flush()

    def start_suite(self, data, result):
        if self._primera:
            self._primera = False
            self._escribir(tipo="inicio", total=data.test_count)

    def start_test(self, data, result):
        ids = [t[3:] for t in data.tags if t.lower().startswith("id:")]
        self._escribir(tipo="test", nombre=data.name, ids=ids)

    def end_test(self, data, result):
        self._escribir(tipo="fin_test", nombre=data.name, estado=result.status, mensaje=(result.message or "")[:300])

    def close(self):
        self._escribir(tipo="fin")
        self._archivo.close()
'''


def preparar_ejecucion(carpeta_salida: Path, carpeta_suites: str | Path, ids: list[str],
                       argumentos: list[str] | None = None) -> list[str]:
    """Escribe el listener y el archivo de argumentos; devuelve los argumentos para Robot.

    Las etiquetas se pasan en minúsculas: Robot no distingue mayúsculas al
    comparar etiquetas, pero sí interpreta AND, OR y NOT en mayúsculas como
    operadores (un ID como «ANDEN-01» rompería el filtro).
    """
    if not ids:
        raise ValueError("No hay ninguna prueba que ejecutar.")
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    listener = carpeta_salida / "progreso_editor.py"
    listener.write_text(LISTENER, encoding="utf-8")
    progreso = carpeta_salida / "progreso.jsonl"
    progreso.write_text("", encoding="utf-8")
    lineas = [
        f"--outputdir {carpeta_salida}",
        f"--listener {listener};{progreso}",
        *(f"--include {PREFIJO_ID}{i.lower()}" for i in ids),
    ]
    archivo_argumentos = carpeta_salida / "argumentos.txt"
    archivo_argumentos.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ["--argumentfile", str(archivo_argumentos), *(argumentos or []), str(carpeta_suites)]


def leer_progreso(ruta: Path) -> dict[str, Any]:
    """Avance según el archivo que escribe el listener."""
    datos: dict[str, Any] = {"total": None, "terminados": [], "actual": None, "fin": False}
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return datos
    for linea in lineas:
        try:
            evento = json.loads(linea)
        except ValueError:
            continue                       # línea a medio escribir
        tipo = evento.get("tipo")
        if tipo == "inicio":
            datos["total"] = evento.get("total")
        elif tipo == "test":
            datos["actual"] = {"nombre": evento.get("nombre"), "ids": evento.get("ids") or []}
        elif tipo == "fin_test":
            datos["terminados"].append({k: evento.get(k) for k in ("nombre", "estado", "mensaje")})
            datos["actual"] = None
        elif tipo == "fin":
            datos["fin"] = True
    return datos
