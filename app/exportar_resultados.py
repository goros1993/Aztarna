#!/usr/bin/env python3
"""Resultados de una ejecución o de una validación en CSV para Excel.

Separado por «;» y en UTF-8 con BOM, para que Excel lo abra bien con un doble
clic (acentos incluidos), como la matriz de trazabilidad.

Uso:
    python herramientas.py resultados ruta/a/la/ejecución-o-validación [-o resultados.csv]
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from app import ejecucion_core as ej
from app import validacion_core as vc


def _escribir(salida: str | Path, cabecera: list[str], filas: list[list[Any]]) -> Path:
    salida = Path(salida)
    if salida.suffix.lower() != ".csv":
        salida = salida.with_suffix(".csv")
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(cabecera)
        escritor.writerows([["" if v is None else str(v) for v in fila] for fila in filas])
    return salida


def _fecha(valor: Any) -> str:
    return str(valor or "").replace("T", " ")


def csv_ejecucion(campaña: dict[str, Any], capitulos: list[dict[str, Any]], salida: str | Path) -> Path:
    """Una fila por prueba: resultado, fecha, ejecutor, observaciones, incidencia, evidencias e intentos."""
    resumen = ej.resumen(campaña, capitulos)
    filas = []
    for p in resumen["pruebas"]:
        r = campaña["resultados"].get(p["id"]) or {}
        filas.append([p["capitulo"], p["id"], p["titulo"], ej.ESTADOS_VISIBLES[p["estado"]], _fecha(r.get("fecha")),
                      r.get("ejecutor"), r.get("observaciones"), r.get("incidencia"), len(r.get("evidencias") or []),
                      len(r.get("intentos") or []), "sí" if p["cambiada"] else ""])
    return _escribir(salida, ["Capítulo", "ID", "Título", "Resultado", "Fecha", "Ejecutor", "Observaciones", "Incidencia",
                              "Evidencias", "Intentos anteriores", "Cambiada después de ejecutarse"], filas)


def csv_validacion(consolidado: dict[str, Any], salida: str | Path) -> Path:
    """Una fila por prueba: resultado de la versión y, por cada entorno, su resultado, ejecución, fecha y ejecutor."""
    entornos = consolidado["entornos"]
    cabecera = ["Capítulo", "ID", "Título", "Resultado de la versión", "Entornos que pide"]
    for e in entornos:
        cabecera += [f"{e}: resultado", f"{e}: ejecución", f"{e}: fecha", f"{e}: ejecutor"]
    cabecera += ["Observaciones", "Incidencias"]
    filas = []
    for p in consolidado["pruebas"]:
        fila = [p["capitulo"], p["id"], p["titulo"], vc.ESTADOS_VISIBLES[p["estado"]], ", ".join(p["requeridos"])]
        observaciones, incidencias = [], []
        for e in entornos:
            c = p["entornos"].get(e)
            v = (c or {}).get("vigente") or {}
            if not c:
                fila += ["—", "", "", ""]
                continue
            estado = {"ok": "OK", "no_ok": "NO OK", "bloqueada": "Bloqueada", "no_aplica": "No aplica", "pendiente": "Pendiente",
                      vc.SIN_PLANIFICAR: "Sin planificar"}.get(c["estado"], c["estado"])
            fila += [estado + ("" if c["cuenta"] else " (no cuenta)"), v.get("ejecucion"), _fecha(v.get("fecha")) if v.get("estado") != "pendiente" else "",
                     v.get("ejecutor")]
            if v.get("observaciones"):
                observaciones.append(f"{e}: {v['observaciones']}")
            if v.get("incidencia") and v["incidencia"] not in incidencias:
                incidencias.append(v["incidencia"])
        filas.append(fila + [" | ".join(observaciones), ", ".join(incidencias)])
    return _escribir(salida, cabecera, filas)


def main(argv=None, prog=None) -> None:
    from app.editor_core import read_chapters
    ap = argparse.ArgumentParser(prog=prog, description="Resultados de una ejecución o de una validación en CSV para Excel")
    ap.add_argument("carpeta", help="carpeta de la ejecución o de la validación")
    ap.add_argument("-o", "--salida", help="archivo CSV (por defecto, resultados_<carpeta>.csv dentro de ella)")
    args = ap.parse_args(argv)
    carpeta = Path(args.carpeta)
    salida = Path(args.salida) if args.salida else carpeta / f"resultados_{carpeta.name}.csv"
    try:
        if vc.es_validacion(carpeta):
            ruta = csv_validacion(vc.consolidar(vc.cargar(carpeta)), salida)
        elif ej.es_campaña(carpeta):
            campaña = ej.cargar(carpeta)
            ruta = csv_ejecucion(campaña, ej.capitulos_de(campaña), salida)
        else:
            raise ValueError(f"{carpeta} no es una ejecución ni una validación.")
    except ValueError as error:
        raise SystemExit(str(error))
    print(f"Resultados -> {ruta}")


if __name__ == "__main__":
    main()
