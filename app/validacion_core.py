#!/usr/bin/env python3
"""Validación de una versión: varias ejecuciones de pruebas consolidadas.

Una validación es una carpeta con `validacion.yaml`:

    nombre: Validación v2.3
    version: Firmware 2.3.0
    pruebas_yaml: ../yaml/pruebas            # relativa a la validación (y absoluta)
    seleccion: {etiquetas: [regresion]}      # qué pruebas hay que pasar (como en una ejecución)
    ejecuciones:                             # las ejecuciones que cuentan
    - ruta: ../ejecuciones/2026-11-03_Regresión v2.3 en Torre
      ruta_absoluta: /home/…

Cada ejecución se pasa en un entorno de pruebas (`entorno_pruebas`: Automático,
Maqueta o Torre). Cada prueba indica en qué entornos hay que pasarla (su campo
`entorno`). El resultado se consolida por prueba y entorno:

- en un entorno vale el resultado más reciente de entre las ejecuciones de ese
  entorno (los anteriores quedan como historial);
- una prueba sin entorno indicado se da por buena en cualquiera (con aviso);
- un resultado en un entorno que la prueba no pide se muestra, pero no cuenta
  (un NO OK ahí se avisa);
- la prueba queda **validada** cuando en todos sus entornos está OK (o No
  aplica); **NO OK** si falla en alguno; **bloqueada** si alguno no se pudo
  ejecutar; **pendiente** si falta alguno (planificado en una ejecución o sin
  planificar).

Este módulo no depende de ninguna interfaz gráfica.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app import ejecucion_core as ej
from app import esquema
from app import formato
from app import git_pruebas
from app import lectura
from app.editor_core import read_chapters, tests_dir

ARCHIVO_VALIDACION = "validacion.yaml"
CUALQUIERA = "(cualquiera)"            # columna de las pruebas sin entorno indicado

# Estado consolidado de una prueba en la versión, de peor a mejor.
ESTADOS = ("no_ok", "bloqueada", "pendiente", "validada", "no_aplica")
ESTADOS_VISIBLES = {
    "no_ok": "NO OK", "bloqueada": "Bloqueada", "pendiente": "Pendiente",
    "validada": "Validada", "no_aplica": "No aplica",
}
# Estado de una prueba en un entorno (además de los de una ejecución).
SIN_PLANIFICAR = "sin_planificar"      # ninguna ejecución de ese entorno la incluye


# ----------------------------------------------------------------------
# Archivo
# ----------------------------------------------------------------------
def es_validacion(carpeta: str | Path) -> bool:
    return (Path(carpeta) / ARCHIVO_VALIDACION).is_file()


def _rutas(base: Path, destino: Path, clave: str) -> dict[str, str]:
    """Ruta relativa a la validación (si se puede) y absoluta, como hacen las ejecuciones con sus pruebas."""
    destino = destino.resolve()
    try:
        relativa = os.path.relpath(destino, base.resolve())
    except ValueError:                 # otra unidad en Windows
        relativa = str(destino)
    return {clave: Path(relativa).as_posix(), f"{clave}_absoluta": str(destino)}


def _resolver(base: Path, entrada: dict[str, Any], clave: str) -> Path | None:
    for k in (clave, f"{clave}_absoluta"):
        valor = entrada.get(k)
        if not valor:
            continue
        ruta = Path(str(valor)).expanduser()
        ruta = ruta if ruta.is_absolute() else (base / ruta).resolve()
        if ruta.exists():
            return ruta
    return None


def cargar(carpeta: str | Path) -> dict[str, Any]:
    carpeta = Path(carpeta)
    if not es_validacion(carpeta):
        raise ValueError(f"La carpeta no contiene una validación ({ARCHIVO_VALIDACION}).")
    datos = ej._leer_yaml(carpeta / ARCHIVO_VALIDACION) or {}
    if not isinstance(datos, dict):
        raise ValueError(f"{ARCHIVO_VALIDACION} no tiene el formato esperado.")
    datos.setdefault("ejecuciones", [])
    return {"carpeta": carpeta, "datos": datos}


def guardar(validacion: dict[str, Any]) -> None:
    formato.comprobar_datos(validacion["datos"], f"La validación «{validacion['datos'].get('nombre', '')}»")
    formato.marcar_datos(validacion["datos"])
    ej._escribir_yaml(validacion["carpeta"] / ARCHIVO_VALIDACION, validacion["datos"])


def crear(carpeta: str | Path, pruebas_yaml: str | Path, nombre: str, version: str = "",
          seleccion: dict[str, Any] | None = None) -> dict[str, Any]:
    carpeta = Path(carpeta)
    if es_validacion(carpeta):
        raise ValueError("Esa carpeta ya contiene una validación.")
    if carpeta.exists() and any(carpeta.iterdir()):
        raise ValueError("Elige una carpeta vacía (o nueva) para la validación.")
    nombre = str(nombre or "").strip()
    if not nombre:
        raise ValueError("La validación necesita un nombre.")
    pruebas = tests_dir(Path(pruebas_yaml).expanduser().resolve())
    if not ej.seleccionar(read_chapters(pruebas), seleccion or {}):
        raise ValueError("Ninguna prueba cumple el criterio de selección.")
    carpeta.mkdir(parents=True, exist_ok=True)
    datos: dict[str, Any] = {"nombre": nombre}
    if str(version or "").strip():
        datos["version"] = str(version).strip()
    datos.update({"creada": ej.ahora(), **_rutas(carpeta, pruebas, "pruebas_yaml"),
                  "seleccion": dict(seleccion or {}), "ejecuciones": []})
    validacion = {"carpeta": carpeta, "datos": datos}
    guardar(validacion)
    return validacion


def carpeta_pruebas(validacion: dict[str, Any]) -> Path | None:
    return _resolver(validacion["carpeta"], validacion["datos"], "pruebas_yaml")


def editar(validacion: dict[str, Any], cambios: dict[str, Any]) -> None:
    """Cambia nombre, versión o criterio de selección."""
    for clave in ("nombre", "version"):
        if clave in cambios:
            valor = str(cambios[clave] or "").strip()
            if clave == "nombre" and not valor:
                raise ValueError("La validación necesita un nombre.")
            if valor:
                validacion["datos"][clave] = valor
            else:
                validacion["datos"].pop(clave, None)
    if "seleccion" in cambios:
        validacion["datos"]["seleccion"] = dict(cambios["seleccion"] or {})
    guardar(validacion)


def rutas_ejecuciones(validacion: dict[str, Any]) -> list[tuple[dict[str, Any], Path | None]]:
    """(entrada de validacion.yaml, carpeta encontrada o None) de cada ejecución."""
    return [(e, _resolver(validacion["carpeta"], e, "ruta")) for e in validacion["datos"]["ejecuciones"]]


def anadir_ejecucion(validacion: dict[str, Any], carpeta_ejecucion: str | Path) -> None:
    carpeta_ejecucion = Path(carpeta_ejecucion).resolve()
    if not ej.es_ejecucion(carpeta_ejecucion):
        raise ValueError("Esa carpeta no contiene una ejecución.")
    if any(ruta and ruta.resolve() == carpeta_ejecucion for _e, ruta in rutas_ejecuciones(validacion)):
        raise ValueError("Esa ejecución ya está en la validación.")
    validacion["datos"]["ejecuciones"].append(_rutas(validacion["carpeta"], carpeta_ejecucion, "ruta"))
    guardar(validacion)


def buscar_ejecuciones(carpeta: str | Path) -> list[Path]:
    """La carpeta, si es una ejecución; si no, las ejecuciones que contiene (hasta dos niveles).

    Así se pueden añadir de una vez las ejecuciones que han ido dejando varias
    personas en una carpeta compartida.
    """
    carpeta = Path(carpeta)
    if ej.es_ejecucion(carpeta):
        return [carpeta]
    encontradas = []
    for hija in sorted(p for p in carpeta.iterdir() if p.is_dir()) if carpeta.is_dir() else []:
        if ej.es_ejecucion(hija):
            encontradas.append(hija)
        else:
            encontradas.extend(n for n in sorted(p for p in hija.iterdir() if p.is_dir()) if ej.es_ejecucion(n))
    return encontradas


def anadir_ejecuciones(validacion: dict[str, Any], carpeta: str | Path) -> dict[str, list[str]]:
    """Añade la ejecución elegida o todas las que haya dentro de la carpeta. Devuelve las añadidas y las que ya estaban."""
    encontradas = buscar_ejecuciones(carpeta)
    if not encontradas:
        raise ValueError("En esa carpeta no hay ninguna ejecución (ni dentro de sus subcarpetas).")
    ya = {ruta.resolve() for _e, ruta in rutas_ejecuciones(validacion) if ruta}
    anadidas, estaban = [], []
    for ruta in encontradas:
        if ruta.resolve() in ya:
            estaban.append(ruta.name)
            continue
        validacion["datos"]["ejecuciones"].append(_rutas(validacion["carpeta"], ruta, "ruta"))
        anadidas.append(ruta.name)
    if anadidas:
        guardar(validacion)
    return {"anadidas": anadidas, "ya_estaban": estaban}


def quitar_ejecucion(validacion: dict[str, Any], indice: int) -> None:
    ejecuciones = validacion["datos"]["ejecuciones"]
    if not isinstance(indice, int) or not 0 <= indice < len(ejecuciones):
        raise ValueError("Esa ejecución ya no está en la validación.")
    del ejecuciones[indice]
    guardar(validacion)


# ----------------------------------------------------------------------
# Consolidación
# ----------------------------------------------------------------------
def _resultados_de(ejecucion: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Resultado actual de cada prueba de la ejecución (pendiente si no tiene)."""
    salida = {}
    for entrada in ejecucion["datos"]["pruebas"]:
        test_id = str(entrada["id"])
        r = ejecucion["resultados"].get(test_id) or {}
        salida[test_id] = {
            "estado": ej.estado_de(ejecucion, test_id), "fecha": str(r.get("fecha") or ""),
            "ejecutor": str(r.get("ejecutor") or ""), "huella": str(r.get("huella") or ""),
            "observaciones": str(r.get("observaciones") or ""), "incidencia": str(r.get("incidencia") or ""),
        }
    return salida


