#!/usr/bin/env python3
"""Informe de la validación de una versión: DOCX (y PDF si hay con qué convertirlo).

Resume las ejecuciones de la validación y da, para cada prueba, su resultado en
cada entorno de pruebas y el de la versión (ver validacion_core.py). El detalle
de cada prueba está en el informe de cada ejecución.

Uso:
    python herramientas.py validacion ruta/a/la/validación [-o informe.docx] [--pdf]
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from docx.enum.section import WD_ORIENT
from docx.shared import Cm, Pt, RGBColor

from app import firma
from app import informe_docx as inf
from app import validacion_core as vc
from app import yaml_a_docx as yd

CELDA_TXT = {"ok": "OK", "no_ok": "NO OK", "bloqueada": "Bloqueada", "no_aplica": "No aplica",
             "pendiente": "Pendiente", vc.SIN_PLANIFICAR: "Sin planificar"}
_CLASE = {"validada": "ok", vc.SIN_PLANIFICAR: "pendiente"}


def _clase(estado: str) -> str:
    return _CLASE.get(estado, estado)


def _colorear(celda, estado: str, cuenta: bool = True) -> None:
    """Fondo y color del texto de una celda según el estado."""
    clase = _clase(estado)
    yd.sombrear(celda, inf.FONDO_ESTADO.get(clase, "FFFFFF") if cuenta else "FFFFFF")
    for p in celda.paragraphs:
        for run in p.runs:
            run.font.color.rgb = RGBColor.from_string(inf.COLOR_ESTADO.get(clase, "18242B"))
            run.bold = cuenta or None
            run.italic = (not cuenta) or None


def _apaisado(doc) -> None:
    """Página apaisada para que quepa la tabla prueba × entorno."""
    seccion = doc.sections[0]
    seccion.orientation = WD_ORIENT.LANDSCAPE
    seccion.page_width, seccion.page_height = Cm(29.7), Cm(21)


def escribir_resumen(doc, d: dict[str, Any]) -> None:
    datos = d["datos"]
    inf._parrafo(doc, "Informe de validación", negrita=True, tamaño=22, despues=2)
    inf._parrafo(doc, str(datos.get("nombre") or ""), tamaño=15, color="485862", despues=10)
    if d["borrador"]:
        abiertas = sum(1 for e in d["ejecuciones"] if e["encontrada"] and not e["cerrada"])
        inf._parrafo(doc, f"BORRADOR: {abiertas} de {len(d['ejecuciones'])} ejecuciones siguen abiertas." if d["ejecuciones"]
                     else "BORRADOR: la validación no tiene ejecuciones.",
                     negrita=True, color=inf.COLOR_ESTADO["no_ok"], despues=8)

    criterio = "; ".join(f"{k}: {', '.join(map(str, v)) if isinstance(v, list) else v}"
                         for k, v in dict(datos.get("seleccion") or {}).items()) or "todas las pruebas"
    t = d["totales"]
    filas = [
        ["Versión", datos.get("version", "")],
        ["Criterio de selección", criterio],
        ["Pruebas", str(d["total"])],
        ["Validadas", f"{t['validada']} ({d['porcentaje_validadas']} % de las que aplican)"],
        ["Informe generado", datetime.now().strftime("%d/%m/%Y %H:%M")],
    ]
    inf._tabla(doc, ["Validación", ""], [f for f in filas if str(f[1]).strip()], [6, 19])

    inf._apartado(doc, "Resultado de la versión")
    inf._parrafo(doc, "Una prueba está validada cuando su resultado es OK (o No aplica) en todos los entornos "
                      "de pruebas que indica. En cada entorno cuenta el resultado más reciente.", color="485862")
    tabla = inf._tabla(doc, ["Resultado", "Pruebas"],
                       [[vc.ESTADOS_VISIBLES[e], str(t[e])] for e in ("validada", "no_ok", "bloqueada", "pendiente", "no_aplica")],
                       [8, 4])
    for fila, e in zip(tabla.rows[1:], ("validada", "no_ok", "bloqueada", "pendiente", "no_aplica")):
        _colorear(fila.cells[0], e)

    inf._apartado(doc, "Ejecuciones")
    if d["ejecuciones"]:
        filas = []
        for e in d["ejecuciones"]:
            if not e["encontrada"]:
                filas.append([f"{e['ruta']} (no se encuentra)", "", "", "", ""])
                continue
            tot = e["totales"]
            resultado = ", ".join(f"{n} {CELDA_TXT[k]}" for k, n in tot.items() if n)
            periodo = f"{inf._fecha(e['inicio'])} – {inf._fecha(e['fin'])}" if e["cerrada"] else f"{inf._fecha(e['inicio'])} – (abierta)"
            filas.append([e["nombre"], e["entorno_pruebas"] or "(sin indicar)", e["responsable"], periodo, resultado])
        inf._tabla(doc, ["Ejecución", "Entorno", "Responsable", "Periodo", "Resultados"], filas, [6.5, 3, 4, 5.5, 6])
    else:
        inf._parrafo(doc, "Sin ejecuciones.")

    inf._apartado(doc, "Por entorno de pruebas")
    claves = ("ok", "no_ok", "bloqueada", "no_aplica", "pendiente", vc.SIN_PLANIFICAR)
    inf._tabla(doc, ["Entorno", "Pruebas", *[CELDA_TXT[k] for k in claves]],
               [[e, str(c["necesitan"]), *[str(c[k] or "·") for k in claves]] for e, c in d["por_entorno"].items()],
               [4, 2.5, 2.5, 2.5, 3, 3, 3, 3.5])

    if d["avisos"]:
        inf._apartado(doc, "Avisos")
        inf._tabla(doc, ["Prueba", "Aviso"], [[a["id"] or "—", a["mensaje"]] for a in d["avisos"]], [4, 21])


def escribir_comparacion(doc, d: dict[str, Any]) -> None:
    """Cambios respecto a la validación anterior (si se ha elegido una)."""
    from app import comparar
    c = d.get("comparacion")
    if not c:
        return
    inf._apartado(doc, "Comparación con la versión anterior")
    if not c.get("encontrada"):
        inf._parrafo(doc, f"No se encuentra la validación con la que se compara ({c.get('ruta', '')}).", color="485862")
        return
    version = f" ({c['version']})" if c.get("version") else ""
    inf._parrafo(doc, f"Con «{c['nombre']}»{version}. "
                      "Nuevos fallos: NO OK ahora y no antes; arregladas: NO OK antes y bien ahora.", color="485862")
    inf._tabla(doc, ["Cambio", "Pruebas"], [[comparar.VISIBLES[k], str(n)] for k, n in c["cuentas"].items()], [8, 4])
    if len(d.get("tendencia") or []) >= 2:
        inf._parrafo(doc, "Evolución por versión:", negrita=True)
        inf._tabla(doc, ["Validación", "Versión", "Validadas", "NO OK", "Bloqueadas", "Pendientes"],
                   [[f["nombre"], f["version"], f"{f['totales']['validada']} ({f['porcentaje_validadas']} %)",
                     str(f["totales"]["no_ok"]), str(f["totales"]["bloqueada"]), str(f["totales"]["pendiente"])] for f in d["tendencia"]],
                   [6, 7, 3.5, 2.5, 3, 3])
    filas = [f for f in c["filas"] if f["categoria"] != "sin_cambios"]
    if filas:
        orden = {k: i for i, k in enumerate(comparar.CATEGORIAS)}
        filas.sort(key=lambda f: orden[f["categoria"]])
        txt = lambda e: vc.ESTADOS_VISIBLES.get(e, CELDA_TXT.get(e, e)) if e else "—"
        tabla = inf._tabla(doc, ["Prueba", "Título", "Antes", "Ahora", "Cambio"],
                           [[f["id"], f["titulo"], txt(f["antes"]), txt(f["ahora"]), comparar.VISIBLES[f["categoria"]]] for f in filas],
                           [3.4, 10.6, 3, 3, 5])
        for fila, f in zip(tabla.rows[1:], filas):
            if f["antes"]:
                _colorear(fila.cells[2], f["antes"])
            if f["ahora"]:
                _colorear(fila.cells[3], f["ahora"])


REQ_CLASE = {"fallido": "no_ok", "bloqueado": "bloqueada", "pendiente": "pendiente", "verificado": "validada",
             "sin_pruebas": vc.SIN_PLANIFICAR, "no_aplica": "no_aplica"}


def escribir_requisitos(doc, d: dict[str, Any]) -> None:
    """Requisitos verificados según el resultado de sus pruebas en esta validación."""
    r = d.get("requisitos")
    if not r:
        return
    inf._apartado(doc, "Requisitos")
    inf._parrafo(doc, "Un requisito está verificado cuando todas las pruebas de esta validación que lo citan están "
                      "validadas; falla si alguna es NO OK. «Sin pruebas aquí»: necesita pruebas, pero ninguna de esta "
                      f"validación lo cita. Verificados: {r['porcentaje_verificados']} % de los que necesitan pruebas.", color="485862")
    tabla = inf._tabla(doc, ["Estado", "Requisitos"], [[vc.REQ_VISIBLES[e], str(r["totales"][e])] for e in vc.REQ_ESTADOS], [8, 4])
    for fila, e in zip(tabla.rows[1:], vc.REQ_ESTADOS):
        _colorear(fila.cells[0], REQ_CLASE[e])
    if r["modificados"]:
        inf._parrafo(doc, f"{r['modificados']} requisito(s) han cambiado desde la última revisión de sus pruebas (marcados «cambiado»).",
                     color=inf.COLOR_ESTADO["bloqueada"])
    filas = [x for x in r["lista"] if x["estado"] != "no_aplica"]
    txt = lambda p: f"{p['id']} ({vc.ESTADOS_VISIBLES[p['estado']]})"
    tabla = inf._tabla(doc, ["Requisito", "Título", "Estado", "Pruebas"],
                       [[x["id"] + (" (cambiado)" if x["modificado"] else ""), x["titulo"], vc.REQ_VISIBLES[x["estado"]],
                         ", ".join(txt(p) for p in x["pruebas"]) + (f"; {len(x['fuera'])} fuera de la validación" if x["fuera"] else "")]
                        for x in filas], [3.6, 9, 3.4, 9])
    for fila, x in zip(tabla.rows[1:], filas):
        _colorear(fila.cells[2], REQ_CLASE[x["estado"]])


def escribir_matriz(doc, d: dict[str, Any]) -> None:
    inf._apartado(doc, "Resultado por prueba y entorno")
    inf._parrafo(doc, "En cursiva, sin fondo: resultados en un entorno que la prueba no indica (se muestran, pero no cuentan). "
                      "«—»: la prueba no pide ese entorno.", color="485862")
    entornos = d["entornos"]
    ancho_entorno = 2.6
    anchos = [3.2, 25 - 3.2 - 2.8 - ancho_entorno * len(entornos), *[ancho_entorno] * len(entornos), 2.8]
    filas = []
    for p in d["pruebas"]:
        celdas = []
        for e in entornos:
            c = p["entornos"].get(e)
            celdas.append(CELDA_TXT.get(c["estado"], c["estado"]) if c else "—")
        filas.append([p["id"], p["titulo"], *celdas, vc.ESTADOS_VISIBLES[p["estado"]]])
    tabla = inf._tabla(doc, ["Prueba", "Título", *entornos, "Versión"], filas, anchos)
    for fila, p in zip(tabla.rows[1:], d["pruebas"]):
        for i, e in enumerate(entornos):
            c = p["entornos"].get(e)
            if c:
                _colorear(fila.cells[2 + i], c["estado"], c["cuenta"])
        _colorear(fila.cells[-1], p["estado"])


def escribir_detalle(doc, d: dict[str, Any]) -> None:
    """Pruebas que no están validadas, con el resultado de cada entorno."""
    pendientes = [p for p in d["pruebas"] if p["estado"] in ("no_ok", "bloqueada", "pendiente")]
    if not pendientes:
        return
    inf._apartado(doc, "Pruebas no validadas")
    filas, estados = [], []
    for p in pendientes:
        for e, c in p["entornos"].items():
            if not c["cuenta"] or c["estado"] in ("ok", "no_aplica"):
                continue
            v = c["vigente"] or {}
            nota = " · ".join(x for x in (v.get("observaciones"), f"Incidencia: {v['incidencia']}" if v.get("incidencia") else "") if x)
            donde = f"{v.get('ejecucion', '')}, {inf._fecha(v.get('fecha'))}" if v.get("fecha") else (v.get("ejecucion") or "ninguna ejecución la incluye")
            filas.append([p["id"], e, CELDA_TXT[c["estado"]], donde, nota])
            estados.append(c["estado"])
    tabla = inf._tabla(doc, ["Prueba", "Entorno", "Resultado", "Ejecución", "Observaciones"], filas, [3.2, 2.8, 2.8, 6.5, 9.7])
    for fila, e in zip(tabla.rows[1:], estados):
        _colorear(fila.cells[2], e)


def generar_informe(validacion: dict[str, Any], salida: str | Path,
                    capitulos: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    d = vc.consolidar(validacion, capitulos)
    salida = Path(salida)
    if salida.suffix.lower() != ".docx":
        salida = salida.with_suffix(".docx")
    salida.parent.mkdir(parents=True, exist_ok=True)
    doc = yd.preparar_documento(1)
    _apaisado(doc)
    escribir_resumen(doc, d)
    escribir_comparacion(doc, d)
    escribir_requisitos(doc, d)
    escribir_detalle(doc, d)
    doc.add_page_break()
    escribir_matriz(doc, d)
    pie = doc.sections[0].footer.paragraphs[0]
    pie.text = f"{validacion['datos'].get('nombre', '')} · informe de validación · generado con {firma()}"
    for run in pie.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor.from_string("72838D")
    doc.save(salida)
    return {"archivo": str(salida), "pruebas": d["total"], "resumen": d}


def main(argv=None, prog=None) -> None:
    ap = argparse.ArgumentParser(prog=prog, description="Informe de la validación de una versión")
    ap.add_argument("validacion", help="carpeta de la validación (con validacion.yaml)")
    ap.add_argument("-o", "--salida", help="archivo DOCX de salida (por defecto, dentro de la validación)")
    ap.add_argument("--pdf", action="store_true", help="genera también el PDF (con LibreOffice o Word)")
    args = ap.parse_args(argv)
    try:
        validacion = vc.cargar(args.validacion)
        salida = Path(args.salida) if args.salida else validacion["carpeta"] / f"Informe_{validacion['carpeta'].name}.docx"
        datos = generar_informe(validacion, salida)
    except ValueError as error:
        raise SystemExit(str(error))
    t = datos["resumen"]["totales"]
    print(f"{datos['pruebas']} pruebas: {t['validada']} validadas, {t['no_ok']} NO OK, {t['bloqueada']} bloqueadas, "
          f"{t['pendiente']} pendientes -> {datos['archivo']}")
    if args.pdf:
        print(f"PDF -> {inf.convertir_a_pdf(datos['archivo'])}")


if __name__ == "__main__":
    main()