def _vigente(resultados: list[dict[str, Any]]) -> dict[str, Any] | None:
    """El más reciente de los ejecutados; si ninguno se ha ejecutado, el primero planificado."""
    ejecutados = [r for r in resultados if r["estado"] != "pendiente"]
    if ejecutados:
        return max(ejecutados, key=lambda r: r["fecha"])
    return resultados[0] if resultados else None


def _estado_prueba(estados: list[str]) -> str:
    if "no_ok" in estados:
        return "no_ok"
    if "bloqueada" in estados:
        return "bloqueada"
    if any(e in ("pendiente", SIN_PLANIFICAR) for e in estados):
        return "pendiente"
    if estados and all(e == "no_aplica" for e in estados):
        return "no_aplica"
    return "validada"


# ----------------------------------------------------------------------
# Comparar con otra validación (la de la versión anterior)
# ----------------------------------------------------------------------
def comparar_con(validacion: dict[str, Any], carpeta: str | Path | None) -> None:
    """Guarda con qué validación se compara esta (None la quita)."""
    datos = validacion["datos"]
    for clave in ("comparar_con", "comparar_con_absoluta"):
        datos.pop(clave, None)
    if carpeta is not None:
        carpeta = Path(carpeta)
        if not es_validacion(carpeta):
            raise ValueError("Esa carpeta no contiene una validación.")
        if carpeta.resolve() == Path(validacion["carpeta"]).resolve():
            raise ValueError("Elige otra validación: no se puede comparar consigo misma.")
        datos.update(_rutas(validacion["carpeta"], carpeta, "comparar_con"))
    guardar(validacion)


def _comparacion(validacion: dict[str, Any], pruebas: list[dict[str, Any]],
                 anteriores: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any] | None:
    from app import comparar
    if not validacion["datos"].get("comparar_con"):
        return None
    ruta = _resolver(validacion["carpeta"], validacion["datos"], "comparar_con")
    if ruta is None or not es_validacion(ruta) or not anteriores:
        return {"encontrada": False, "ruta": str(validacion["datos"].get("comparar_con"))}
    anterior, consolidada = anteriores[0]
    datos = anterior["datos"]
    ahora = {p["id"]: {"estado": p["estado"], "titulo": p["titulo"]} for p in pruebas}
    return {"encontrada": True, "carpeta": str(ruta), "nombre": str(datos.get("nombre") or Path(ruta).name),
            "version": str(datos.get("version") or ""),
            **comparar.comparar(comparar.estados_validacion(consolidada), ahora)}


def _anteriores(validacion: dict[str, Any], capitulos: list[dict[str, Any]], pruebas_dir: Path | None,
                maximo: int = 7) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Las validaciones de la cadena «comparar con» (de la más reciente a la más antigua), consolidadas.

    Cada una se consolida una sola vez, sin requisitos ni comparación (solo hacen falta sus totales y estados).
    """
    salida: list[tuple[dict[str, Any], dict[str, Any]]] = []
    vistas = {Path(validacion["carpeta"]).resolve()}
    actual = validacion
    while len(salida) < maximo:
        ruta = _resolver(actual["carpeta"], actual["datos"], "comparar_con") if actual["datos"].get("comparar_con") else None
        if ruta is None or not es_validacion(ruta) or ruta.resolve() in vistas:
            break
        vistas.add(ruta.resolve())
        try:
            actual = cargar(ruta)
            suyas = carpeta_pruebas(actual)
            mismas = suyas is not None and pruebas_dir is not None and suyas.resolve() == pruebas_dir.resolve()
            salida.append((actual, consolidar(actual, capitulos if mismas else None, con_comparacion=False, con_requisitos=False)))
        except (OSError, ValueError):
            break
    return salida


def tendencia(validacion: dict[str, Any], totales: dict[str, int], porcentaje: float,
              anteriores: list[tuple[dict[str, Any], dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    """Evolución por versión siguiendo la cadena «comparar con» (de la más antigua a esta)."""
    def fila(datos: dict[str, Any], tot: dict[str, int], pct: float) -> dict[str, Any]:
        return {"nombre": str(datos.get("nombre") or ""), "version": str(datos.get("version") or ""),
                "creada": str(datos.get("creada") or ""), "total": sum(tot.values()), "totales": dict(tot), "porcentaje_validadas": pct}

    if anteriores is None:
        anteriores = _anteriores(validacion, [], carpeta_pruebas(validacion))
    filas = [fila(validacion["datos"], totales, porcentaje)]
    filas += [fila(v["datos"], c["totales"], c["porcentaje_validadas"]) for v, c in anteriores]
    return list(reversed(filas))


# ----------------------------------------------------------------------
# Requisitos: verificados según el resultado de sus pruebas
# ----------------------------------------------------------------------
REQ_ESTADOS = ("fallido", "bloqueado", "pendiente", "verificado", "sin_pruebas", "no_aplica")
REQ_VISIBLES = {"fallido": "Fallido", "bloqueado": "Bloqueado", "pendiente": "Pendiente", "verificado": "Verificado",
                "sin_pruebas": "Sin pruebas en la validación", "no_aplica": "No aplica"}


def _estado_requisito(necesita: bool, estados: list[str]) -> str:
    if not necesita:
        return "no_aplica"
    if not estados:
        return "sin_pruebas"
    for estado, resultado in (("no_ok", "fallido"), ("bloqueada", "bloqueado"), ("pendiente", "pendiente")):
        if estado in estados:
            return resultado
    return "verificado" if "validada" in estados else "no_aplica"      # todas sus pruebas No aplica


def _requisitos(pruebas: list[dict[str, Any]], capitulos: list[dict[str, Any]], pruebas_dir: Path | None) -> dict[str, Any] | None:
    """Estado de cada requisito según las pruebas de la validación que lo citan."""
    from app import trazabilidad
    if pruebas_dir is None:
        return None
    req_capitulos = lectura.requisitos(pruebas_dir)
    if not req_capitulos:
        return None
    revisiones = trazabilidad.leer_revisiones(trazabilidad.carpeta_requisitos(pruebas_dir))
    traza = trazabilidad.calcular(capitulos, req_capitulos, revisiones)
    en_validacion = {p["id"]: p for p in pruebas}
    lista, impacto = [], []
    for r in traza["requisitos"]:
        suyas = [en_validacion[p["id"]] for p in r["pruebas"] if p["id"] in en_validacion]
        fuera = sorted({p["id"] for p in r["pruebas"] if p["id"] not in en_validacion})
        estado = _estado_requisito(r["necesita"], [p["estado"] for p in suyas])
        lista.append({"id": r["id"], "titulo": r["titulo"], "capitulo": r["nombre_capitulo"], "seccion": r["seccion"],
                      "estado": estado, "modificado": r["modificado"], "necesita": r["necesita"],
                      "pruebas": [{"id": p["id"], "estado": p["estado"]} for p in suyas], "fuera": fuera})
        if r["modificado"]:
            impacto.extend(p["id"] for p in suyas if p["id"] not in impacto)
    totales = {e: sum(1 for r in lista if r["estado"] == e) for e in REQ_ESTADOS}
    evaluables = sum(totales[e] for e in ("fallido", "bloqueado", "pendiente", "verificado", "sin_pruebas"))
    return {"lista": lista, "totales": totales, "modificados": sum(1 for r in lista if r["modificado"]),
            "porcentaje_verificados": round(100 * totales["verificado"] / evaluables, 1) if evaluables else 0.0,
            "impacto": impacto}


def consolidar(validacion: dict[str, Any], capitulos: list[dict[str, Any]] | None = None,
               con_comparacion: bool = True, con_requisitos: bool = True) -> dict[str, Any]:
    """Resultado por prueba y entorno, totales, desglose, avisos, requisitos y comparación con la anterior."""
    pruebas_dir = carpeta_pruebas(validacion)
    if capitulos is None:
        if pruebas_dir is None:
            raise ValueError("No se encuentra la carpeta de pruebas de la validación.")
        esquema.configurar(pruebas_dir)         # sus entornos (fuera del editor, que ya los tiene)
        capitulos = lectura.capitulos(pruebas_dir)
    entornos = list(ej.entornos_pruebas())
    avisos: list[dict[str, str]] = []

    # Ejecuciones y sus resultados.
    ejecuciones, resultados_por_id = [], {}
    commits: dict[str | None, list[str]] = {}         # versión de las pruebas (Git) con la que se hizo cada una
    for i, (entrada, ruta) in enumerate(rutas_ejecuciones(validacion)):
        info = {"indice": i, "ruta": str(entrada.get("ruta") or ""), "carpeta": str(ruta) if ruta else None}
        if ruta is None or not ej.es_ejecucion(ruta):
            avisos.append({"tipo": "error", "id": "", "mensaje": f"No se encuentra la ejecución {info['ruta']}."})
            ejecuciones.append({**info, "encontrada": False})
            continue
        ejecucion = lectura.ejecucion(ruta)
        d = ejecucion["datos"]
        entorno = str(d.get("entorno_pruebas") or "")
        resumen = ej.resumen(ejecucion, capitulos)
        ejecuciones.append({
            **info, "encontrada": True, "nombre": str(d.get("nombre") or ruta.name), "entorno_pruebas": entorno,
            "objeto": str(d.get("objeto") or ""), "responsable": str(d.get("responsable") or ""),
            "cerrada": d.get("estado") == "cerrada", "inicio": str(d.get("inicio") or ""), "fin": str(d.get("fin") or ""),
            "total": resumen["total"], "ejecutadas": resumen["ejecutadas"], "totales": resumen["totales"],
            "version_pruebas": git_pruebas.texto_ejecucion(d),
        })
        versiones = [v for v in (d.get("git"), d.get("git_cierre")) if v]
        if any(v.get("cambios") for v in versiones):
            avisos.append({"tipo": "aviso", "id": "", "mensaje": f"La ejecución «{ejecuciones[-1]['nombre']}» se hizo con cambios sin commit en su copia de las pruebas."})
        commits.setdefault((versiones[-1].get("commit") if versiones else None), []).append(ejecuciones[-1]["nombre"])
        if not entorno:
            avisos.append({"tipo": "aviso", "id": "", "mensaje": f"La ejecución «{ejecuciones[-1]['nombre']}» no indica su entorno de pruebas: sus resultados no cuentan."})
            continue
        for test_id, r in _resultados_de(ejecucion).items():
            resultados_por_id.setdefault(test_id, []).append({**r, "entorno": entorno, "ejecucion": ejecuciones[-1]["nombre"], "ejecucion_indice": i})

    distintos = {c: n for c, n in commits.items() if c}
    if len(distintos) > 1:
        detalle = "; ".join(f"{c[:7]}: {', '.join(n)}" for c, n in distintos.items())
        avisos.append({"tipo": "aviso", "id": "", "mensaje": f"Las ejecuciones se hicieron con versiones distintas de las pruebas ({detalle})."})

    # Pruebas que hay que pasar.
    nombres = {c["path"].name: str(c["data"].get("capitulo") or c["path"].name) for c in capitulos}
    seleccion = ej.seleccionar(capitulos, validacion["datos"].get("seleccion") or {})
    pruebas, totales = [], {e: 0 for e in ESTADOS}
    por_entorno = {e: {"necesitan": 0, "ok": 0, "no_ok": 0, "bloqueada": 0, "no_aplica": 0, "pendiente": 0, SIN_PLANIFICAR: 0}
                   for e in [*entornos, CUALQUIERA]}
    por_capitulo: dict[str, dict[str, int]] = {}
    for item in seleccion:
        test_id, prueba = item["id"], item["prueba"]
        requeridos = [e for e in ej._lista(prueba.get("entorno")) if e in entornos]
        if not requeridos:
            avisos.append({"tipo": "aviso", "id": test_id, "mensaje": "La prueba no indica su entorno de pruebas: vale un resultado en cualquiera."})
        actual = ej.huella(prueba)
        resultados = resultados_por_id.get(test_id, [])
        celdas: dict[str, dict[str, Any]] = {}
        cambiada_en: list[str] = []
        for entorno in requeridos or [CUALQUIERA]:
            suyos = [r for r in resultados if entorno == CUALQUIERA or r["entorno"] == entorno]
            vigente = _vigente(suyos)
            estado = vigente["estado"] if vigente else SIN_PLANIFICAR
            celdas[entorno] = {"estado": estado, "cuenta": True, "vigente": vigente,
                               "historial": sorted(suyos, key=lambda r: r["fecha"], reverse=True)}
            if vigente and estado != "pendiente" and vigente["huella"] and vigente["huella"] != actual:
                cambiada_en.append(entorno)
                avisos.append({"tipo": "aviso", "id": test_id, "mensaje": f"La prueba ha cambiado después de ejecutarse en {entorno} («{vigente['ejecucion']}»)."})
            pe = por_entorno[entorno]
            pe["necesitan"] += 1
            pe[estado] += 1
        for entorno in entornos:
            if entorno in celdas or not requeridos:
                continue
            suyos = [r for r in resultados if r["entorno"] == entorno]
            vigente = _vigente(suyos)
            if vigente is None:
                continue
            celdas[entorno] = {"estado": vigente["estado"], "cuenta": False, "vigente": vigente,
                               "historial": sorted(suyos, key=lambda r: r["fecha"], reverse=True)}
            if vigente["estado"] == "no_ok":
                avisos.append({"tipo": "aviso", "id": test_id, "mensaje": f"NO OK en {entorno} («{vigente['ejecucion']}»), un entorno que la prueba no pide."})
        estado = _estado_prueba([c["estado"] for c in celdas.values() if c["cuenta"]])
        totales[estado] += 1
        capitulo = nombres.get(item["archivo"], item["archivo"])
        por_capitulo.setdefault(capitulo, {e: 0 for e in ESTADOS})[estado] += 1
        pruebas.append({
            "id": test_id, "titulo": str(prueba.get("titulo") or prueba.get("nombre") or ""), "archivo": item["archivo"], "capitulo": capitulo,
            "indice": item["indice"], "requeridos": requeridos, "estado": estado, "entornos": celdas,
            "cambiada_en": cambiada_en,     # entornos cuyo resultado vigente es de una versión anterior de la prueba
        })

    en_validacion = {p["id"] for p in pruebas}
    fuera = sorted(set(resultados_por_id) - en_validacion)
    total = len(pruebas)
    aplicables = total - totales["no_aplica"]
    porcentaje = round(100 * totales["validada"] / aplicables, 1) if aplicables else 0.0
    anteriores = _anteriores(validacion, capitulos, pruebas_dir) if con_comparacion and validacion["datos"].get("comparar_con") else []
    return {
        "datos": {k: v for k, v in validacion["datos"].items() if k != "ejecuciones"},
        "carpeta": str(validacion["carpeta"]),
        "entornos": entornos + ([CUALQUIERA] if por_entorno[CUALQUIERA]["necesitan"] else []),
        "ejecuciones": ejecuciones,
        "pruebas": pruebas,
        "total": total,
        "totales": totales,
        "porcentaje_validadas": porcentaje,
        "por_entorno": {e: v for e, v in por_entorno.items() if v["necesitan"]},
        "por_capitulo": por_capitulo,
        "fuera_de_alcance": fuera,
        "borrador": any(not e.get("cerrada") for e in ejecuciones if e["encontrada"]) or not ejecuciones,
        "avisos": avisos,
        "requisitos": _requisitos(pruebas, capitulos, pruebas_dir) if con_requisitos else None,
        "comparacion": _comparacion(validacion, pruebas, anteriores) if con_comparacion else None,
        "tendencia": tendencia(validacion, totales, porcentaje, anteriores) if anteriores else [],
    }
